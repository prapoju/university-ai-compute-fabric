"""The typed error catalog (contracts.md section 4) as data: status, retryability, message."""

from __future__ import annotations

from typing import get_args

import pytest

from src.domain.error_catalog import CATALOG, fail, render, spec_for
from src.domain.result import Failure
from src.dto import ErrorCode

pytestmark = pytest.mark.unit


def test_the_catalog_covers_exactly_the_error_codes_of_the_dto_module() -> None:
    assert set(CATALOG) == set(get_args(ErrorCode))


@pytest.mark.parametrize(
    ("code", "status", "retryable"),
    [
        ("VALIDATION_EMPTY_QUERY", 400, False),
        ("VALIDATION_QUERY_TOO_LONG", 400, False),
        ("VALIDATION_MALFORMED_BODY", 400, False),
        ("PAGINATION_INVALID", 400, False),
        ("SESSION_NOT_FOUND", 404, False),
        ("SESSION_EXPIRED", 410, False),
        ("ENTITY_NOT_FOUND", 404, False),
        ("CLARIFICATION_REQUIRED", 200, False),
        ("INTENT_NOT_SUPPORTED", 200, False),
        ("ACTION_REFUSED", 200, False),
        ("PROVIDER_UNAVAILABLE", 503, True),
        ("CLOCK_UNAVAILABLE", 503, True),
        ("AUDIT_WRITE_FAILED", 500, True),
        ("PROPOSAL_STATE_INVALID", 409, False),
        ("GATE_TOKEN_INVALID", 403, False),
        ("EXECUTOR_PARTIAL_APPLY", 502, False),
        ("RUNBOOK_TEMPLATE_EMPTY", 422, False),
    ],
)
def test_status_and_retryability_match_the_contract_table(
    code: str, status: int, retryable: bool
) -> None:
    spec = spec_for(code)
    assert (spec.status, spec.retryable) == (status, retryable)


def test_render_fills_the_contract_message_templates() -> None:
    assert render("SESSION_NOT_FOUND", sid="sess-00000000000000ff") == (
        "Session sess-00000000000000ff not found."
    )
    assert (
        render("SESSION_EXPIRED", sid="sess-1") == "Session sess-1 expired after 30 minutes idle."
    )
    assert render("VALIDATION_QUERY_TOO_LONG", n=1001) == (
        "Query exceeds 1000 characters; received 1001."
    )
    assert render("VALIDATION_EMPTY_QUERY") == (
        "Query must contain between 1 and 1000 characters; received 0."
    )
    assert render("PROVIDER_UNAVAILABLE") == "Provider unavailable — cannot answer."
    assert render("CLARIFICATION_REQUIRED", reason="r") == "Clarification required: r."


def test_every_provider_failure_shares_the_safe_failure_literal() -> None:
    literal = "Provider unavailable — cannot answer."
    for code in ("PROVIDER_UNAVAILABLE", "CLOCK_UNAVAILABLE", "LLM_UNAVAILABLE",
                 "LLM_PROSE_REJECTED", "EXECUTOR_UNAVAILABLE"):  # fmt: skip
        assert render(code) == literal


def test_a_missing_template_parameter_is_a_clear_error_not_a_silent_blank() -> None:
    with pytest.raises(ValueError, match="sid"):
        render("SESSION_NOT_FOUND")


def test_fail_builds_a_failure_that_already_carries_its_message() -> None:
    failure = fail("SESSION_NOT_FOUND", sid="sess-00000000000000ff")
    assert isinstance(failure, Failure)
    assert failure.code == "SESSION_NOT_FOUND"
    assert failure.message == "Session sess-00000000000000ff not found."


def test_a_failure_still_works_without_a_message_for_adapters_that_do_not_care() -> None:
    assert Failure("PROVIDER_UNAVAILABLE").message is None
