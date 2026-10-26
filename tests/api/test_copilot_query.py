"""Annex 12.1 inbound: ``POST /api/v1/copilot/query`` with ``{ "query": "..." }``."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import Settings
from src.dto import ErrorBody, SubmitQueryResponse

pytestmark = pytest.mark.api

PATH = "/api/v1/copilot/query"
ANNEX_QUERY = "Why was student alex denied access to deepseek-coder?"


def client() -> TestClient:
    return TestClient(create_app(Settings.from_env({})), raise_server_exceptions=False)


def test_the_annex_payload_returns_the_cited_access_denial_diagnosis() -> None:
    with client() as http:
        response = http.post(PATH, json={"query": ANNEX_QUERY})
    assert response.status_code == 200
    answer = SubmitQueryResponse.model_validate(response.json()).answers[0]
    assert answer.intent == "diagnose_access_denial"
    assert answer.diagnosis_class == "access_denial_not_in_allowlist"
    assert answer.answer_chain == ["observation", "evidence", "diagnosis"]
    ids = {e.citation_id for e in answer.evidence}
    assert {"user#alex", "model#deepseek-coder", "policy#catalog.4.2", "event#evt-4711"} <= ids
    assert all(set(c.claim_citations) <= ids for c in answer.claims)
    assert "RULE-CAT-04" in " ".join(c.text for c in answer.claims)


def test_the_turn_is_stored_in_a_session_the_caller_can_read_back() -> None:
    with client() as http:
        answer = SubmitQueryResponse.model_validate(
            http.post(PATH, json={"query": ANNEX_QUERY}).json()
        ).answers[0]
        stored = http.get(f"/api/v1/sessions/{answer.session_id}").json()
    assert [t["answer_id"] for t in stored["turns"]] == [answer.answer_id]


def test_the_other_annex_scenarios_work_on_the_same_endpoint() -> None:
    with client() as http:
        window = http.post(PATH, json={"query": "Why can't Group 4 run their fine-tuning job now?"})
        ghost = http.post(PATH, json={"query": "Why was ghost_user_99 denied deepseek-coder?"})
    assert SubmitQueryResponse.model_validate(window.json()).answers[0].diagnosis_class == (
        "schedule_window_restricted"
    )
    assert window.json()["answers"][0]["recommendation"]["next_open_window"] == {
        "start": "2026-10-16T22:00:00.000Z", "end": "2026-10-17T06:00:00.000Z", "timezone": "UTC",
    }  # fmt: skip
    body = ErrorBody.model_validate(ghost.json())
    assert (ghost.status_code, body.code) == (200, "ENTITY_NOT_FOUND")


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"query": ""}, "VALIDATION_EMPTY_QUERY"),
        ({"query": "x" * 1001}, "VALIDATION_QUERY_TOO_LONG"),
        ({}, "VALIDATION_MALFORMED_BODY"),
        ({"query": ANNEX_QUERY, "extra": 1}, "VALIDATION_MALFORMED_BODY"),
        ({"query_text": ANNEX_QUERY}, "VALIDATION_MALFORMED_BODY"),
    ],
)
def test_a_bad_payload_is_a_structured_400(payload: dict, code: str) -> None:
    with client() as http:
        response = http.post(PATH, json=payload)
    assert response.status_code == 400 and response.json()["code"] == code
    assert set(response.json()) >= {"code", "status", "message", "retryable"}


def test_a_destructive_request_is_refused_not_executed() -> None:
    with client() as http:
        response = http.post(PATH, json={"query": "Delete all pending jobs for CS201"})
    assert response.status_code == 200
    assert response.json()["code"] in {"CLARIFICATION_REQUIRED", "ACTION_REFUSED"}
