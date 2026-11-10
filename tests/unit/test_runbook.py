"""Story 3.3 - pure node triage and runbook rendering (Annex 12.6, AD-9)."""

from __future__ import annotations

import pytest

from src.domain.references import asks_for_runbook, extract_node_triage_references
from src.domain.runbook import (
    NODE_TRIAGE_CLASS,
    diagnose_node_triage,
    is_renderable,
    runbook_miss,
    runbook_recommendation,
)
from src.dto import NodeRecordDTO, RunbookTemplateDTO

pytestmark = pytest.mark.unit

CODE = "ERR_THERMAL_88"


def node(**changes: object) -> NodeRecordDTO:
    base = {
        "id": "node#ws-gpu-11",
        "hostname": "ws-gpu-11",
        "gpu_memory_gb": 24,
        "status": "fault",
        "cordoned": True,
        "error_code": CODE,
        "health": "fault",
    }
    return NodeRecordDTO(**{**base, **changes})


def template(**changes: object) -> RunbookTemplateDTO:
    base = {
        "template_id": "rb-err-thermal-88",
        "error_code": CODE,
        "steps": ["first step", "second step", "third step"],
        "required_tools": ["torx screwdriver"],
        "safety_warnings": ["Power the node down and unplug it before opening the chassis."],
        "physical_intervention": True,
        "approved_source": "Lab Safety SOP-THERM-01",
        "version": "1.0",
    }
    return RunbookTemplateDTO(**{**base, **changes})


# -- P1 / P2: the node must be cordoned and must report the queried code ----------------------
def test_a_cordoned_node_reporting_the_queried_code_may_be_triaged() -> None:
    assert runbook_miss(node(), CODE) is None


@pytest.mark.parametrize(
    ("record", "queried", "named"),
    [
        (node(cordoned=False), CODE, CODE),  # not cordoned (P1): the recorded code is named
        (node(error_code="ERR_OTHER_01"), CODE, "ERR_OTHER_01"),  # mismatch (P2)
        (node(error_code=None), CODE, "null"),  # no code recorded: the text null is named
    ],
)
def test_a_miss_names_the_code_the_node_reports(
    record: NodeRecordDTO, queried: str, named: str
) -> None:
    assert runbook_miss(record, queried) == named


# -- verbatim rendering (AD-9, 100 % step-match) ---------------------------------------------
def test_the_steps_are_the_template_steps_in_template_order() -> None:
    steps = ["zeta", "alpha", "mu"]  # not sorted: order is the template's, never re-derived
    result = diagnose_node_triage(node(), template(steps=steps))
    assert result.recommendation["runbook"]["steps"] == steps


def test_tools_safety_and_provenance_are_rendered_as_separate_sections() -> None:
    recommendation = runbook_recommendation(template())
    assert recommendation == {
        "runbook": {
            "steps": ["first step", "second step", "third step"],
            "required_tools": ["torx screwdriver"],
            "safety_warnings": ["Power the node down and unplug it before opening the chassis."],
            "provenance": {"source": "Lab Safety SOP-THERM-01", "version": "1.0"},
        }
    }


def test_the_diagnosis_is_node_triage_with_one_claim_citing_the_node() -> None:
    result = diagnose_node_triage(node(), template())
    assert result.diagnosis_class == NODE_TRIAGE_CLASS
    assert [e.citation_id for e in result.evidence] == ["node#ws-gpu-11"]
    assert [e.position for e in result.evidence] == [0]
    (claim,) = result.claims
    assert claim.citations == ("node#ws-gpu-11",)


def test_the_node_and_template_ids_are_fact_tokens_for_the_prose_guard() -> None:
    result = diagnose_node_triage(node(), template())
    assert {"node#ws-gpu-11", "ws-gpu-11", "err_thermal_88", "rb-err-thermal-88"} <= (
        result.fact_tokens
    )


# -- the physical-intervention source guard (AD-9, D44) --------------------------------------
def test_a_physical_template_without_an_approved_source_is_not_renderable() -> None:
    assert is_renderable(template(approved_source=None)) is False


def test_a_physical_template_with_a_source_is_renderable() -> None:
    assert is_renderable(template()) is True


def test_a_non_physical_template_is_renderable_without_a_source() -> None:
    assert is_renderable(template(physical_intervention=False, approved_source=None)) is True


# -- extraction of the S3 question ------------------------------------------------------------
def test_the_s3_question_yields_the_node_and_the_code_as_typed() -> None:
    query = "Node ws-gpu-11 is cordoned with code ERR_THERMAL_88. What should I do?"
    refs = extract_node_triage_references(query)
    assert refs is not None
    assert (refs.node, refs.code) == ("ws-gpu-11", "ERR_THERMAL_88")


@pytest.mark.parametrize(
    "query",
    [
        # NFR-1 corpus (story 3.3 scope): no word "node", and the code follows "cordoned with"
        "ws-gpu-11 cordoned ERR_THERMAL_88, what do I do?",
        "What should I do about node ws-gpu-11 cordoned with ERR_THERMAL_88?",
    ],
)
def test_a_bare_node_id_and_a_code_without_its_word_are_extracted(query: str) -> None:
    refs = extract_node_triage_references(query)
    assert refs is not None
    assert (refs.node, refs.code) == ("ws-gpu-11", "ERR_THERMAL_88")


@pytest.mark.parametrize(
    "query",
    [
        "What about the node is cordoned with code ERR_THERMAL_88?",
        "The node was cordoned with code ERR_THERMAL_88, what now?",
        "node cordoned with code ERR_THERMAL_88 what should I do",
        "Why is the node cordoned with code ERR_THERMAL_88?",
    ],
)
def test_a_word_after_node_that_is_not_an_id_names_no_node(query: str) -> None:
    assert extract_node_triage_references(query) is None


def test_a_typed_node_id_and_a_question_without_a_code_are_handled() -> None:
    refs = extract_node_triage_references("node#ws-gpu-11 is cordoned with code ERR_X")
    assert refs is not None and refs.node == "ws-gpu-11"
    assert extract_node_triage_references("Node ws-gpu-11 is cordoned") is None


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Student Alex was denied model deepseek-coder. Diagnose and provide runbook.", True),
        ("Node ws-gpu-11 is cordoned with code ERR_THERMAL_88. Show the RUNBOOK.", True),
        ("Why was student Alex denied access to model deepseek-coder?", False),
    ],
)
def test_the_runbook_word_is_detected_case_insensitively(query: str, expected: bool) -> None:
    assert asks_for_runbook(query) is expected
