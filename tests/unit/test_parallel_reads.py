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


def test_results_come_back_in_argument_order_whatever_the_completion_order() -> None:
    second_done = threading.Event()

    def first():
        second_done.wait(WAIT)  # the first argument finishes last
        return Ok("first")

    def second():
        second_done.set()
        return Ok("second")

    reads = ParallelReads(budget_seconds=5.0, pool=FanoutPool(2))  # cannot expire before the gate
    assert reads.run((first, second)) == Ok(["first", "second"])


def test_the_first_failure_in_argument_order_is_the_one_reported() -> None:
    second_done = threading.Event()

    def first():
        second_done.wait(WAIT)
        return Failure("PROVIDER_UNAVAILABLE", observed=("first",))

    def second():
        second_done.set()
        return Failure("PROVIDER_UNAVAILABLE", observed=("second",))

    reads = ParallelReads(budget_seconds=5.0, pool=FanoutPool(2))  # cannot expire before the gate
    assert reads.run((first, second)) == Failure("PROVIDER_UNAVAILABLE", observed=("first",))


def test_a_read_that_raises_is_a_typed_failure_not_an_exception() -> None:
    def boom():
        raise RuntimeError("provider exploded")

    reads = ParallelReads(budget_seconds=WAIT, pool=FanoutPool(2))
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

    outcome = ParallelReads(budget_seconds=WAIT, pool=pool).run((read("a"), read("b")))
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
