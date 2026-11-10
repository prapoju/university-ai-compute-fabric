"""The confirmation use case (story 2.3, FR-09, AD-4, AD-5, AD-6, AD-10; ``post_confirm``).

Order (normative, contracts): P1 the proposal exists -> P5 a state other than ``dry_run`` answers
the persisted proposal to the identical token and ``CONFIRMATION_CONFLICT`` to another -> P2 the
token equals, then is fresh on the Clock port -> P4 there is something actionable -> P3 the stored
selector is re-executed through the audited read-only ports and the set must still match -> the
claim ``dry_run -> confirmed``. The claim is one conditional ``UPDATE`` in the same writer
transaction as the audit rows; when it changes no row another confirm won, so the proposal is read
again and P5 decides (a lost race is never mapped to an error code).

The request carries no identity and the session context is never consulted: the session row is read
only for the ``operator_role`` the audit schema needs, whatever its status. Nothing is dispatched
here (story 2.4); the executor does not exist yet. A failure before the claim writes nothing.
"""

from __future__ import annotations

import logging
import threading
import weakref
from collections.abc import Sequence

from src.application.audit_writer import AuditWriter
from src.application.proposal_dispatcher import ProposalDispatcher
from src.application.tool_audit import RecordedCall, ToolCallRecorder
from src.domain.canonical_strings import S_CAP
from src.domain.confirmation import (
    STALE_LAST_LINE,
    delta_lines,
    delta_text,
    diff,
    expired_delta,
    has_actionable,
    token_is_fresh,
    tokens_match,
)
from src.domain.dry_run import JOBS_PORT, NODES_PORT, enumerate_items, reexecution_query
from src.domain.error_catalog import fail
from src.domain.result import Failure, Ok, Result, is_failure
from src.dto import ClockReadDTO, ConfirmationDTO, ProposalDTO, SessionDTO
from src.ports.inbound import ConfirmUseCases
from src.ports.outbound import (
    AuditEntry,
    ClockPort,
    IdGenPort,
    JobsPort,
    NodesPort,
    ProposalStorePort,
    SessionStorePort,
    UnitOfWorkError,
    UnitOfWorkPort,
)

_HEAD = "toolcall.confirm_and_dispatch"
logger = logging.getLogger(__name__)
# the refusals worth a trace: they say someone asked to confirm what could not be confirmed
_REJECTIONS = frozenset(
    {
        "PROPOSAL_NOT_FOUND",
        "GATE_TOKEN_INVALID",
        "CONFIRMATION_CONFLICT",
        "CONFIRMATION_STALE",
        "DRY_RUN_EMPTY_SET",
        "PROPOSAL_STATE_INVALID",
    }
)
_ATTEMPTS = 3  # the first read plus two re-reads after a lost claim; the second always settles


class _Guard:
    """A per-proposal lock that can be held weakly (a bare ``threading.Lock`` cannot)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def __enter__(self) -> None:
        self._lock.acquire()

    def __exit__(self, *_: object) -> None:
        self._lock.release()


class ConfirmationService(ConfirmUseCases):
    def __init__(
        self,
        *,
        proposals: ProposalStorePort,
        sessions: SessionStorePort,
        clock: ClockPort,
        idgen: IdGenPort,
        jobs: JobsPort,
        nodes: NodesPort,
        uow: UnitOfWorkPort,
        audit: AuditWriter,
        recorder: ToolCallRecorder,
        dispatcher: ProposalDispatcher,
        token_ttl_seconds: int,
    ) -> None:
        self._dispatcher = dispatcher
        self._guards: weakref.WeakValueDictionary[str, _Guard] = weakref.WeakValueDictionary()
        self._registry = threading.Lock()
        self._proposals = proposals
        self._sessions = sessions
        self._clock = clock
        self._idgen = idgen
        self._jobs = jobs
        self._nodes = nodes
        self._uow = uow
        self._audit = audit
        self._recorder = recorder
        self._ttl = token_ttl_seconds

    def _guard(self, proposal_id: str) -> _Guard:
        with self._registry:
            guard = self._guards.get(proposal_id)
            if guard is None:
                guard = _Guard()
                self._guards[proposal_id] = guard
            return guard

    def post_confirm(self, proposal_id: str, gate_token: str) -> Result[ProposalDTO]:
        # one confirmation of a proposal at a time in this process: a simultaneous identical confirm
        # waits for the winner and then answers the settled proposal (the claim is still the guard
        # against another process)
        with self._guard(proposal_id):
            result = self._confirm(proposal_id, gate_token)
        if isinstance(result, Failure) and result.code in _REJECTIONS:
            # a rejected attempt writes no audit row (D7); this line is its only trace, and it never
            # holds the token. ``%r`` escapes anything a caller put in the id (review P-1)
            logger.warning(
                "confirmation rejected: proposal=%.64r code=%s", proposal_id, result.code
            )
        return result

    def _confirm(self, proposal_id: str, gate_token: str) -> Result[ProposalDTO]:
        read: ClockReadDTO | None = None  # one clock read per request, once the proposal exists
        for _ in range(_ATTEMPTS):
            found = self._proposals.get(proposal_id)  # P1
            if is_failure(found):
                return found
            proposal = found.value
            if proposal is None:
                return fail("PROPOSAL_NOT_FOUND", pid=proposal_id)
            if proposal.state != "dry_run":  # P5, before the token lifetime
                return _settled(proposal, gate_token)

            if read is None:
                now = self._clock.now()
                if is_failure(now):
                    return now
                read = now.value
            instant = read.instant
            gate = self._gate(proposal, gate_token, instant)  # P2, P4
            if gate is not None:
                return gate

            with self._recorder.turn() as calls:  # P3
                stale = self._revalidate(proposal)
            if isinstance(stale, Failure):
                return stale
            session = self._session_of(proposal)
            if is_failure(session):
                return session
            claimed = self._claim(proposal, gate_token, read, calls, session.value)
            if is_failure(claimed):
                return claimed
            if claimed.value:  # committed as ``dispatched``: now, and only now, the executor
                return self._dispatcher.dispatch(_dispatched(proposal, instant), session.value)
            # another confirm won the claim: read again and let P5 answer
        return fail("PROVIDER_UNAVAILABLE", observed=("the confirmation could not be settled",))

    # -- P2 and P4 ------------------------------------------------------------------------------
    def _gate(self, proposal: ProposalDTO, token: str, instant: str) -> Failure | None:
        if not tokens_match(token, proposal.gate_token):
            return fail("GATE_TOKEN_INVALID", pid=proposal.proposal_id)
        snapshot = proposal.dry_run_snapshot
        if not token_is_fresh(snapshot.snapshot_timestamp, instant, self._ttl):
            lapsed = expired_delta(snapshot.snapshot_timestamp, instant, self._ttl)
            return fail("CONFIRMATION_STALE", observed=(lapsed,), delta=lapsed)
        if not has_actionable(snapshot.affected_items):  # before any provider read
            return fail("DRY_RUN_EMPTY_SET")
        return None

    # -- P3 -------------------------------------------------------------------------------------
    def _revalidate(self, proposal: ProposalDTO) -> Failure | None:
        """Re-execute the stored selector; ``None`` when the set still matches the snapshot."""
        selector = proposal.dry_run_snapshot.selector
        port = {JOBS_PORT: self._jobs, NODES_PORT: self._nodes}.get(selector.method)
        if port is None:  # the table allowlists the method, so this is a corrupted row
            return Failure(
                "PROVIDER_UNAVAILABLE", observed=(f"unknown selector {selector.method}",)
            )
        listed = port.select(reexecution_query(selector))
        if is_failure(listed):
            return listed  # an outage is never "unchanged" (AD-12)
        delta = diff(proposal.dry_run_snapshot.affected_items, enumerate_items(listed.value))
        if delta.empty:
            return None
        return fail(
            "CONFIRMATION_STALE",
            observed=(*delta_lines(delta), STALE_LAST_LINE),
            delta=delta_text(delta),
        )

    # -- the claim, with its audit rows ---------------------------------------------------------
    def _session_of(self, proposal: ProposalDTO) -> Result[SessionDTO]:
        """The session row, read only for the audit's ``operator_role`` (never its context)."""
        stored = self._sessions.get(proposal.session_id)
        if is_failure(stored):
            return stored
        if stored.value is None:
            return fail("PROPOSAL_NOT_FOUND", pid=proposal.proposal_id)
        return Ok(stored.value.session)

    def _claim(
        self,
        proposal: ProposalDTO,
        token: str,
        read: ClockReadDTO,
        calls: Sequence[RecordedCall],
        session: SessionDTO,
    ) -> Result[bool]:
        head = RecordedCall(
            _HEAD,
            {"proposal_id": proposal.proposal_id},
            "ok",
            result={
                "state": "confirmed",
                "affected_count": len(proposal.dry_run_snapshot.affected_items),
            },
        )
        entries = self._audit.entries_for(session, read, head, calls)
        if is_failure(entries):
            return entries
        return self._commit(proposal.proposal_id, token, read.instant, entries.value)

    def _commit(
        self, proposal_id: str, token: str, instant: str, entries: list[AuditEntry]
    ) -> Result[bool]:
        """The claim and the audit rows in one unit of work; ``Ok(False)`` when the claim lost."""
        try:
            with self._uow.atomic() as tx:
                claimed = self._proposals.claim(proposal_id, token, instant)
                if is_failure(claimed):
                    tx.abort()
                    return claimed
                if not claimed.value:
                    return Ok(False)  # nothing was written: another confirm already won
                begun = self._proposals.begin_dispatch(proposal_id, instant)
                if is_failure(begun):
                    tx.abort()
                    return begun
                if not begun.value:  # confirmed a moment ago in this very transaction: impossible
                    tx.abort()
                    return Failure(
                        "PROVIDER_UNAVAILABLE", observed=("the dispatch was not claimed",)
                    )
                audited = self._audit.write(entries)
                if is_failure(audited):
                    tx.abort()
                    return audited
        except UnitOfWorkError as exc:
            return Failure("PROVIDER_UNAVAILABLE", observed=(str(exc),))
        return Ok(True)


def _settled(proposal: ProposalDTO, token: str) -> Result[ProposalDTO]:
    """P5: a proposal that is not in ``dry_run`` already has a confirmation (or never had one)."""
    if proposal.state == "refused":
        return fail(
            "PROPOSAL_STATE_INVALID", pid=proposal.proposal_id, state="refused", action="confirm"
        )
    if tokens_match(token, proposal.gate_token):
        return Ok(proposal)  # the persisted proposal, never a second transition
    return fail("CONFIRMATION_CONFLICT", pid=proposal.proposal_id, state=proposal.state)


def _dispatched(proposal: ProposalDTO, instant: str) -> ProposalDTO:
    return proposal.model_copy(
        update={
            "state": "dispatched",
            "confirmation": ConfirmationDTO(confirmed_at=instant, caption=S_CAP),
        }
    )
