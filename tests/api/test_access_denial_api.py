"""Story 1.3 - the access-denial diagnoser served through the real composition root.

No dependency overrides: the app is built by ``create_app`` exactly as in production, over the
real fixtures, the simulated clock/LLM and a SQLite store.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import PROJECT_ROOT, Settings
from src.dto import ErrorBody, GetSessionResponse, SubmitQueryResponse
from src.ports.outbound import LlmProsePort

pytestmark = pytest.mark.api

BASE = "/api/v1/sessions"
S1 = "why was alex denied deepseek-coder"


def client_for(**env: str) -> TestClient:
    settings = Settings.from_env({f"M12_{k.upper()}": v for k, v in env.items()})
    return TestClient(create_app(settings), raise_server_exceptions=False)


def open_session(client: TestClient) -> str:
    created = client.post(BASE, json={"operator_role": "role-operations"})
    assert created.status_code == 201
    return created.json()["session_id"]


def ask(client: TestClient, sid: str, text: str):
    return client.post(f"{BASE}/{sid}/queries", json={"query_text": text})


def test_s1_returns_a_cited_diagnosis_that_validates_against_the_contract() -> None:
    with client_for() as client:
        sid = open_session(client)
        response = ask(client, sid, S1)
    assert response.status_code == 200
    answer = SubmitQueryResponse.model_validate(response.json()).answers[0]  # extra="forbid"
    assert answer.intent == "diagnose_access_denial"
    assert answer.answer_chain == ["observation", "evidence", "diagnosis"]
    assert answer.diagnosis_class == "access_denial_not_in_allowlist"
    cited = {c for claim in answer.claims for c in claim.claim_citations}
    assert {"user#alex", "policy#catalog.4.2", "event#evt-4711"} <= cited
    assert cited <= {e.citation_id for e in answer.evidence}
    assert [e.position for e in answer.evidence] == list(range(len(answer.evidence)))


def test_get_session_returns_the_stored_evidence_claims_and_context() -> None:
    with client_for() as client:
        sid = open_session(client)
        posted = SubmitQueryResponse.model_validate(ask(client, sid, S1).json()).answers[0]
        stored = GetSessionResponse.model_validate(client.get(f"{BASE}/{sid}").json())
    assert stored.turns == [posted]
    assert stored.context.resolved_entities == ["user#alex", "model#deepseek-coder"]
    assert stored.context.prior_intents == ["diagnose_access_denial"]


def test_the_follow_up_reuses_the_model_from_the_session() -> None:
    with client_for() as client:
        sid = open_session(client)
        ask(client, sid, S1)
        follow_up = SubmitQueryResponse.model_validate(
            ask(client, sid, "and what about mateo?").json()
        ).answers[0]
    assert follow_up.diagnosis_class == "access_denial_not_in_allowlist"
    ids = [e.citation_id for e in follow_up.evidence]
    assert ids[:2] == ["user#mateo", "model#deepseek-coder"] and "event#evt-4713" in ids


def test_an_unknown_user_is_a_200_entity_not_found_error_body_and_a_stored_turn() -> None:
    with client_for() as client:
        sid = open_session(client)
        response = ask(client, sid, "why was ghost_user_99 denied deepseek-coder")
        assert response.status_code == 200
        body = ErrorBody.model_validate(response.json())
        assert body.code == "ENTITY_NOT_FOUND"
        assert body.message == "Entity Not Found in State: user#ghost_user_99."
        turns = client.get(f"{BASE}/{sid}").json()["turns"]
    assert [t["canonical"] for t in turns] == ["ENTITY_NOT_FOUND"]
    assert turns[0]["claims"] == [] and turns[0]["evidence"] == []


def test_a_user_without_a_recorded_denial_is_cannot_confirm() -> None:
    with client_for() as client:
        sid = open_session(client)
        response = ask(client, sid, "why was sofia denied deepseek-coder")
        body = ErrorBody.model_validate(response.json())
        turns = client.get(f"{BASE}/{sid}").json()["turns"]
    assert response.status_code == 200 and body.code == "CANNOT_CONFIRM"
    assert body.message.startswith("Cannot confirm (insufficient evidence): checked user#sofia")
    assert turns[0]["canonical"] == "CANNOT_CONFIRM" and turns[0]["evidence"]  # audit trail kept


def test_the_same_turn_is_reproduced_identically_by_a_fresh_service() -> None:
    def run() -> dict:
        with client_for() as client:
            return ask(client, open_session(client), S1).json()

    first = run()
    assert run() == first and run() == first


def test_ids_continue_after_a_restart_including_claim_ids(tmp_path: Path) -> None:
    database = str(tmp_path / "m12.db")
    with client_for(db_path=database) as first:
        sid = open_session(first)
        ask(first, sid, S1)
    with client_for(db_path=database) as second:
        again = ask(second, sid, S1)  # would collide on claims.claim_id if not seeded
        assert again.status_code == 200
        answer = SubmitQueryResponse.model_validate(again.json()).answers[0]
    assert [c.claim_id for c in answer.claims] == [f"clm-{n:016x}" for n in (4, 5, 6)]


def test_a_broken_estate_fails_the_turn_safely_with_a_503(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures"
    shutil.copytree(PROJECT_ROOT / "fixtures", fixtures)
    (fixtures / "estate" / "users.json").unlink()
    with client_for(fixtures_dir=str(fixtures)) as client:  # the app still starts
        sid = open_session(client)
        response = ask(client, sid, S1)
        assert client.get("/readyz").status_code == 503  # readiness reports the estate
    assert response.status_code == 503
    assert response.json()["code"] == "PROVIDER_UNAVAILABLE"


# -- review patches: failures leave no state; follow-ups; logical determinism -------------------
def prose_port(client: TestClient):
    return client.app.state.container.port(LlmProsePort)


@pytest.mark.parametrize(
    ("failure", "code"), [("unavailable", "LLM_UNAVAILABLE"), ("rejected", "LLM_PROSE_REJECTED")]
)
def test_a_failed_llm_turn_is_a_503_that_stores_nothing_and_leaves_the_context(
    failure: str, code: str
) -> None:
    with client_for() as client:
        sid = open_session(client)
        prose = prose_port(client)
        if failure == "unavailable":
            prose.fail()
        else:
            prose.script("Alex was denied.", "The student role.")
        response = ask(client, sid, S1)
        stored = client.get(f"{BASE}/{sid}").json()
    assert response.status_code == 503 and response.json()["code"] == code
    assert stored["turns"] == []
    assert stored["context"] == {
        "resolved_entities": [], "prior_intents": [], "active_answer_ids": [],
    }  # fmt: skip


def test_a_broken_estate_503_also_stores_nothing(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures"
    shutil.copytree(PROJECT_ROOT / "fixtures", fixtures)
    (fixtures / "estate" / "users.json").unlink()
    with client_for(fixtures_dir=str(fixtures)) as client:
        sid = open_session(client)
        assert ask(client, sid, S1).status_code == 503
        stored = client.get(f"{BASE}/{sid}").json()
    assert stored["turns"] == [] and stored["context"]["resolved_entities"] == []


def test_a_follow_up_in_a_fresh_session_asks_for_an_earlier_topic() -> None:
    with client_for() as client:
        body = ask(client, open_session(client), "and what about mateo?").json()
    assert body["code"] == "CLARIFICATION_REQUIRED"
    assert body["message"] == (
        "Clarification required: there is no earlier topic in this session to follow up on."
    )


def test_a_follow_up_uses_the_most_recently_used_model_not_the_first_one() -> None:
    with client_for() as client:
        sid = open_session(client)
        ask(client, sid, S1)  # alex / deepseek-coder
        ask(client, sid, "why was sofia denied llama-3-8b-instruct")
        ask(client, sid, "and what about deepseek-coder?")  # deepseek-coder is used again
        follow_up = SubmitQueryResponse.model_validate(
            ask(client, sid, "and what about mateo?").json()
        ).answers[0]
    assert [e.citation_id for e in follow_up.evidence][:2] == ["user#mateo", "model#deepseek-coder"]


def _logical(answer) -> dict:
    """The answer with the per-request counters (answer, claim and clock-read ids) removed."""
    body = answer.model_dump()
    clock_ids = {e["citation_id"] for e in body["evidence"] if e["source_type"] == "clock"}
    for entry in body["evidence"]:
        if entry["citation_id"] in clock_ids:
            entry["citation_id"] = "clock#<read>"
            entry["snippet"] = "<clock read>"
    for claim in body["claims"]:
        claim["claim_id"] = "<claim>"
        claim["claim_citations"] = [
            "clock#<read>" if c in clock_ids else c for c in claim["claim_citations"]
        ]
    body["answer_id"] = body["session_id"] = "<id>"
    return body


def test_three_sessions_of_one_service_give_logically_identical_answers() -> None:
    with client_for() as client:
        answers = [
            SubmitQueryResponse.model_validate(
                ask(client, open_session(client), S1).json()
            ).answers[0]
            for _ in range(3)
        ]
    first = _logical(answers[0])
    assert _logical(answers[1]) == first and _logical(answers[2]) == first
    # only the counters differ: that is the documented, deliberate difference (AD-22)
    assert len({a.evidence[-1].citation_id for a in answers}) == 3
