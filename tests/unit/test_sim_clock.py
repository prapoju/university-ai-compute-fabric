"""The simulated clock adapter implements OP-10 deterministically (AD-2, DP-5)."""

from __future__ import annotations

import re

import pytest

from src.adapters.outbound.sim.clock_adapter import SimClock
from src.domain.result import Failure, is_ok

pytestmark = pytest.mark.unit

START = "2026-10-16T15:00:00.000Z"


def _now(clock: SimClock):
    result = clock.now()
    assert is_ok(result), result
    return result.value


def test_reads_carry_the_frozen_instant_a_unique_id_and_source_clock() -> None:
    clock = SimClock(START)
    first, second = _now(clock), _now(clock)
    assert first.instant == second.instant == START
    assert first.source == "clock"
    assert re.fullmatch(r"clk-[0-9a-f]{16}", first.read_id)
    assert first.read_id != second.read_id


def test_two_clocks_with_the_same_start_issue_the_same_sequence() -> None:
    a, b = SimClock(START), SimClock(START)
    assert [_now(a).read_id for _ in range(3)] == [_now(b).read_id for _ in range(3)]


def test_advance_moves_time_forward_only() -> None:
    clock = SimClock(START)
    clock.advance(hours=7)
    assert _now(clock).instant == "2026-10-16T22:00:00.000Z"
    with pytest.raises(ValueError):
        clock.advance(seconds=-1)
    with pytest.raises(ValueError):
        clock.set("2026-10-16T10:00:00.000Z")


def test_set_pins_the_scenario_time() -> None:
    clock = SimClock(START)
    clock.set("2026-10-17T03:30:00.000Z")
    assert _now(clock).instant == "2026-10-17T03:30:00.000Z"


def test_an_injected_failure_is_clock_unavailable_then_recovers() -> None:
    clock = SimClock(START)
    clock.fail()
    result = clock.now()
    assert isinstance(result, Failure) and result.code == "CLOCK_UNAVAILABLE"
    clock.recover()
    assert is_ok(clock.now())


def test_a_malformed_start_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError):
        SimClock("noon")
