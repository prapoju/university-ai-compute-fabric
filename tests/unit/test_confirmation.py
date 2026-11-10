"""Story 2.3 - the pure confirmation rules: lifetime, token, something to confirm, the delta."""

from __future__ import annotations

import pytest

from src.domain.confirmation import (
    STALE_LAST_LINE,
    Delta,
    delta_lines,
    delta_text,
    diff,
    elapsed_seconds,
    expired_delta,
    has_actionable,
    token_is_fresh,
    tokens_match,
)
from src.dto import AffectedItemDTO

pytestmark = pytest.mark.unit

T0 = "2026-10-16T15:00:00.000Z"


def item(n: int, value: str = "running", actionable: bool = True) -> AffectedItemDTO:
    return AffectedItemDTO(
        key=f"job#job-{n}", actionable=actionable, actionable_field="status", actionable_value=value
    )


# -- the lifetime is on the clock instant, with `<=` ------------------------------------------
@pytest.mark.parametrize(
    ("now", "ttl", "fresh"),
    [
        ("2026-10-16T15:00:00.000Z", 60, True),  # the same instant
        ("2026-10-16T15:00:59.999Z", 60, True),
        ("2026-10-16T15:01:00.000Z", 60, True),  # the boundary is accepted
        ("2026-10-16T15:01:00.001Z", 60, False),  # one millisecond late
        ("2026-10-16T15:00:05.000Z", 5, True),
        ("2026-10-16T15:00:05.001Z", 5, False),
        ("2026-10-16T15:02:00.000Z", 60, False),
        ("2026-10-16T14:59:59.000Z", 60, True),  # a clock that went back is not an expiry
    ],
)
def test_the_token_is_fresh_up_to_and_including_the_lifetime(
    now: str, ttl: int, fresh: bool
) -> None:
    assert token_is_fresh(T0, now, ttl) is fresh


def test_the_elapsed_time_and_the_expired_text_are_exact() -> None:
    assert elapsed_seconds(T0, "2026-10-16T15:01:00.001Z") == 60.001
    assert expired_delta(T0, "2026-10-16T15:01:00.001Z", 60) == (
        "token expired: 60.001 s after the snapshot, lifetime 60 s"
    )
    assert expired_delta(T0, "2026-10-16T15:00:06.000Z", 5) == (
        "token expired: 6.000 s after the snapshot, lifetime 5 s"
    )


# -- the token --------------------------------------------------------------------------------
def test_tokens_match_only_when_equal() -> None:
    token = "gt-" + "ab" * 16
    assert tokens_match(token, token)
    assert not tokens_match("gt-" + "ab" * 15 + "ac", token)  # one character off
    assert not tokens_match(token[:-1], token)  # shorter
    assert not tokens_match(token + "0", token)  # longer
    assert not tokens_match("", token)
    assert tokens_match("gt-é", "gt-é")  # a non-ASCII value never raises


# -- something to confirm -----------------------------------------------------------------------
def test_something_to_confirm_needs_one_actionable_item() -> None:
    assert has_actionable([item(1)])
    assert has_actionable([item(1, "cancelled", False), item(2)])
    assert not has_actionable([])
    assert not has_actionable([item(1, "cancelled", False), item(2, "succeeded", False)])


# -- the delta -----------------------------------------------------------------------------------
def test_an_identical_set_has_an_empty_delta_whatever_its_order() -> None:
    delta = diff([item(1), item(2)], [item(2), item(1)])
    assert delta == Delta() and delta.empty
    assert delta_lines(delta) == [] and delta_text(delta) == ""
    assert diff([], []).empty


def test_each_kind_of_difference_is_found_and_named() -> None:
    stored = [item(1), item(2), item(3)]
    current = [item(2, "succeeded"), item(3), item(4)]
    delta = diff(stored, current)
    assert [i.key for i in delta.added] == ["job#job-4"]
    assert [i.key for i in delta.removed] == ["job#job-1"]
    assert [(a.key, b.actionable_value) for a, b in delta.changed] == [("job#job-2", "succeeded")]
    assert not delta.empty
    assert delta_lines(delta) == [
        "added job#job-4",
        "removed job#job-1",
        "job#job-2 running -> succeeded",
    ]
    assert delta_text(delta) == "added job#job-4; removed job#job-1; job#job-2 running -> succeeded"


def test_a_change_of_the_actionable_flag_alone_is_a_change() -> None:
    delta = diff([item(1, "running", True)], [item(1, "running", False)])
    assert delta_lines(delta) == ["job#job-1 actionable True -> False"]


def test_the_lines_of_every_kind_are_ordered_by_key() -> None:
    delta = diff([item(9), item(2)], [item(5), item(7)])
    assert delta_lines(delta) == [
        "added job#job-5",
        "added job#job-7",
        "removed job#job-2",
        "removed job#job-9",
    ]


def test_a_changed_field_name_is_a_change_too() -> None:
    other = AffectedItemDTO(
        key="job#job-1", actionable=True, actionable_field="state", actionable_value="running"
    )
    assert not diff([item(1)], [other]).empty


def test_the_last_line_of_a_stale_answer_says_confirmation_is_disabled() -> None:
    assert STALE_LAST_LINE == "confirmation disabled: run a new dry-run"
