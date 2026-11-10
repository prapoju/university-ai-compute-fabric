"""The proposal dispatcher (story 2.4, FR-10, FR-16, AD-1, AD-3, AD-13, AD-15; contract P6, Q1-Q3).

Called by the confirmation, and only by it, once the proposal is committed as ``dispatched``. It
builds the frozen request from the stored row (the persisted selector and the stored token, never a
re-derived scope), calls the executor port exactly once outside any writer transaction, measures the
5 s on the clock, classifies the result against the snapshot's scope and records the outcome: the
proposal state, the executor columns and the one ``actor = executor`` audit row in one transaction.

An executor that is down, or that took more than 5.000 s, leaves the proposal ``failed`` (no result,
no audit row of the executor) and the typed failure is returned; a late result is never recorded on
the proposal and the call is never repeated (D4). A partial or larger-than-scope result is a
``failed`` proposal carrying the real records. The dispatcher never writes simulated state; only the
executor does.
"""

from __future__ import annotations

from src.application.audit_writer import AuditWriter
from src.domain.execution import classify, expected_keys, within_limit
from src.domain.result import Failure, Ok, Result, is_failure
from src.dto import ExecutorRequestDTO, ExecutorResultDTO, ProposalDTO, SessionDTO
from src.ports.outbound import (
    ClockPort,
    ExecutorPort,
    ProposalStorePort,
    UnitOfWorkError,
    UnitOfWorkPort,
)

_TOOL = "executor.dispatch"


class ProposalDispatcher:
    def __init__(
        self,
        *,
        proposals: ProposalStorePort,
        executor: ExecutorPort,
        clock: ClockPort,
        uow: UnitOfWorkPort,
        audit: AuditWriter,
    ) -> None:
        self._proposals = proposals
        self._executor = executor
        self._clock = clock
        self._uow = uow
        self._audit = audit

    def dispatch(self, proposal: ProposalDTO, session: SessionDTO) -> Result[ProposalDTO]:
        """Hand a ``dispatched`` proposal to the executor once and record what came back."""
        snapshot = proposal.dry_run_snapshot
        request = ExecutorRequestDTO(
            proposal_id=proposal.proposal_id,
            action=proposal.action,
            selector=snapshot.selector,
            gate_token=proposal.gate_token,
            dry_run_ref={"proposal_id": proposal.proposal_id},
        )
        started = self._clock.now()
        if is_failure(started):
            return started
        answered = self._executor.dispatch(request)  # the one call, outside any transaction
        returned = self._clock.now()
        if is_failure(returned):
            return returned
        late = not within_limit(started.value.instant, returned.value.instant)
        if is_failure(answered) or late:
            return self._failed(
                proposal, answered if is_failure(answered) else None, returned.value.instant
            )
        return self._record(proposal, session, answered.value, returned.value.instant)

    # -- the executor did not answer in time, or at all -----------------------------------------
    def _failed(
        self, proposal: ProposalDTO, refusal: Failure | None, instant: str
    ) -> Result[ProposalDTO]:
        marked = self._write(lambda: self._proposals.mark_failed(proposal.proposal_id, instant), [])
        if is_failure(marked):
            return marked
        if refusal is not None:
            return refusal  # the executor's own typed answer: down, a token it refused, a duplicate
        return Failure("EXECUTOR_UNAVAILABLE", observed=("no executor answer within 5 s",))

    # -- the executor answered in time ----------------------------------------------------------
    def _record(
        self, proposal: ProposalDTO, session: SessionDTO, result: ExecutorResultDTO, instant: str
    ) -> Result[ProposalDTO]:
        items = proposal.dry_run_snapshot.affected_items
        verdict = classify(expected_keys(items), result.applied_records)
        consistent = result.applied_count == len(result.applied_records)
        status = verdict
        if verdict == "applied" and not (result.status == "applied" and consistent):
            status = "partial"  # the executor's own report disagrees with the scope: not a success
        recorded = result.model_copy(update={"status": status})
        state = "executed" if status == "applied" else "failed"
        entry = self._audit.executor_entry(
            session,
            proposal.proposal_id,
            result.timestamp,
            {"tool_name": _TOOL, "status": status, "applied_count": result.applied_count},
        )
        if is_failure(entry):
            return entry
        written = self._write(
            lambda: self._proposals.record_result(proposal.proposal_id, state, recorded, instant),
            [entry.value],
        )
        if is_failure(written):
            return written
        return Ok(proposal.model_copy(update={"state": state, "executor_result": recorded}))

    def _write(self, step, entries: list) -> Result[None]:
        """``step`` (one conditional update) and the audit rows in one unit of work."""
        try:
            with self._uow.atomic() as tx:
                changed = step()
                if is_failure(changed):
                    tx.abort()
                    return changed
                if not changed.value:  # the proposal is no longer ``dispatched``: nothing to add
                    tx.abort()
                    return Failure("PROVIDER_UNAVAILABLE", observed=("the proposal moved on",))
                if entries:
                    audited = self._audit.write(entries)
                    if is_failure(audited):
                        tx.abort()
                        return audited
        except UnitOfWorkError as exc:
            return Failure("PROVIDER_UNAVAILABLE", observed=(str(exc),))
        return Ok(None)
