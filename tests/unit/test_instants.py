"""``Instant`` parsing/formatting is pure and never reads the wall clock (R1/R2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.domain.instants import add_seconds, format_instant, parse_instant

pytestmark = pytest.mark.unit


def test_parses_with_and_without_milliseconds_to_the_same_instant() -> None:
    assert parse_instant("2026-10-16T15:00:00Z") == parse_instant("2026-10-16T15:00:00.000Z")
    assert parse_instant("2026-10-16T15:00:00.250Z") > parse_instant("2026-10-16T15:00:00Z")


def test_formats_with_millisecond_precision_in_utc() -> None:
    value = datetime(2026, 10, 16, 15, 0, tzinfo=UTC)
    assert format_instant(value) == "2026-10-16T15:00:00.000Z"
    assert format_instant(value + timedelta(milliseconds=7)) == "2026-10-16T15:00:00.007Z"


@pytest.mark.parametrize(
    "bad", ["", "2026-10-16", "2026-10-16 15:00:00", "2026-10-16T15:00:00+01:00"]
)
def test_rejects_anything_that_is_not_a_utc_instant(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_instant(bad)


def test_add_seconds_round_trips() -> None:
    assert add_seconds("2026-10-16T15:00:00.000Z", 90) == "2026-10-16T15:01:30.000Z"
