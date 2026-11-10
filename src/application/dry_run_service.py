"""The dry-run use case (story 2.2, FR-09, AD-3, AD-4, AD-6, AD-10; contracts ``post_dry_run``).

Order: the request shape (P1) -> the session is active (P2) -> one clock read -> inside the turn's
tool-call recorder: resolve and fit every target (P3), the compound check of the query text (P4),
and the enumeration of the affected items through the audited read-only ports. Then every id is
minted, and one writer transaction inserts the ``dry_run`` proposal together with its audit rows,
``toolcall.propose_destructive_action`` first and the reads after it (D12). Anything that fails
before that transaction writes nothing, so a provider outage leaves no partial snapshot (AD-12).

The use case holds read-only provider ports and the proposal store: it cannot touch simulated state
(AD-1, AD-3), and it never starts a dispatch (that is story 2-4).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import get_args

from src.application.audit_writer import AuditWriter
from src.application.entity_resolver import EntityResolver, ResolvedTarget, Unresolved
from src.application.session_service import session_usable
from src.application.tool_audit import RecordedCall, ToolCallRecorder
from src.domain import canonical_strings as cs
from src.domain.dry_run import (
    JOBS_PORT,
    build_selector,
    confirmation_enabled,
    enumerate_items,
    impact_summary,
    token_expiry,
)
from src.domain.error_catalog import fail
from src.domain.result import Failure, Ok, Result, is_failure
from src.domain.safety import (
    INTENT_CODE,
    JOB_VERBS,
    Compound,
    DestructiveRequest,
    Fleet,
    Target,
    TargetKind,
    accepts,
    parse_destructive,
)
from src.domain.session_rules import normalise_query
from src.dto import ActionVerb, DryRunSnapshotDTO, ProposalDTO
from src.ports.inbound import CanonicalOutcome, DestructiveUseCases, DryRunOutcome
from src.ports.outbound import (
    ClockPort,
    IdGenPort,
    JobsPort,
    NodesPort,
    ProposalStorePort,
    SessionStorePort,
    UnitOfWorkError,
    UnitOfWorkPort,
)

_KINDS: tuple[str, ...] = ("group", "job", "node")
_VERBS: frozenset[str] = frozenset(get_args(ActionVerb))
_HEAD = f"toolcall.{INTENT_CODE}"
MAX_TARGET_REFS = 50  # one request, one bounded set of provider reads and audit rows (review P-1)

Aim = tuple[TargetKind | None, list[str]] | CanonicalOutcome

Outcome = DryRunOutcome | CanonicalOutcome


class DryRunService(DestructiveUseCases):
    def __init__(
        self,
        *,
        sessions: SessionStorePort,
        proposals: ProposalStorePort,
        clock: ClockPort,
        idgen: IdGenPort,
        resolver: EntityResolver,
        jobs: JobsPort,
        nodes: NodesPort,
        uow: UnitOfWorkPort,
        audit: AuditWriter,
        recorder: ToolCallRecorder,
        token_ttl_seconds: int,
    ) -> None:
        self._sessions = sessions
        self._proposals = proposals
        self._clock = clock
        self._idgen = idgen
        self._resolver = resolver
        self._jobs = jobs
        self._nodes = nodes
        self._uow = uow
        self._audit = audit
        self._recorder = recorder
        self._ttl = token_ttl_seconds

    # -- the two entries ------------------------------------------------------------------------
    def post_dry_run(
        self, query_text: str, action: str, target_refs: list[str], session_id: str
    ) -> Result[Outcome]:
        return self._post(query_text, action, target_refs, session_id, None)

    def redispatch(
        self, parent: ProposalDTO, query_text: str, action: str, target_refs: list[str]
    ) -> Result[Outcome]:
        """A new dry-run in the parent's session, linked to it (story 2.4, PD-6)."""
        return self._post(query_text, action, target_refs, parent.session_id, parent)

    def _post(
        self,
        query_text: str,
        action: str,
        target_refs: list[str],
        session_id: str,
        supersedes: ProposalDTO | None,
    ) -> Result[Outcome]:
        if action not in _VERBS or not 1 <= len(target_refs) <= MAX_TARGET_REFS:  # P1
            return fail("VALIDATION_MALFORMED_BODY", schema_id="PostDryRunRequest")
        query = normalise_query(query_text)
        if is_failure(query):
            return query
        verb: ActionVerb = action  # type: ignore[assignment]  # checked against the enum above
        aim = lambda: self._targets(verb, target_refs)  # noqa: E731
        return self._run(session_id, verb, query.value, aim, supersedes)

    def dry_run_request(self, session_id: str, request: DestructiveRequest) -> Result[Outcome]:
        target = request.target
        return self._run(session_id, request.verb, None, lambda: self._parsed(request.verb, target))

    # -- the common path ------------------------------------------------------------------------
    def _run(
        self,
        session_id: str,
        action: ActionVerb,
        query: str | None,
        aim: Callable[[], Result],
        supersedes: ProposalDTO | None = None,
    ) -> Result[Outcome]:
        found = self._sessions.get(session_id)
        if is_failure(found):
            return found
        if found.value is None:
            return fail("SESSION_NOT_FOUND", sid=session_id)
        now = self._clock.now()  # one read per use case
        if is_failure(now):
            return now
        usable = session_usable(found.value, now.value.instant)
        if is_failure(usable):
            return usable
        if not usable.value:
            return fail("SESSION_EXPIRED", sid=session_id)
        session = found.value.session

        with self._recorder.turn() as calls:
            aimed = aim()  # P3: resolve and fit
            if is_failure(aimed):
                return aimed
            if isinstance(aimed.value, CanonicalOutcome):
                return Ok(aimed.value)
            kind, keys = aimed.value
            if query is not None and isinstance(parse_destructive(query), Compound):  # P4
                return Ok(_clarify(cs.R_COMPOUND_DESTRUCTIVE))
            selection = build_selector(action, kind, keys)
            port = self._jobs if selection.method == JOBS_PORT else self._nodes
            listed = port.select(selection.query())
            if is_failure(listed):
                return listed  # an outage is never an empty set (AD-12)
            records = listed.value

        items = enumerate_items(records)
        snapshot = DryRunSnapshotDTO(
            selector=selection.persisted(),
            affected_items=items,
            snapshot_timestamp=now.value.instant,
        )
        proposal_id = self._idgen.new_id("proposal")  # D9: minted before the transaction
        if is_failure(proposal_id):
            return proposal_id
        token = self._idgen.new_id("gate_token")
        if is_failure(token):
            return token
        proposal = ProposalDTO(
            proposal_id=proposal_id.value,
            session_id=session_id,
            state="dry_run",
            action=action,
            supersedes_proposal_id=supersedes.proposal_id if supersedes else None,
            dry_run_snapshot=snapshot,
            gate_token=token.value,
        )
        head = RecordedCall(
            _HEAD,
            {
                "proposal_id": proposal.proposal_id,
                "action": action,
                "targets": list(keys),
                **({"supersedes": supersedes.proposal_id} if supersedes else {}),
            },
            "ok",
            result={
                "state": "dry_run",
                "affected_count": len(items),
                **({"supersedes": supersedes.proposal_id} if supersedes else {}),
            },
        )
        entries = self._audit.entries_for(session, now.value, head, calls)
        if is_failure(entries):
            return entries
        written = self._store(proposal, now.value.instant, entries.value, supersedes)
        if is_failure(written):
            return written
        return Ok(
            DryRunOutcome(
                proposal=proposal,
                impact_summary=impact_summary(action, selection, records),
                token_expires_at=token_expiry(now.value.instant, self._ttl),
                confirmation_enabled=confirmation_enabled(items),
            )
        )

    def _store(
        self,
        proposal: ProposalDTO,
        instant: str,
        entries: list,
        supersedes: ProposalDTO | None = None,
    ) -> Result[None]:
        """The proposal and its audit rows in one unit of work: both commit, or neither does.

        A re-dispatch supersedes its parent in the same transaction (C7), unless the parent was
        already partly applied: it then stays ``failed``, as the contract says.
        """
        try:
            with self._uow.atomic() as tx:
                added = self._proposals.add(proposal, instant)
                if is_failure(added):
                    tx.abort()
                    return added
                if supersedes is not None and not _partly_applied(supersedes):
                    done = self._proposals.supersede(supersedes.proposal_id, instant)
                    if is_failure(done):
                        tx.abort()
                        return done
                    if not done.value:  # no longer ``failed``: another re-dispatch got there first
                        tx.abort()
                        return fail(
                            "PROPOSAL_STATE_INVALID",
                            pid=supersedes.proposal_id,
                            state="superseded",
                            action="re-dispatch",
                        )
                audited = self._audit.write(entries)
                if is_failure(audited):
                    tx.abort()
                    return audited
        except UnitOfWorkError as exc:
            return Failure("PROVIDER_UNAVAILABLE", observed=(str(exc),))
        return Ok(None)

    # -- aiming: which kind of target, and which resolved keys ----------------------------------
    def _parsed(self, action: ActionVerb, target: Target | Fleet) -> Result[Aim]:
        if isinstance(target, Fleet):
            if not accepts(action, target):
                return fail("VALIDATION_BAD_ACTION", value=f"{action} on the whole fleet")
            return Ok((None, []))
        found = self._resolver.resolve_target(target.kind, target.token)
        if is_failure(found):
            return found
        return _aimed(action, [(target, found.value)])

    def _targets(self, action: ActionVerb, refs: Sequence[str]) -> Result[Aim]:
        """Typed refs (``group#x``) keep their kind; a bare ref takes the kind of its action.

        A repeated ref is read once, and every ref is resolved once: the dry-run's reads are audit
        rows, so the audit of a request grows with its distinct refs only (review P-1).
        """
        distinct = list(dict.fromkeys(refs))
        kinds = [_typed_kind(ref) for ref in distinct]
        if None not in kinds and len(set(kinds)) > 1:  # decided before any read
            return Ok(_clarify(cs.R_MIXED_TARGETS))
        resolved: list[tuple[Target, ResolvedTarget | Unresolved]] = []
        for ref, kind in zip(distinct, kinds, strict=True):
            found = self._resolve(action, ref, kind)
            if is_failure(found):
                return found
            resolved.append(found.value)
        return _aimed(action, resolved)

    def _resolve(
        self, action: ActionVerb, ref: str, kind: TargetKind | None
    ) -> Result[tuple[Target, ResolvedTarget | Unresolved]]:
        """One lookup per candidate kind: node verbs act on nodes, job verbs try group then job."""
        candidates: tuple[TargetKind, ...] = (
            (kind,) if kind else ("group", "job") if action in JOB_VERBS else ("node",)
        )
        first_miss: tuple[Target, Unresolved] | None = None
        for candidate in candidates:
            found = self._resolver.resolve_target(candidate, ref)
            if is_failure(found):
                return found
            if not isinstance(found.value, Unresolved):
                return Ok((Target(candidate, ref), found.value))
            first_miss = first_miss or (Target(candidate, ref), found.value)
        assert first_miss is not None  # candidates is never empty
        return Ok(first_miss)


def _aimed(
    action: ActionVerb, resolved: list[tuple[Target, ResolvedTarget | Unresolved]]
) -> Result[Aim]:
    """The kind and the distinct keys of resolved targets, or the reason there is none."""
    if len({target.kind for target, _ in resolved}) > 1:
        return Ok(_clarify(cs.R_MIXED_TARGETS))
    missing = list(
        dict.fromkeys(
            ref for _, found in resolved if isinstance(found, Unresolved) for ref in found.refs
        )
    )
    if missing:
        return Ok(CanonicalOutcome("ENTITY_NOT_FOUND", cs.entity_not_found(missing)))
    targets = [target for target, _ in resolved]
    keys = list(
        dict.fromkeys(found.key for _, found in resolved if isinstance(found, ResolvedTarget))
    )
    if not all(accepts(action, target) for target in targets):
        return fail("VALIDATION_BAD_ACTION", value=f"{action} on {', '.join(keys)}")
    return Ok((targets[0].kind, keys))


def _partly_applied(parent: ProposalDTO) -> bool:
    """The executor already applied something of the parent: it stays ``failed`` (Q2)."""
    return parent.executor_result is not None and parent.executor_result.applied_count > 0


def _typed_kind(ref: str) -> TargetKind | None:
    prefix, separator, _ = ref.partition("#")
    return prefix if separator and prefix in _KINDS else None  # type: ignore[return-value]


def _clarify(reason: str) -> CanonicalOutcome:
    return CanonicalOutcome("CLARIFICATION_REQUIRED", cs.clarification(reason))
