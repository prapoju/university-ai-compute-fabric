"""`fake_clock` — OP-10 `clock_port` conformance and determinism (AD-2, DP-5)."""

from __future__ import annotations

import pytest

from support.clock import INSTANT_RE, READ_ID_RE, FakeClock, parse_instant

pytestmark = pytest.mark.unit


def test_now_returns_op10_clock_read(fake_clock: FakeClock) -> None:
    read = fake_clock.now()
    assert read.source == "clock"                      # OP-10 Distinct Q
    assert READ_ID_RE.match(read.read_id)              # ^clk-[0-9a-f]{16}$
    assert INSTANT_RE.match(read.instant)              # §0.1 Instant
    assert read.as_dict().keys() == {"read_id", "instant", "source"}


def test_citation_id_is_clock_hash_read_id(fake_clock: FakeClock) -> None:
    read = fake_clock.now()
    assert read.citation_id == f"clock#{read.read_id}"  # §0.1 ClockRead


def test_advance_moves_time_forward_without_sleeping(fake_clock: FakeClock) -> None:
    before = parse_instant(fake_clock.current)
    after = parse_instant(fake_clock.advance(minutes=31))
    assert (after - before).total_seconds() == 31 * 60


def test_read_ids_are_unique_and_monotonic(fake_clock: FakeClock) -> None:
    reads = [fake_clock.now() for _ in range(5)]
    ids = [r.read_id for r in reads]
    assert len(set(ids)) == 5
    assert ids == sorted(ids)
    assert fake_clock.issued == 5


def test_two_fresh_clocks_are_reproducible() -> None:
    a, b = FakeClock(), FakeClock()
    assert [a.now().read_id for _ in range(3)] == [b.now().read_id for _ in range(3)]


def test_clock_only_moves_forward(fake_clock: FakeClock) -> None:
    with pytest.raises(ValueError):
        fake_clock.advance(minutes=-1)
    with pytest.raises(ValueError):
        fake_clock.advance_to("2020-01-01T00:00:00.000Z")
