"""Story 1.2 - the session REST API against the OpenAPI contract (paths, bodies, status codes).

Every body is validated through the contract DTOs (``extra="forbid"``), every error must be the
``ErrorBody`` envelope, and nothing may leak an internal error text.
"""

from __future__ import annotations

import re

import pytest

from src.dto import ErrorBody, GetSessionResponse, SessionDTO, SubmitQueryResponse

pytestmark = pytest.mark.api

S1 = "why was alex denied deepseek-coder"
ENVELOPE_KEYS = {"code", "status", "message", "retryable", "explanation"}
BASE = "/api/v1/sessions"


def create(api, role: str = "role-operations") -> str:
    response = api.client.post(BASE, json={"operator_role": role})
    assert response.status_code == 201, response.text
    return response.json()["session_id"]


def ask(api, sid: str, text: str = S1, **extra):
    return api.client.post(f"{BASE}/{sid}/queries", json={"query_text": text, **extra})


def assert_envelope(response, status: int, code: str):
    body = response.json()
    assert response.status_code == status, response.text
    assert set(body) == ENVELOPE_KEYS and "detail" not in body
    assert (body["code"], body["status"]) == (code, status)
    ErrorBody.model_validate(body)  # contract DTO, extra="forbid"
    assert response.headers["content-type"].startswith("application/json")
    return body


# -- Scenario: Create a session ----------------------------------------------------------------
def test_post_sessions_returns_201_with_an_active_session(api) -> None:
    response = api.client.post(BASE, json={"operator_role": "role-operations"})
    assert response.status_code == 201
    session = SessionDTO.model_validate(response.json())
    assert re.fullmatch(r"sess-[0-9a-f]{16}", session.session_id)
    assert session.status == "active" and session.created_at == "2026-10-16T15:00:00.000Z"
    assert session.context.model_dump() == {
        "resolved_entities": [], "prior_intents": [], "active_answer_ids": [],
    }  # fmt: skip
    assert set(response.json()) == {
        "session_id",
        "created_at",
        "operator_role",
        "context",
        "status",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"operator_role": "admin"},
        {"operator_role": "role-"},
        {"operator_role": 7},
        {},
        {"operator_role": "role-ops", "extra": 1},
    ],
)
def test_a_bad_create_body_is_a_400_envelope(api, payload) -> None:
    assert_envelope(api.client.post(BASE, json=payload), 400, "VALIDATION_MALFORMED_BODY")


def test_a_non_json_create_body_is_a_400_envelope(api) -> None:
    response = api.client.post(
        BASE, content="not json", headers={"content-type": "application/json"}
    )
    assert_envelope(response, 400, "VALIDATION_MALFORMED_BODY")


# -- Scenario: Route the S1 query --------------------------------------------------------------
def test_the_s1_query_returns_a_200_envelope_routed_to_access_denial(api) -> None:
    sid = create(api)
    response = ask(api, sid)
    assert response.status_code == 200
    body = SubmitQueryResponse.model_validate(response.json())
    assert len(body.answers) == 1
    answer = body.answers[0]
    assert answer.intent == "diagnose_access_denial" and answer.answer_chain == ["observation"]
    assert answer.session_id == sid and answer.query == S1
    assert set(response.json()) == {"answers"}


def test_the_same_query_twice_creates_two_answers(api) -> None:
    sid = create(api)
    first = ask(api, sid).json()["answers"][0]["answer_id"]
    second = ask(api, sid).json()["answers"][0]["answer_id"]
    assert first != second


# -- Scenario: clarification is a 200 ErrorBody ------------------------------------------------
@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("what's the weather?", "Clarification required: no registered intent matches this query."),
        (
            "why was alex denied deepseek-coder and delete all his jobs",
            "Clarification required: the query mixes a diagnosis with a destructive action; "
            "submit them separately.",
        ),
    ],
)
def test_clarifications_are_http_200_with_the_canonical_literal_in_an_error_body(
    api, text: str, message: str
) -> None:
    response = ask(api, create(api), text)
    body = assert_envelope(response, 200, "CLARIFICATION_REQUIRED")
    assert body["message"] == message and body["retryable"] is False


def test_a_clarified_turn_is_still_listed_among_the_turns(api) -> None:
    sid = create(api)
    ask(api, sid, "what's the weather?")
    turns = api.client.get(f"{BASE}/{sid}").json()["turns"]
    assert [(t["intent"], t["canonical"]) for t in turns] == [("clarification", "CLARIFICATION")]


# -- Scenario: Query validation ----------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "code", "message"),
    [
        (
            "",
            "VALIDATION_EMPTY_QUERY",
            "Query must contain between 1 and 1000 characters; received 0.",
        ),
        (
            "   ",
            "VALIDATION_EMPTY_QUERY",
            "Query must contain between 1 and 1000 characters; received 0.",
        ),
        ("a" * 1001, "VALIDATION_QUERY_TOO_LONG", "Query exceeds 1000 characters; received 1001."),
    ],
)
def test_empty_and_too_long_queries_are_400_with_the_contract_codes(
    api, text, code, message
) -> None:
    body = assert_envelope(ask(api, create(api), text), 400, code)
    assert body["message"] == message and body["retryable"] is False


def test_a_1000_character_query_is_accepted(api) -> None:
    assert ask(api, create(api), "a" * 1000).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"query_text": 123},
        {"query_text": None},
        {"query_text": "x", "session_id": "sess-0000000000000001"},
    ],
)
def test_a_bad_query_body_is_a_400_malformed_body(api, payload) -> None:
    sid = create(api)
    assert_envelope(
        api.client.post(f"{BASE}/{sid}/queries", json=payload), 400, "VALIDATION_MALFORMED_BODY"
    )


def test_a_rejected_query_leaves_the_session_untouched(api) -> None:
    sid = create(api)
    ask(api, sid, "")
    ask(api, sid, "x", session_id=sid)
    session = api.client.get(f"{BASE}/{sid}").json()
    assert session["turns"] == [] and session["context"]["prior_intents"] == []


# -- Scenario: session states ------------------------------------------------------------------
def test_an_unknown_session_is_404_with_the_contract_message(api) -> None:
    sid = "sess-00000000000000ff"
    for response in (
        ask(api, sid),
        api.client.get(f"{BASE}/{sid}"),
        api.client.delete(f"{BASE}/{sid}"),
    ):
        body = assert_envelope(response, 404, "SESSION_NOT_FOUND")
        assert body["message"] == f"Session {sid} not found."


@pytest.mark.parametrize(
    "sid", ["nope", "sess-XYZ", "sess-0000000000000001ff", "SESS-0000000000000001"]
)
def test_a_malformed_session_id_is_a_400_before_any_lookup(api, sid: str) -> None:
    for response in (
        ask(api, sid),
        api.client.get(f"{BASE}/{sid}"),
        api.client.delete(f"{BASE}/{sid}"),
    ):
        assert_envelope(response, 400, "VALIDATION_MALFORMED_BODY")


def test_an_idle_session_is_410_and_get_then_shows_expired(api) -> None:
    sid = create(api)
    api.clock.advance(minutes=31)
    body = assert_envelope(ask(api, sid), 410, "SESSION_EXPIRED")
    assert body["message"] == f"Session {sid} expired after 30 minutes idle."
    assert api.client.get(f"{BASE}/{sid}").json()["status"] == "expired"


def test_exactly_30_minutes_idle_is_still_accepted(api) -> None:
    sid = create(api)
    api.clock.advance(minutes=30)
    assert ask(api, sid).status_code == 200


# -- Scenario: read and reset ------------------------------------------------------------------
def test_get_session_returns_the_context_and_turns(api) -> None:
    sid = create(api)
    ask(api, sid)
    ask(api, sid, "hello")
    response = api.client.get(f"{BASE}/{sid}")
    assert response.status_code == 200
    session = GetSessionResponse.model_validate(response.json())
    assert [t.answer_id for t in session.turns] == ["ans-0000000000000001", "ans-0000000000000002"]
    assert session.context.prior_intents == ["diagnose_access_denial", "clarification"]
    assert api.client.get(f"{BASE}/{sid}").json() == response.json()  # idempotent read


def test_delete_returns_204_with_no_body_clears_the_context_and_is_idempotent(api) -> None:
    sid = create(api)
    ask(api, sid)
    first = api.client.delete(f"{BASE}/{sid}")
    assert first.status_code == 204 and first.content == b""
    assert api.client.delete(f"{BASE}/{sid}").status_code == 204
    session = api.client.get(f"{BASE}/{sid}").json()
    assert session["status"] == "reset" and len(session["turns"]) == 1
    assert session["context"] == {
        "resolved_entities": [],
        "prior_intents": [],
        "active_answer_ids": [],
    }


def test_a_query_to_a_reset_session_is_410(api) -> None:
    sid = create(api)
    api.client.delete(f"{BASE}/{sid}")
    assert_envelope(ask(api, sid), 410, "SESSION_EXPIRED")


# -- Scenario: follow-up -----------------------------------------------------------------------
def test_a_follow_up_is_routed_from_the_session_context_over_http(api) -> None:
    sid = create(api)
    ask(api, sid)
    answer = ask(api, sid, "and what about mateo?").json()["answers"][0]
    assert answer["intent"] == "diagnose_access_denial"
    assert_envelope(ask(api, create(api), "and what about mateo?"), 200, "CLARIFICATION_REQUIRED")


# -- errors never leak, dependencies fail safely -----------------------------------------------
def test_a_store_failure_is_503_with_only_the_safe_literal(api) -> None:
    sid = create(api)
    api.store._connection.close()  # noqa: SLF001
    for response in (
        ask(api, sid),
        api.client.get(f"{BASE}/{sid}"),
        api.client.delete(f"{BASE}/{sid}"),
    ):
        body = assert_envelope(response, 503, "PROVIDER_UNAVAILABLE")
        assert (
            body["message"] == "Provider unavailable — cannot answer." and body["retryable"] is True
        )
        assert body["explanation"]["observed_values"] == []  # no sqlite text leaks to the client
        assert "sqlite" not in response.text.lower() and "closed" not in response.text.lower()


def test_a_clock_failure_is_503(api) -> None:
    api.clock.fail()
    assert_envelope(
        api.client.post(BASE, json={"operator_role": "role-operations"}), 503, "CLOCK_UNAVAILABLE"
    )


def test_unsupported_methods_use_the_envelope_too(api) -> None:
    assert_envelope(api.client.put(BASE, json={}), 405, "VALIDATION_MALFORMED_BODY")
    assert_envelope(
        api.client.get(f"{BASE}/sess-0000000000000001/queries"), 405, "VALIDATION_MALFORMED_BODY"
    )


def test_a_nul_character_in_a_query_is_a_400_not_a_retryable_503(api) -> None:
    body = assert_envelope(
        ask(api, create(api), "\u0000why was alex denied"), 400, "VALIDATION_MALFORMED_BODY"
    )
    assert body["retryable"] is False
