"""Typed ok | failure results (AD-12): a failure never carries partial data."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.domain.result import Failure, Ok, is_failure, is_ok

pytestmark = pytest.mark.unit


def test_ok_wraps_a_value_including_none_for_a_miss() -> None:
    assert is_ok(Ok(42)) and not is_failure(Ok(42))
    miss = Ok(None)  # Q-port-1: a single-record miss is Ok(None), not a failure
    assert is_ok(miss) and miss.value is None


def test_failure_carries_a_catalog_code_and_the_observed_reason() -> None:
    failure = Failure("PROVIDER_UNAVAILABLE", observed=("fixtures/nodes.json missing",))
    assert is_failure(failure) and not is_ok(failure)
    assert failure.code == "PROVIDER_UNAVAILABLE"
    assert failure.observed == ("fixtures/nodes.json missing",)


def test_failure_rejects_a_code_outside_the_typed_error_catalog() -> None:
    with pytest.raises(ValueError, match="MADE_UP"):
        Failure("MADE_UP")


def test_results_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        Ok(1).value = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        Failure("PROVIDER_UNAVAILABLE").code = "CLOCK_UNAVAILABLE"  # type: ignore[misc]
