"""Story 3.3 - the node-triage diagnoser served through the real composition root (Annex 12.6)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import Settings
from src.dto import ErrorBody, SubmitQueryResponse

pytestmark = pytest.mark.api

BASE = "/api/v1/sessions"
S3 = "Node ws-gpu-11 is cordoned with code ERR_THERMAL_88. What should I do?"
FIXTURE_STEPS = json.loads(
    (Settings.from_env({}).fixtures_dir / "runbooks" / "err-thermal-88.json").read_text(
        encoding="utf-8"
    )
)


def client_for() -> TestClient:
    return TestClient(create_app(Settings.from_env({})), raise_server_exceptions=False)


def ask(client: TestClient, text: str):
    created = client.post(BASE, json={"operator_role": "role-operations"})
    assert created.status_code == 201
    sid = created.json()["session_id"]
    return client.post(f"{BASE}/{sid}/queries", json={"query_text": text})


def answer_of(text: str):
    with client_for() as client:
        response = ask(client, text)
    assert response.status_code == 200
    return SubmitQueryResponse.model_validate(response.json()).answers[0]  # extra="forbid"


def test_s3_renders_the_registered_steps_verbatim_with_tools_safety_and_provenance() -> None:
    answer = answer_of(S3)
    assert answer.intent == "diagnose_node_triage"
    assert answer.diagnosis_class == "node_triage_runbook"
    assert answer.answer_chain == ["observation", "evidence", "diagnosis", "recommendation"]
    runbook = answer.recommendation["runbook"]
    assert runbook["steps"] == FIXTURE_STEPS["steps"]  # 100 % step-match
    assert runbook["required_tools"] == FIXTURE_STEPS["required_tools"]
    assert runbook["safety_warnings"] == FIXTURE_STEPS["safety_warnings"]
    assert runbook["provenance"] == {
        "source": FIXTURE_STEPS["approved_source"],
        "version": FIXTURE_STEPS["version"],
    }


def test_s3_claims_cite_only_the_node_record_and_the_evidence_is_positioned() -> None:
    answer = answer_of(S3)
    assert [e.citation_id for e in answer.evidence] == ["node#ws-gpu-11"]
    assert [e.position for e in answer.evidence] == [0]
    assert all(c.claim_citations == ["node#ws-gpu-11"] for c in answer.claims)
    assert answer.canonical is None


def canonical_of(text: str) -> ErrorBody:
    with client_for() as client:
        response = ask(client, text)
    assert (
        response.status_code == 200
    )  # canonical outcomes are answered with HTTP 200 (contracts §4)
    return ErrorBody.model_validate(response.json())


@pytest.mark.parametrize(
    ("query", "named"),
    [
        # mismatch (P2): the node reports ERR_THERMAL_88, the operator asks about another code
        ("Node ws-gpu-11 is cordoned with code ERR_OTHER_01. What should I do?", "ERR_THERMAL_88"),
        # not cordoned (P1): ws-gpu-01 is healthy and reports no code, so the text null is named
        ("Node ws-gpu-01 is cordoned with code ERR_THERMAL_88. What should I do?", "null"),
    ],
)
def test_a_miss_is_the_canonical_literal_and_no_steps(query: str, named: str) -> None:
    body = canonical_of(query)
    assert body.code == "RUNBOOK_NOT_FOUND"
    assert body.message == f"no runbook available for code {named}."


def test_an_unknown_node_is_entity_not_found_with_no_diagnosis() -> None:
    body = canonical_of("Node ws-gpu-99 is cordoned with code ERR_THERMAL_88. What should I do?")
    assert body.code == "ENTITY_NOT_FOUND"
    assert body.message == "Entity Not Found in State: node#ws-gpu-99."


def test_a_triage_question_without_a_code_is_a_clarification() -> None:
    body = canonical_of("Node ws-gpu-11 is cordoned with code. What should I do?")
    assert body.code == "CLARIFICATION_REQUIRED"
    assert body.message == (
        "Clarification required: the query must name a node and the error code it reports."
    )
