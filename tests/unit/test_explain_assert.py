"""`explain_assert` — a decision must cite a rule, its observed values, and citations."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from support.explain import Explanation, coerce_explanation

pytestmark = pytest.mark.unit


@dataclass
class _Evidence:
    citation_id: str
    source_type: str = "node"


@dataclass
class _Claim:
    claim_id: str
    text: str
    claim_citations: list[str]


@dataclass
class _Diagnosis:
    diagnosis_class: str
    observed: dict = field(default_factory=dict)
    claims: list = field(default_factory=list)
    evidence: list = field(default_factory=list)


def test_mapping_decision_passes(explain_assert) -> None:
    decision = {
        "matched_rule_id": "rule.access_denial.allowlist",
        "observed": {"job_status": "cancelled", "reason_class": "not-in-allowlist"},
        "citations": ["policy#catalog.4.2", "job#job-8823"],
    }
    explanation = explain_assert(
        decision,
        rule_id="rule.access_denial.allowlist",
        values={"job_status": "cancelled"},
        min_citations=2,
    )
    assert isinstance(explanation, Explanation)
    assert explanation.rule_ids == ("rule.access_denial.allowlist",)


def test_nested_intent_rule_is_found(explain_assert) -> None:
    decision = {
        "intent": {"intent_code": "diagnose_node_triage", "matched_rule_id": "rule.node_triage"},
        "observed": {"error_code": "ERR_THERMAL_88"},
        "claim_citations": ["node#ws-gpu-11"],
    }
    explain_assert(decision, rule_id="rule.node_triage", values={"error_code": "ERR_THERMAL_88"})


def test_dataclass_decision_passes(explain_assert) -> None:
    decision = _Diagnosis(
        diagnosis_class="node_triage_runbook",
        observed={"error_code": "ERR_THERMAL_88"},
        claims=[_Claim("clm-0", "Node ws-gpu-11 is cordoned.", ["node#ws-gpu-11"])],
        evidence=[_Evidence("node#ws-gpu-11"), _Evidence("clock#clk-0000000000000001")],
    )
    explanation = explain_assert(
        decision,
        rule_id="node_triage_runbook",
        values={"error_code": "ERR_THERMAL_88"},
        min_citations=1,
    )
    assert set(explanation.citations) >= {"node#ws-gpu-11", "clock#clk-0000000000000001"}


def test_missing_rule_fails(explain_assert) -> None:
    with pytest.raises(AssertionError, match="no rule id"):
        explain_assert({"observed": {}, "citations": ["node#ws-gpu-11"]})


def test_wrong_rule_fails(explain_assert) -> None:
    decision = {"matched_rule_id": "rule.a", "citations": ["node#ws-gpu-11"]}
    with pytest.raises(AssertionError, match="expected rule_id"):
        explain_assert(decision, rule_id="rule.b")


def test_missing_observed_value_fails(explain_assert) -> None:
    decision = {"matched_rule_id": "rule.a", "observed": {"x": 1}, "citations": ["node#ws-gpu-11"]}
    with pytest.raises(AssertionError, match="no observed value"):
        explain_assert(decision, values={"y": 2})


def test_observed_mismatch_fails(explain_assert) -> None:
    decision = {"matched_rule_id": "rule.a", "observed": {"x": 1}, "citations": ["node#ws-gpu-11"]}
    with pytest.raises(AssertionError, match="expected"):
        explain_assert(decision, values={"x": 2})


def test_missing_citation_fails(explain_assert) -> None:
    decision = {"matched_rule_id": "rule.a", "observed": {"x": 1}}
    with pytest.raises(AssertionError, match="citation"):
        explain_assert(decision)


def test_citations_optional(explain_assert) -> None:
    decision = {"matched_rule_id": "rule.a", "observed": {"x": 1}}
    explain_assert(decision, require_citations=False)


def test_coerce_is_order_preserving_and_dedupes() -> None:
    explanation = coerce_explanation(
        {"rule_ids": ["r1", "r1", "r2"], "citations": ["c", "c"]}
    )
    assert explanation.rule_ids == ("r1", "r2")
    assert explanation.citations == ("c",)
