"""Canonical strings have a single owner and match the contract byte for byte (AD-8, D57)."""

from __future__ import annotations

import pytest

from src.adapters.inbound import errors
from src.config import PROJECT_ROOT
from src.domain import canonical_strings as cs

pytestmark = pytest.mark.unit

CONTRACT_TEXT = (PROJECT_ROOT / "planning/detailed-design/contracts.md").read_text(encoding="utf-8")
ARCHITECTURE_TEXT = (PROJECT_ROOT / "planning/ARCHITECTURE.md").read_text(encoding="utf-8")


def test_literals_are_byte_identical_to_the_contract() -> None:
    assert cs.S_ENF == "Entity Not Found in State: {ref_list}."
    assert cs.S_CNC == "Cannot confirm (insufficient evidence): checked {checked_list}."
    assert cs.S_PUA == "Provider unavailable — cannot answer."
    assert cs.S_ARF == "Action refused."
    assert cs.S_RBX == "no runbook available for code {code}."
    assert cs.S_CAP == (
        "This confirms a proposal for delegation. It does not grant or assert authorization."
    )
    assert cs.S_CLR == "Clarification required: {reason}."
    for literal in (cs.S_ENF, cs.S_CNC, cs.S_PUA, cs.S_ARF, cs.S_RBX, cs.S_CLR):
        assert literal in CONTRACT_TEXT, literal
    assert cs.S_CAP in ARCHITECTURE_TEXT


def test_the_error_envelope_reuses_the_single_owner_instead_of_a_copy() -> None:
    assert errors.S_PUA is cs.S_PUA


def test_clarification_renders_the_reason_into_the_literal() -> None:
    assert cs.clarification(cs.R_NO_INTENT) == (
        "Clarification required: no registered intent matches this query."
    )
    assert cs.clarification("x") == "Clarification required: x."


def test_reasons_are_fixed_sentences_without_a_trailing_period() -> None:
    for reason in (
        cs.R_NO_INTENT,
        cs.R_COMPOUND_DESTRUCTIVE,
        cs.R_FOLLOWUP_NO_CONTEXT,
        cs.R_MULTIPLE_INTENTS,
    ):
        assert reason and not reason.endswith(".")  # the template supplies the period
    assert cs.R_FOLLOWUP_NO_CONTEXT == "there is no earlier topic in this session to follow up on"
    assert cs.R_COMPOUND_DESTRUCTIVE == (
        "the query mixes a diagnosis with a destructive action; submit them separately"
    )
