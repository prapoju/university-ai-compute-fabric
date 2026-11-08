"""The parallel read fan-out of one turn (story 1.6; review D-2.1 to D-2.6, log I2-35, I2-39).

Independent read-only tool calls run concurrently, each in a worker thread of one shared, bounded
pool, inside its own recorder lane. ``run`` returns the values in argument order, so evidence
positions, the audit rows and the reported failure never depend on completion order.

The budget is wall time: ``run`` waits for the reads with ``concurrent.futures.wait(timeout)`` and
answers ``PROVIDER_UNAVAILABLE`` (503) at the budget, even when a read is still running. A read
that finishes after the budget never records into the turn, the audit or the evidence: the lanes
are settled only when every read finished in time. A read that is still running keeps its pool
slot until it returns. When no slot is free, the turn is refused at once and nothing is queued.

Pure application ring: stdlib, the recorder and the domain result only (R3).
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from typing import Any

from src.application.tool_audit import RecordedCall, ToolCallRecorder
from src.domain.fanout import DEFAULT_FANOUT_BUDGET_SECONDS
from src.domain.result import Failure, Ok, Result, is_failure

UNAVAILABLE = "PROVIDER_UNAVAILABLE"
BUDGET_OBSERVED = "fan-out budget exceeded"
POOL_FULL_OBSERVED = "fan-out pool is full"

# Two reads per turn, and anyio runs at most 40 sync route handlers at once (its default thread
# limit), so at most 80 reads are in flight from the request threads. 50 operators therefore never
# find the pool full; a full pool means reads are still hung, and the turn is refused at once.
FANOUT_SLOTS = 80


class FanoutPool:
    """Worker threads for the reads, with one slot per read that is still running."""

    def __init__(self, size: int) -> None:
        self.size = size
        self._executor = ThreadPoolExecutor(max_workers=size, thread_name_prefix="m12-fanout")
        self._slots = threading.BoundedSemaphore(size)

    def claim(self, count: int) -> bool:
        """Take ``count`` slots without blocking; all or none."""
        for claimed in range(count):
            if not self._slots.acquire(blocking=False):
                for _ in range(claimed):
                    self._slots.release()
                return False
        return True

    def submit(self, call: Callable[[], Result[Any]]) -> Future[Result[Any]]:
        """Run ``call`` on a worker; the slot taken by ``claim`` comes back before it completes."""

        def run_and_release() -> Result[Any]:
            try:
                return call()
            finally:
                self._slots.release()

        return self._executor.submit(run_and_release)


SHARED_POOL = FanoutPool(FANOUT_SLOTS)


class ParallelReads:
    """Runs the reads of one turn in parallel. The recorder is required: a fan-out built without
    one would drop its audit rows silently (review of story 1.6, deferred item closed here)."""

    def __init__(
        self,
        *,
        recorder: ToolCallRecorder,
        budget_seconds: float = DEFAULT_FANOUT_BUDGET_SECONDS,
        pool: FanoutPool = SHARED_POOL,
    ) -> None:
        self._budget = budget_seconds
        self._recorder = recorder
        self._pool = pool

    def run(self, reads: Sequence[Callable[[], Result[Any]]]) -> Result[list[Any]]:
        """The values of ``reads`` in argument order, or the first failure in argument order.

        A read that raises becomes a ``PROVIDER_UNAVAILABLE`` failure (AD-12). A fan-out still
        running at the budget, or a full pool, is ``PROVIDER_UNAVAILABLE`` too. No partial
        evidence is returned, and nothing from a read that outlives the turn is recorded.
        """
        if not self._pool.claim(len(reads)):
            return Failure(UNAVAILABLE, observed=(POOL_FULL_OBSERVED,))
        lanes: list[list[RecordedCall]] = [[] for _ in reads]
        futures = [
            self._pool.submit(self._in_lane(read, lane))
            for read, lane in zip(reads, lanes, strict=True)
        ]
        finished, pending = wait(futures, timeout=self._budget)
        if pending:
            # the late reads write into their lanes, which are never settled into the turn
            return Failure(UNAVAILABLE, observed=(BUDGET_OBSERVED,))
        outcomes = [future.result() for future in futures]
        self._recorder.settle(lanes)
        for outcome in outcomes:
            if is_failure(outcome):
                return outcome
        return Ok([outcome.value for outcome in outcomes])

    def _in_lane(
        self, read: Callable[[], Result[Any]], lane: list[RecordedCall]
    ) -> Callable[[], Result[Any]]:
        return self._recorder.within(lane, _guarded(read))


def _guarded(read: Callable[[], Result[Any]]) -> Callable[[], Result[Any]]:
    def call() -> Result[Any]:
        try:
            return read()
        except Exception as exc:  # AD-12: an unexpected error is a typed failure, never a 500
            return Failure(UNAVAILABLE, observed=(f"read raised {type(exc).__name__}",))

    return call
