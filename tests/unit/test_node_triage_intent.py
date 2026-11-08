"""Story 3.3 - the node-triage rule and the annex 12.6 access-denial phrasing (FR-01, AD-4)."""

from __future__ import annotations

import pytest

from src.domain import canonical_strings as cs
from src.domain.intent import Clarify, Routed, classify

pytestmark = pytest.mark.unit

S3 = "Node ws-gpu-11 is cordoned with code ERR_THERMAL_88. What should I do?"
ANNEX_12_6 = "Student Alex was denied model deepseek-coder. Diagnose and provide runbook."
S1 = "Why was student Alex denied access to model deepseek-coder?"
S2 = "Why can't group 4 run their fine-tuning job right now?"
GHOST = "Why was ghost_user_99 denied access to model deepseek-coder?"


def test_s3_routes_to_node_triage_by_its_rule() -> None:
    assert classify(S3, []) == Routed("diagnose_node_triage", "RULE-INTENT-NODE-TRIAGE")


def test_the_annex_12_6_query_routes_to_access_denial() -> None:
    assert classify(ANNEX_12_6, []) == Routed("diagnose_access_denial", "RULE-INTENT-ACCESS-DENIAL")


@pytest.mark.parametrize(
    ("query", "intent"),
    [
        (S1, "diagnose_access_denial"),
        (GHOST, "diagnose_access_denial"),
        (S2, "diagnose_schedule_window"),
    ],
)
def test_the_mandatory_queries_keep_their_routes(query: str, intent: str) -> None:
    assert classify(query, []).intent_code == intent  # type: ignore[union-attr]


def test_a_node_question_that_also_asks_for_a_cordon_is_never_split() -> None:
    query = "Node ws-gpu-11 is cordoned with code ERR_THERMAL_88. Cordon it now."
    assert classify(query, []) == Clarify(cs.R_COMPOUND_DESTRUCTIVE)


def test_a_cordon_request_without_a_node_question_is_not_a_triage() -> None:
    routed = classify("cordon ws-gpu-11 now", [])
    assert not (isinstance(routed, Routed) and routed.intent_code == "diagnose_node_triage")


@pytest.mark.parametrize(
    ("query", "intent", "rule"),
    [
        # NFR-1 corpus misses, fixed in story 3.3 scope (smallest rule change)
        (
            "ws-gpu-11 cordoned ERR_THERMAL_88, what do I do?",
            "diagnose_node_triage",
            "RULE-INTENT-NODE-TRIAGE",
        ),
        (
            "What should I do about node ws-gpu-11 cordoned with ERR_THERMAL_88?",
            "diagnose_node_triage",
            "RULE-INTENT-NODE-TRIAGE",
        ),
        (
            "why cant group 4 run their fine-tuning job now",
            "diagnose_schedule_window",
            "RULE-INTENT-SCHEDULE-WINDOW",
        ),
    ],
)
def test_the_corpus_phrasings_route_to_their_intent(query: str, intent: str, rule: str) -> None:
    assert classify(query, []) == Routed(intent, rule)


def test_a_cordoned_node_with_no_error_code_is_not_a_node_triage() -> None:
    assert classify("why was ws-gpu-11 cordoned?", []) != Routed(
        "diagnose_node_triage", "RULE-INTENT-NODE-TRIAGE"
    )
