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
from src.application.entity_resolver import EntityResolver, Unresolved
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
        if action not in _VERBS or not target_refs:  # P1
            return fail("VALIDATION_MALFORMED_BODY", schema_id="PostDryRunRequest")
        query = normalise_query(query_text)
        if is_failure(query):
            return query
        verb: ActionVerb = action  # type: ignore[assignment]  # checked against the enum above
        return self._run(session_id, verb, query.value, lambda: self._targets(verb, target_refs))

    def dry_run_request(self, session_id: str, request: DestructiveRequest) -> Result[Outcome]:
        target = request.target
        return self._run(session_id, request.verb, None, lambda: self._parsed(request.verb, target))

    # -- the common path ------------------------------------------------------------------------
    def _run(
        self, session_id: str, action: ActionVerb, query: str | None, aim: Callable[[], Result]
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
            dry_run_snapshot=snapshot,
            gate_token=token.value,
        )
        head = RecordedCall(
            _HEAD,
            {"proposal_id": proposal.proposal_id, "action": action, "targets": list(keys)},
            "ok",
            result={"state": "dry_run", "affected_count": len(items)},
        )
        entries = self._audit.entries_for(session, now.value, head, calls)
        if is_failure(entries):
            return entries
        written = self._store(proposal, now.value.instant, entries.value)
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

    def _store(self, proposal: ProposalDTO, instant: str, entries: list) -> Result[None]:
        """The proposal and its audit rows in one unit of work: both commit, or neither does."""
        try:
            with self._uow.atomic() as tx:
                added = self._proposals.add(proposal, instant)
                if is_failure(added):
                    tx.abort()
                    return added
                audited = self._audit.write(entries)
                if is_failure(audited):
                    tx.abort()
                    return audited
        except UnitOfWorkError as exc:
            return Failure("PROVIDER_UNAVAILABLE", observed=(str(exc),))
        return Ok(None)

    # -- aiming: which kind of target, and which resolved keys ----------------------------------
    def _parsed(
        self, action: ActionVerb, target: Target | Fleet
    ) -> Result[tuple[TargetKind | None, list[str]] | CanonicalOutcome]:
        if isinstance(target, Fleet):
            if not accepts(action, target):
                return fail("VALIDATION_BAD_ACTION", value=f"{action} on the whole fleet")
            return Ok((None, []))
        return self._resolved(action, [target])

    def _targets(
        self, action: ActionVerb, refs: Sequence[str]
    ) -> Result[tuple[TargetKind | None, list[str]] | CanonicalOutcome]:
        """Typed refs (``group#x``) keep their kind; a bare ref takes the kind of its action."""
        targets: list[Target] = []
        for ref in refs:
            kind = _typed_kind(ref)
            if kind is None:
                kind = self._bare_kind(action, ref)
                if is_failure(kind):
                    return kind
                kind = kind.value
            targets.append(Target(kind, ref))
        return self._resolved(action, targets)

    def _bare_kind(self, action: ActionVerb, ref: str) -> Result[TargetKind]:
        """A bare ref: node verbs act on nodes; job verbs try a group first, then a job (D11)."""
        if action not in JOB_VERBS:
            return Ok("node")
        for kind in ("group", "job"):
            found = self._resolver.resolve_target(kind, ref)
            if is_failure(found):
                return found
            if not isinstance(found.value, Unresolved):
                return Ok(kind)
        return Ok("group")  # neither exists: resolving it later reports it as not found

    def _resolved(
        self, action: ActionVerb, targets: list[Target]
    ) -> Result[tuple[TargetKind | None, list[str]] | CanonicalOutcome]:
        if len({t.kind for t in targets}) > 1:
            return Ok(_clarify(cs.R_MIXED_TARGETS))
        keys: list[str] = []
        missing: list[str] = []
        for target in targets:
            resolution = self._resolver.resolve_target(target.kind, target.token)
            if is_failure(resolution):
                return resolution
            found = resolution.value
            if isinstance(found, Unresolved):
                missing.extend(found.refs)
                continue
            keys.append(found.key)
        if missing:
            return Ok(CanonicalOutcome("ENTITY_NOT_FOUND", cs.entity_not_found(missing)))
        if not all(accepts(action, t) for t in targets):
            return fail("VALIDATION_BAD_ACTION", value=f"{action} on {', '.join(keys)}")
        return Ok((targets[0].kind, keys))


def _typed_kind(ref: str) -> TargetKind | None:
    prefix, separator, _ = ref.partition("#")
    return prefix if separator and prefix in _KINDS else None  # type: ignore[return-value]


def _clarify(reason: str) -> CanonicalOutcome:
    return CanonicalOutcome("CLARIFICATION_REQUIRED", cs.clarification(reason))
