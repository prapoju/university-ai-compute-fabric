"""The simulated executor: the reference adapter of OP-15 and the only writer of simulated state.

It receives the frozen request, finds the proposal it refers to (a read of the proposal store),
accepts only a ``dispatched`` proposal with its token (so the executor route cannot bypass the
confirmation, D7), applies the **snapshot's** actionable items by key through the one write handle
the estate stores give it (never re-enumerating scope, D13), takes its own clock read for the result
timestamp (E44) and keeps its own record per proposal, so an identical retry returns the stored
result and a differing one is ``EXECUTOR_DUPLICATE_APPLY`` (E35, D11). It writes no proposal state.

Test controls (the story's seam): ``down``, ``delay_seconds`` (simulated latency, advanced on the
shared fake clock), ``apply_only`` (apply only the first N items), ``extra_applied`` (report keys
outside the scope), and the counters ``calls`` and ``requests``.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any

from src.adapters.outbound.sim.record_store import RecordStore
from src.domain.error_catalog import fail
from src.domain.execution import classify, effect, expected_keys, still_promised
from src.domain.result import Failure, Ok, Result, is_failure
from src.dto import ExecutorRequestDTO, ExecutorResultDTO, ProposalDTO
from src.ports.outbound import ClockPort, ExecutorPort, ProposalStorePort

_STORE_OF_KEY = {"job#": "jobs", "node#": "nodes"}


class SimExecutor(ExecutorPort):
    def __init__(
        self,
        *,
        clock: Any,  # a SimClock: ClockPort plus ``advance`` for the simulated latency
        stores: Mapping[str, RecordStore[Any] | Failure],
        proposals: ProposalStorePort,
    ) -> None:
        self._clock: ClockPort = clock
        self._advance = clock.advance
        self._stores = stores
        self._proposals = proposals
        self._lock = threading.Lock()
        self._records: dict[str, tuple[ExecutorRequestDTO, ExecutorResultDTO]] = {}
        self.down = False
        self.delay_seconds: float = 0
        self.apply_only: int | None = None
        self.extra_applied: list[str] = []
        self.calls = 0
        self.requests: list[ExecutorRequestDTO] = []

    # -- ExecutorPort ---------------------------------------------------------------------------
    def dispatch(self, request: ExecutorRequestDTO) -> Result[ExecutorResultDTO]:
        with self._lock:  # one apply at a time: the record check and the apply are one step
            self.calls += 1
            self.requests.append(request)
            if self.down:
                return Failure("EXECUTOR_UNAVAILABLE", observed=("the simulated executor is down",))
            found = self._proposals.get(request.proposal_id)
            if is_failure(found):
                return found
            proposal = found.value
            if proposal is None:
                return fail("PROPOSAL_NOT_FOUND", pid=request.proposal_id)
            if request.gate_token != proposal.gate_token:
                return fail("GATE_TOKEN_INVALID", pid=request.proposal_id)
            prior = self._records.get(request.proposal_id)
            if prior is not None:
                if prior[0] == request:
                    return Ok(prior[1])  # an identical retry is not an error
                return fail("EXECUTOR_DUPLICATE_APPLY", pid=request.proposal_id)
            if proposal.state != "dispatched":
                return fail(
                    "PROPOSAL_STATE_INVALID",
                    pid=request.proposal_id,
                    state=proposal.state,
                    action="apply",
                )
            return self._apply(request, proposal)

    def get(self, proposal_id: str) -> Result[ExecutorResultDTO | None]:
        with self._lock:
            stored = self._records.get(proposal_id)
        return Ok(None if stored is None else stored[1])

    # -- the apply ------------------------------------------------------------------------------
    def _apply(
        self, request: ExecutorRequestDTO, proposal: ProposalDTO
    ) -> Result[ExecutorResultDTO]:
        items = proposal.dry_run_snapshot.affected_items
        if self.delay_seconds:
            self._advance(seconds=self.delay_seconds)  # the executor works for that long
        todo = [item for item in items if item.actionable]
        if self.apply_only is not None:
            todo = todo[: self.apply_only]
        applied: list[str] = []
        for item in todo:
            store = self._store_of(item.key)
            if isinstance(store, Failure):
                return store
            current = store.get(item.key)
            if is_failure(current):
                return current
            if not still_promised(item, current.value):
                continue  # it changed since the dry-run: skipped, so the result is partial
            updated = effect(proposal.action, current.value)
            if updated is None:
                store.remove(item.key)
            else:
                store.replace(item.key, updated)
            applied.append(item.key)
        records = [*applied, *self.extra_applied]
        stamp = self._clock.now()  # the executor's own read, never the caller's instant
        if is_failure(stamp):
            return stamp
        result = ExecutorResultDTO(
            status=classify(expected_keys(items), records),
            applied_records=records,
            applied_count=len(records),
            timestamp=stamp.value.instant,
            source="executor",
        )
        self._records[request.proposal_id] = (request, result)
        return Ok(result)

    def _store_of(self, key: str) -> RecordStore[Any] | Failure:
        for prefix, name in _STORE_OF_KEY.items():
            if key.startswith(prefix):
                return self._stores[name]
        return Failure("PROVIDER_UNAVAILABLE", observed=(f"no store for {key}",))
