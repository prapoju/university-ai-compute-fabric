"""Story 1.5 - ``GET /api/v1/sessions/{sid}/audit`` through the real composition root (AC 6)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.adapters.inbound.audit import get_audit_use_cases
from src.application.unavailable import UnavailableAuditUseCases
from src.config import Settings
from src.domain import canonical_strings as cs
from src.dto import GetAuditPageResponse

pytestmark = pytest.mark.api

SESSIONS = "/api/v1/sessions"
S1 = "why was alex denied deepseek-coder"
S1_TOOL_CALLS = [
    "toolcall.answer_query",
    "toolcall.users_port.get",
    "toolcall.catalog_port.get",
    "toolcall.policy_port.for_model",
    "toolcall.event_store_port.query",
]
AUDIT_RECORD_FIELDS = {
    "audit_id", "tool_call_id", "session_id", "operator_role", "timestamp", "result_summary",
    "actor", "proposal_id",
}  # fmt: skip


def client_for(**env: str) -> TestClient:
    settings = Settings.from_env({f"M12_{k.upper()}": v for k, v in env.items()})
    return TestClient(create_app(settings), raise_server_exceptions=False)


@pytest.fixture
def client():
    with client_for() as client:
        yield client


def new_session(client: TestClient) -> str:
    return client.post(SESSIONS, json={"operator_role": "role-operations"}).json()["session_id"]


def s1(client: TestClient) -> str:
    sid = new_session(client)
    assert client.post(f"{SESSIONS}/{sid}/queries", json={"query_text": S1}).status_code == 200
    return sid


def audit(client: TestClient, sid: str, **params):
    return client.get(f"{SESSIONS}/{sid}/audit", params=params)


def retained(client: TestClient) -> int:
    with client.app.state.container.writer.read() as db:
        return db.execute("SELECT count(*) FROM audit_records").fetchone()[0]


def test_after_s1_the_page_lists_every_tool_call_once_in_call_order(client) -> None:
    sid = s1(client)
    response = audit(client, sid)
    assert response.status_code == 200
    body = response.json()
    page = GetAuditPageResponse.model_validate(body)  # schema-valid (dto mirrors openapi)
    assert [e.result_summary["tool_name"] for e in page.entries] == S1_TOOL_CALLS
    assert len({e.tool_call_id for e in page.entries}) == len(S1_TOOL_CALLS)
    assert (body["page"], body["page_size"], body["total"], body["has_more"]) == (1, 20, 5, False)
    assert all(set(entry) == AUDIT_RECORD_FIELDS for entry in body["entries"])
    assert {e["session_id"] for e in body["entries"]} == {sid}
    assert all(S1 not in str(entry) for entry in body["entries"])


def test_paging_has_more_and_a_page_beyond_the_rows(client) -> None:
    sid = s1(client)
    first = audit(client, sid, page=1, page_size=2).json()
    second = audit(client, sid, page=2, page_size=2).json()
    third = audit(client, sid, page=3, page_size=2).json()
    assert [first["has_more"], second["has_more"], third["has_more"]] == [True, True, False]
    names = [e["result_summary"]["tool_name"] for p in (first, second, third) for e in p["entries"]]
    assert names == S1_TOOL_CALLS
    beyond = audit(client, sid, page=9, page_size=2)
    assert beyond.status_code == 200
    assert beyond.json()["entries"] == [] and beyond.json()["total"] == 5  # E14


def test_a_new_session_has_an_empty_audit(client) -> None:
    body = audit(client, new_session(client)).json()
    assert (body["entries"], body["total"], body["has_more"]) == ([], 0, False)


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0}, {"page": -1}, {"page_size": 0}, {"page_size": 101},
        {"page": 501, "page_size": 20},  # (501-1)*20 = 10,000: at the default cap
    ],
)  # fmt: skip
def test_invalid_pagination_is_a_400(client, params) -> None:
    response = audit(client, new_session(client), **params)
    assert response.status_code == 400
    body = response.json()
    assert (body["code"], body["retryable"]) == ("PAGINATION_INVALID", False)
    assert body["message"].startswith("Invalid pagination: page_size")


def test_the_page_depth_is_bounded_by_the_retention_cap() -> None:
    with client_for(audit_retention_cap="5") as client:
        sid = new_session(client)
        assert audit(client, sid, page=5, page_size=1).status_code == 200  # (5-1)*1 < 5
        assert audit(client, sid, page=6, page_size=1).status_code == 400  # (6-1)*1 >= 5
        assert audit(client, sid, page=1, page_size=100).status_code == 200


def test_pagination_is_checked_before_the_session_lookup(client) -> None:
    response = audit(client, "sess-00000000000000ff", page=0)
    assert response.json()["code"] == "PAGINATION_INVALID"


def test_an_unknown_session_is_a_404(client) -> None:
    response = audit(client, "sess-00000000000000ff")
    assert response.status_code == 404
    assert response.json()["code"] == "SESSION_NOT_FOUND"
    assert response.json()["message"] == "Session sess-00000000000000ff not found."


def test_a_malformed_session_id_is_a_400(client) -> None:
    response = client.get(f"{SESSIONS}/not-a-session/audit")
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_MALFORMED_BODY"


def test_an_unavailable_store_is_a_503_with_only_the_safe_literal(client) -> None:
    client.app.dependency_overrides[get_audit_use_cases] = lambda: UnavailableAuditUseCases(
        "disk gone"
    )
    response = audit(client, "sess-0000000000000001")
    assert response.status_code == 503
    body = response.json()
    assert (body["code"], body["message"]) == ("PROVIDER_UNAVAILABLE", cs.S_PUA)
    assert "disk gone" not in response.text


def test_a_broken_audit_table_is_a_503_not_a_crash(client) -> None:
    sid = s1(client)
    with client.app.state.container.writer.transaction() as db:
        db.execute("ALTER TABLE audit_records RENAME TO audit_records_gone")
    response = audit(client, sid)
    assert response.status_code == 503 and response.json()["message"] == cs.S_PUA


def test_reading_the_audit_writes_no_audit_row(client) -> None:
    sid = s1(client)
    before = retained(client)
    for _ in range(2):
        assert audit(client, sid).status_code == 200
    assert retained(client) == before == 5


@pytest.mark.parametrize("method", ["put", "patch", "delete", "post"])
def test_no_route_edits_or_deletes_the_audit(client, method: str) -> None:
    sid = s1(client)
    response = getattr(client, method)(f"{SESSIONS}/{sid}/audit")
    assert response.status_code in (404, 405)
    assert retained(client) == 5
