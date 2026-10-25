"""Pure session rules: query normalisation, idle expiry, empty context (FR-01, D51)."""

from __future__ import annotations

import pytest

from src.domain.result import Failure, Ok
from src.domain.session_rules import (
    IDLE_LIMIT_MINUTES,
    MAX_QUERY_CHARS,
    empty_context,
    is_idle_expired,
    is_valid_operator_role,
    normalise_query,
)

pytestmark = pytest.mark.unit


def test_the_limits_are_the_contract_values() -> None:
    assert MAX_QUERY_CHARS == 1000 and IDLE_LIMIT_MINUTES == 30


def test_the_query_is_trimmed_once_and_returned_trimmed() -> None:
    assert normalise_query("  why was alex denied?  \n") == Ok("why was alex denied?")


@pytest.mark.parametrize("text", ["", "   ", "\n\t  \n"])
def test_empty_after_trimming_is_validation_empty_query(text: str) -> None:
    result = normalise_query(text)
    assert isinstance(result, Failure) and result.code == "VALIDATION_EMPTY_QUERY"
    assert result.message == "Query must contain between 1 and 1000 characters; received 0."


def test_the_boundary_is_1000_accepted_and_1001_rejected() -> None:
    assert normalise_query("a" * 1000) == Ok("a" * 1000)
    over = normalise_query("a" * 1001)
    assert isinstance(over, Failure) and over.code == "VALIDATION_QUERY_TOO_LONG"
    assert over.message == "Query exceeds 1000 characters; received 1001."


def test_the_length_test_runs_on_the_trimmed_value_not_the_raw_input() -> None:
    padded = "   " + "a" * 1000 + "   "  # 1006 raw characters, 1000 after trimming
    assert normalise_query(padded) == Ok("a" * 1000)


def test_idle_expiry_is_strictly_greater_than_30_minutes() -> None:
    last = "2026-10-16T15:00:00.000Z"
    assert not is_idle_expired(last, "2026-10-16T15:30:00.000Z")  # exactly 30 min
    assert is_idle_expired(last, "2026-10-16T15:30:00.001Z")
    assert is_idle_expired(last, "2026-10-16T15:31:00.000Z")
    assert not is_idle_expired(last, "2026-10-16T15:00:00.000Z")


def test_idle_expiry_handles_instants_with_and_without_milliseconds() -> None:
    assert not is_idle_expired("2026-10-16T15:00:00Z", "2026-10-16T15:30:00.000Z")
    assert is_idle_expired("2026-10-16T15:00:00.000Z", "2026-10-16T15:30:01Z")


def test_the_empty_context_is_a_fresh_object_each_time() -> None:
    first, second = empty_context(), empty_context()
    assert first.model_dump() == {
        "resolved_entities": [],
        "prior_intents": [],
        "active_answer_ids": [],
    }
    first.prior_intents.append("x")
    assert second.prior_intents == []


@pytest.mark.parametrize("role", ["role-operations", "role-a", "role-" + "x" * 32, "role-a_b-c1"])
def test_valid_operator_roles(role: str) -> None:
    assert is_valid_operator_role(role)


@pytest.mark.parametrize(
    "role",
    ["admin", "role-", "role-UPPER", "role-" + "x" * 33, "", "role-a b", "ROLE-a", "role-a\n"],
)
def test_invalid_operator_roles(role: str) -> None:
    assert not is_valid_operator_role(role)
