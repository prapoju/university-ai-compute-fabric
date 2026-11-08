"""The parallel read fan-out of one turn (story 1.6; review D-2.1 to D-2.6, log I2-35).

Independent read-only tool calls run concurrently. Each read runs in a worker thread, inside its
own recorder lane. ``run`` returns the values in argument order, so evidence positions, the audit
rows and the reported failure never depend on completion order. The budget is wall time
(``asyncio.timeout``), never a Clock-port read, so a turn still makes exactly one clock read.

Constraint: ``run`` calls ``asyncio.run``, so it must be called from a thread that has no running
event loop. The routes that reach it are sync ``def`` handlers, and a route audit test pins that.

Pure application ring: stdlib, the recorder and the domain result only (R3).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import Any

from src.application.tool_audit import RecordedCall, ToolCallRecorder
from src.domain.fanout import DEFAULT_FANOUT_BUDGET_SECONDS
from src.domain.result import Failure, Ok, Result, is_failure

UNAVAILABLE = "PROVIDER_UNAVAILABLE"
BUDGET_OBSERVED = "fan-out budget exceeded"


class ParallelReads:
    def __init__(
        self,
        *,
        budget_seconds: float = DEFAULT_FANOUT_BUDGET_SECONDS,
        recorder: ToolCallRecorder | None = None,
    ) -> None:
        self._budget = budget_seconds
        self._recorder = recorder

    def run(self, reads: Sequence[Callable[[], Result[Any]]]) -> Result[list[Any]]:
        """The values of ``reads`` in argument order, or the first failure in argument order.

        A read that raises becomes a ``PROVIDER_UNAVAILABLE`` failure (AD-12). A fan-out past the
        budget is ``PROVIDER_UNAVAILABLE`` too. No partial evidence is returned in either case.
        """
        lanes: list[list[RecordedCall]] = [[] for _ in reads]
        try:
            outcomes = asyncio.run(self._fan_out(reads, lanes))
        except TimeoutError:
            return Failure(UNAVAILABLE, observed=(BUDGET_OBSERVED,))
        finally:
            if self._recorder is not None:
                self._recorder.settle(lanes)
        for outcome in outcomes:
            if is_failure(outcome):
                return outcome
        return Ok([outcome.value for outcome in outcomes])

    async def _fan_out(
        self, reads: Sequence[Callable[[], Result[Any]]], lanes: list[list[RecordedCall]]
    ) -> list[Result[Any]]:
        async with asyncio.timeout(self._budget):
            return await asyncio.gather(
                *(
                    asyncio.to_thread(self._in_lane(read, lane))
                    for read, lane in zip(reads, lanes, strict=True)
                )
            )

    def _in_lane(
        self, read: Callable[[], Result[Any]], lane: list[RecordedCall]
    ) -> Callable[[], Result[Any]]:
        guarded = _guarded(read)
        if self._recorder is None:
            return guarded
        return self._recorder.within(lane, guarded)


def _guarded(read: Callable[[], Result[Any]]) -> Callable[[], Result[Any]]:
    def call() -> Result[Any]:
        try:
            return read()
        except Exception as exc:  # AD-12: an unexpected error is a typed failure, never a 500
            return Failure(UNAVAILABLE, observed=(f"read raised {type(exc).__name__}",))

    return call
