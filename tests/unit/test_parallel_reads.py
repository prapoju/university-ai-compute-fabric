"""Story 1.6 task 3.5 and the fan-out contract: order, failures, budget, pool and late reads.

Only ``threading.Event`` gates and bounded waits are used; no sleep and no timing assertion.
"""

from __future__ import annotations

import threading

import pytest

from src.application.parallel_reads import FanoutPool, ParallelReads
from src.application.tool_audit import RecordedCall, ToolCallRecorder
from src.domain.result import Failure, Ok

pytestmark = pytest.mark.unit

WAIT = 2.0  # an upper bound on every gate, so a broken gate fails instead of hanging
BUDGET_FAILURE = Failure("PROVIDER_UNAVAILABLE", observed=("fan-out budget exceeded",))
POOL_FAILURE = Failure("PROVIDER_UNAVAILABLE", observed=("fan-out pool is full",))


def test_a_fan_out_cannot_be_built_without_its_recorder() -> None:
    """Without a recorder the reads' audit rows would be dropped silently, so it is refused."""
    with pytest.raises(TypeError):
        ParallelReads(budget_seconds=WAIT, pool=FanoutPool(2))  # type: ignore[call-arg]


def test_results_come_back_in_argument_order_whatever_the_completion_order() -> None:
    second_done = threading.Event()
    gate_opened: list[bool] = []

    def first():
        gate_opened.append(second_done.wait(WAIT))  # the first argument finishes last
        return Ok("first")

    def second():
        second_done.set()
        return Ok("second")

    # cannot expire before the gate
    reads = ParallelReads(budget_seconds=5.0, recorder=ToolCallRecorder(), pool=FanoutPool(2))
    assert reads.run((first, second)) == Ok(["first", "second"])
    assert gate_opened == [True], "the second read did not run while the first was waiting"


def test_the_first_failure_in_argument_order_is_the_one_reported() -> None:
    second_done = threading.Event()
    gate_opened: list[bool] = []

    def first():
        gate_opened.append(second_done.wait(WAIT))
        return Failure("PROVIDER_UNAVAILABLE", observed=("first",))

    def second():
        second_done.set()
        return Failure("PROVIDER_UNAVAILABLE", observed=("second",))

    # cannot expire before the gate
    reads = ParallelReads(budget_seconds=5.0, recorder=ToolCallRecorder(), pool=FanoutPool(2))
    assert reads.run((first, second)) == Failure("PROVIDER_UNAVAILABLE", observed=("first",))
    assert gate_opened == [True], "the second read did not run while the first was waiting"


def test_a_read_that_raises_is_a_typed_failure_not_an_exception() -> None:
    def boom():
        raise RuntimeError("provider exploded")

    reads = ParallelReads(budget_seconds=WAIT, recorder=ToolCallRecorder(), pool=FanoutPool(2))
    outcome = reads.run((boom, lambda: Ok("fine")))
    assert outcome == Failure("PROVIDER_UNAVAILABLE", observed=("read raised RuntimeError",))


def test_a_full_pool_refuses_the_turn_without_calling_any_read() -> None:
    pool = FanoutPool(1)
    assert pool.claim(1)  # somebody else holds the only slot
    calls: list[str] = []

    def read(name):
        def call():
            calls.append(name)
            return Ok(name)

        return call

    reads = ParallelReads(budget_seconds=WAIT, recorder=ToolCallRecorder(), pool=pool)
    outcome = reads.run((read("a"), read("b")))
    assert outcome == POOL_FAILURE
    assert calls == [], "a refused turn must not start any read"


def test_one_slow_read_of_two_is_a_503_at_the_budget_and_its_late_result_is_dropped() -> None:
    """Task 3.5. The slow read records a tool call after the budget; the turn must not see it."""
    recorder = ToolCallRecorder()
    release = threading.Event()
    finished = threading.Event()

    def fast():
        return Ok("fast")

    def slow():
        release.wait(WAIT)
        recorder.record(RecordedCall("toolcall.slow", {}, "ok"))
        finished.set()
        return Ok("slow")

    reads = ParallelReads(budget_seconds=0.05, recorder=recorder, pool=FanoutPool(4))
    with recorder.turn() as calls:
        outcome = reads.run((fast, slow))
        assert outcome == BUDGET_FAILURE
        assert not finished.is_set(), "the 503 arrived only after the slow read had returned"
        release.set()
        assert finished.wait(WAIT), "the slow read never finished"
    assert calls == [], "a read that outlived the budget recorded into the turn"


def test_a_slot_comes_back_before_its_read_completes() -> None:
    """The slot of a read that outlived the budget is free again once the read has returned."""
    pool = FanoutPool(1)
    release = threading.Event()

    def slow():
        release.wait(WAIT)
        return Ok("late")

    assert pool.claim(1)
    future = pool.submit(slow)  # takes over the claimed slot
    assert not pool.claim(1), "the running read must hold its slot"
    release.set()
    future.result(timeout=WAIT)  # the slot is released before the future completes
    assert pool.claim(1), "the slot did not come back after the read returned"


class _SecondCompletesFirst(FanoutPool):
    """Sets ``second_completed`` when the second submitted call's future is done.

    The callback is added before ParallelReads adds its own, so the flag is set before any
    completion bookkeeping of the second read runs.
    """

    def __init__(self) -> None:
        super().__init__(2)
        self.second_completed = threading.Event()
        self._submitted = 0

    def submit(self, call):
        future = super().submit(call)
        if self._submitted == 1:
            future.add_done_callback(lambda _finished: self.second_completed.set())
        self._submitted += 1
        return future


def test_recorded_calls_settle_in_argument_order_when_the_second_read_finishes_first() -> None:
    """Settling the lanes in completion order would put the second read's call first."""
    recorder = ToolCallRecorder()
    pool = _SecondCompletesFirst()
    gate_opened: list[bool] = []

    def first():
        gate_opened.append(pool.second_completed.wait(WAIT))  # the first finishes after the second
        recorder.record(RecordedCall("toolcall.first", {}, "ok"))
        return Ok("first")

    def second():
        recorder.record(RecordedCall("toolcall.second", {}, "ok"))
        return Ok("second")

    reads = ParallelReads(budget_seconds=5.0, recorder=recorder, pool=pool)
    with recorder.turn() as calls:
        assert reads.run((first, second)) == Ok(["first", "second"])
    assert gate_opened == [True], "the second read did not complete while the first was waiting"
    assert [call.tool_name for call in calls] == ["toolcall.first", "toolcall.second"]
