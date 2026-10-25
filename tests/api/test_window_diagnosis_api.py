"""Story 3.1 - the window diagnoser served through the real composition root (Annex 12.2)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import Settings
from src.dto import ErrorBody, GetSessionResponse, SubmitQueryResponse
from src.ports.outbound import ClockPort

pytestmark = pytest.mark.api

BASE = "/api/v1/sessions"
S2 = "why can't group 4 run their fine-tuning job right now"


def client_for() -> TestClient:
    return TestClient(create_app(Settings.from_env({})), raise_server_exceptions=False)


def open_session(client: TestClient) -> str:
    created = client.post(BASE, json={"operator_role": "role-operations"})
    assert created.status_code == 201
    return created.json()["session_id"]


def ask(client: TestClient, sid: str, text: str):
    return client.post(f"{BASE}/{sid}/queries", json={"query_text": text})


def test_s2_explains_the_restriction_and_gives_the_next_open_window() -> None:
    with client_for() as client:
        sid = open_session(client)
        response = ask(client, sid, S2)
    assert response.status_code == 200
    answer = SubmitQueryResponse.model_validate(response.json()).answers[0]  # extra="forbid"
    assert answer.intent == "diagnose_schedule_window"
    assert answer.diagnosis_class == "schedule_window_restricted"
    assert answer.answer_chain == ["observation", "evidence", "diagnosis"]
    text = " ".join(claim.text for claim in answer.claims)
    assert "2026-10-16T22:00:00.000Z" in text and "2026-10-17T06:00:00.000Z" in text
    assert "(UTC)" in text and "2026-10-16T15:00:00.000Z" in text  # date + timezone, at "now"
    ids = {e.citation_id for e in answer.evidence}
    assert {"group#group-4", "job#job-8823", "window#night"} <= ids
    assert all(set(claim.claim_citations) <= ids for claim in answer.claims)
    assert [e.position for e in answer.evidence] == list(range(len(answer.evidence)))


def test_the_turn_is_stored_and_the_session_context_gains_the_group() -> None:
    with client_for() as client:
        sid = open_session(client)
        posted = SubmitQueryResponse.model_validate(ask(client, sid, S2).json()).answers[0]
        stored = GetSessionResponse.model_validate(client.get(f"{BASE}/{sid}").json())
    assert stored.turns == [posted]
    assert stored.context.resolved_entities == ["group#group-4"]


def test_a_group_without_a_constraint_gets_no_restriction_and_no_window() -> None:
    with client_for() as client:
        answer = SubmitQueryResponse.model_validate(
            ask(client, open_session(client), "why can't group 7 run their job").json()
        ).answers[0]
    assert answer.diagnosis_class == "schedule_no_constraint"
    assert not [e for e in answer.evidence if e.source_type == "window"]


def test_a_missing_group_is_a_200_entity_not_found() -> None:
    with client_for() as client:
        response = ask(client, open_session(client), "why can't group 99 run their job")
    assert response.status_code == 200
    body = ErrorBody.model_validate(response.json())
    assert body.code == "ENTITY_NOT_FOUND"
    assert body.message == "Entity Not Found in State: group#group-99."


def test_a_failed_clock_is_a_503_that_never_fabricates_a_window() -> None:
    with client_for() as client:
        sid = open_session(client)
        client.app.state.container.port(ClockPort).fail()
        response = ask(client, sid, S2)
        client.app.state.container.port(ClockPort).recover()
        stored = client.get(f"{BASE}/{sid}").json()
    assert response.status_code == 503 and response.json()["code"] == "CLOCK_UNAVAILABLE"
    assert stored["turns"] == []


VARIANTS = [
    "why can't group 4 run their fine-tuning job right now",
    "Why can’t Group 4 run their fine-tuning job right now?",
    "why cannot group 4 run its job",
    "why won't group 4's fine-tuning job start",
    "why is group 4's job not running",
    "why is group 4's job pending",
    "when can group 4 run their fine-tuning job",
    "why can't group-4 launch fine-tuning now",
    "why isn't group 4 able to run its job",
    "when does the next window open for group 4",
]


def test_ten_phrasings_all_give_the_same_cited_diagnosis() -> None:
    with client_for() as client:
        classes = []
        for query in VARIANTS:
            answer = SubmitQueryResponse.model_validate(
                ask(client, open_session(client), query).json()
            ).answers[0]
            classes.append((answer.intent, answer.diagnosis_class))
    assert classes == [("diagnose_schedule_window", "schedule_window_restricted")] * len(VARIANTS)
