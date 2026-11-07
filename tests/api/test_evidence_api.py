"""Story 1.4 - the evidence and citation routes through the real composition root (no overrides)."""

from __future__ import annotations

from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import Settings
from src.domain import canonical_strings as cs

pytestmark = pytest.mark.api

SESSIONS = "/api/v1/sessions"
S1 = "why was alex denied deepseek-coder"


def client_for(**env: str) -> TestClient:
    settings = Settings.from_env({f"M12_{k.upper()}": v for k, v in env.items()})
    return TestClient(create_app(settings), raise_server_exceptions=False)


def citation(client: TestClient, cid: str):
    return client.get(f"/api/v1/citations/{quote(cid, safe='')}")


@pytest.fixture
def client():
    with client_for() as client:
        yield client


@pytest.fixture
def s1(client: TestClient) -> tuple[str, dict]:
    sid = client.post(SESSIONS, json={"operator_role": "role-operations"}).json()["session_id"]
    body = client.post(f"{SESSIONS}/{sid}/queries", json={"query_text": S1}).json()
    return sid, body["answers"][0]


def assert_not_found(response, ref: str) -> None:
    assert response.status_code == 404
    body = response.json()
    assert (body["code"], body["status"], body["retryable"]) == ("ENTITY_NOT_FOUND", 404, False)
    assert body["message"] == cs.S_ENF.format(ref_list=ref)


# -- GET /api/v1/answers/{aid}/evidence ---------------------------------------------------------
def test_the_evidence_route_returns_the_stored_set_in_position_order(client, s1) -> None:
    _, answer = s1
    response = client.get(f"/api/v1/answers/{answer['answer_id']}/evidence")
    assert response.status_code == 200
    assert response.json() == {"evidence": answer["evidence"]}
    assert [e["position"] for e in response.json()["evidence"]] == list(
        range(len(answer["evidence"]))
    )


def test_an_unknown_answer_is_a_404_entity_not_found(client) -> None:
    assert_not_found(
        client.get("/api/v1/answers/ans-00000000000000ff/evidence"), "ans-00000000000000ff"
    )


# -- GET /api/v1/citations/{cid} ----------------------------------------------------------------
def test_a_record_citation_returns_the_source_record_and_the_stored_snippet(client, s1) -> None:
    _, answer = s1
    response = citation(client, "user#alex")
    assert response.status_code == 200
    stored = next(e for e in answer["evidence"] if e["citation_id"] == "user#alex")
    assert response.json() == {
        "source_record": {"id": "user#alex", "display_name": "Alex Rivera", "role": "student"},
        "snippet": stored["snippet"],
    }


def test_a_clock_citation_returns_the_clock_read(client, s1) -> None:
    _, answer = s1
    clock = next(e for e in answer["evidence"] if e["source_type"] == "clock")
    response = citation(client, clock["citation_id"])
    assert response.status_code == 200
    assert response.json() == {
        "source_record": {
            "read_id": clock["citation_id"].removeprefix("clock#"),
            "instant": "2026-10-16T15:00:00.000Z",
            "source": "clock",
        },
        "snippet": clock["snippet"],
    }


@pytest.mark.parametrize(
    "cid",
    [
        "user#nobody",  # well formed, cited by no answer
        "model#deepseek-coder-v9",
        "alex",  # malformed: no type (D6, never a 400)
        "course#CS-101",  # malformed: not a citation type
        "user#a/b",  # an encoded slash still reaches the route, never the framework 404
        "user#",
    ],
)
def test_an_uncited_or_malformed_citation_is_a_404_with_the_s_enf_body(client, s1, cid) -> None:
    assert_not_found(citation(client, cid), cid)


def test_an_existing_record_that_no_answer_cites_is_still_a_404(client) -> None:
    assert_not_found(citation(client, "user#alex"), "user#alex")  # AD-8


def test_a_broken_database_answers_503_on_both_routes_and_never_crashes(tmp_path) -> None:
    with client_for(db_path=str(tmp_path / "missing" / "m12.db")) as broken:
        for response in (
            broken.get("/api/v1/answers/ans-0000000000000001/evidence"),
            citation(broken, "user#alex"),
        ):
            assert response.status_code == 503
            assert response.json()["code"] == "PROVIDER_UNAVAILABLE"
            assert response.json()["message"] == cs.S_PUA


def test_both_routes_are_read_only(client, s1) -> None:
    sid, answer = s1
    before = client.get(f"{SESSIONS}/{sid}").json()
    evidence_route = f"/api/v1/answers/{answer['answer_id']}/evidence"
    first = [client.get(evidence_route), citation(client, "event#evt-4711")]
    second = [client.get(evidence_route), citation(client, "event#evt-4711")]
    assert [r.status_code for r in first + second] == [200, 200, 200, 200]
    assert [r.json() for r in first] == [r.json() for r in second]
    after = client.get(f"{SESSIONS}/{sid}").json()
    assert after == before and len(after["turns"]) == 1
