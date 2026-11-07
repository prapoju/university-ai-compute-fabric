"""Story 1.5 ATDD - the tool-call audit log and state inspection on the real app.

Every scenario builds the real app through ``create_app(Settings.from_env(...))`` on a **file**
database under ``tmp_path``: real composition root, real fixtures, real migrated SQLite schema,
the simulated prose writer and the simulated clock. Nothing is mocked.

Cases were taken from the stub suite ``test/atdd/module12_contracts.test.py``
(``test_get_audit_page_*``, ``test_get_state_record_*``, ``test_browse_state_*``), which is never
imported. Its ``toolcall.state.get`` expectation is not carried over: session-less reads are not
audited (story 1.5 D2).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import PROJECT_ROOT, Settings
from src.domain import canonical_strings as cs
from src.domain.result import is_ok
from src.ports.inbound import SessionUseCases

pytestmark = pytest.mark.api

SESSIONS = "/api/v1/sessions"
S1 = "Why was student Alex denied access to model deepseek-coder?"
S1_TOOL_CALLS = [
    "toolcall.answer_query",
    "toolcall.users_port.get",
    "toolcall.catalog_port.get",
    "toolcall.policy_port.for_model",
    "toolcall.event_store_port.query",
]
SECRETS = ("sk-live-123", "abc123", "t0ps3cret")
ESTATE = PROJECT_ROOT / "fixtures" / "estate"


def app_on(tmp_path: Path, **env: str):
    settings = Settings.from_env(
        {"M12_DB_PATH": str(tmp_path / "m12.db"), **{f"M12_{k.upper()}": v for k, v in env.items()}}
    )
    return create_app(settings)


def new_session(client: TestClient) -> str:
    created = client.post(SESSIONS, json={"operator_role": "role-operations"})
    assert created.status_code == 201
    return created.json()["session_id"]


def ask(client: TestClient, sid: str, query: str = S1) -> dict:
    response = client.post(f"{SESSIONS}/{sid}/queries", json={"query_text": query})
    assert response.status_code == 200, response.json()
    return response.json()


def audit_page(client: TestClient, sid: str, **params) -> dict:
    response = client.get(f"{SESSIONS}/{sid}/audit", params=params)
    assert response.status_code == 200, response.json()
    return response.json()


def raw_rows(database: Path, table: str) -> list[tuple]:
    connection = sqlite3.connect(database)
    try:
        return connection.execute(f"SELECT * FROM {table}").fetchall()
    finally:
        connection.close()


def fixture(route: str, key: str, field: str = "id") -> dict:
    records = json.loads((ESTATE / f"{route}.json").read_text(encoding="utf-8"))
    return next(r for r in records if r[field] == key)


# -- AC 2 + AC 3 + AC 6: the S1 investigation is audited, once per tool call, in call order ----
def test_the_s1_investigation_lists_every_tool_call_once_in_call_order(tmp_path: Path) -> None:
    app = app_on(tmp_path)
    with TestClient(app) as client:
        sid = new_session(client)
        answer = ask(client, sid)["answers"][0]
        body = audit_page(client, sid)

        names = [e["result_summary"]["tool_name"] for e in body["entries"]]
        assert names == S1_TOOL_CALLS
        assert body["total"] == len(S1_TOOL_CALLS) and body["has_more"] is False
        ids = [e["tool_call_id"] for e in body["entries"]]
        assert len(set(ids)) == len(ids) == len(S1_TOOL_CALLS)
        assert {(e["session_id"], e["operator_role"], e["actor"]) for e in body["entries"]} == {
            (sid, "role-operations", "copilot")
        }
        assert body["entries"][0]["result_summary"]["diagnosis_class"] == answer["diagnosis_class"]

        # append-only: no route edits or deletes an audit row (AD-10, AD-13)
        for method in ("put", "patch", "delete", "post"):
            response = getattr(client, method)(f"{SESSIONS}/{sid}/audit")
            assert response.status_code in (404, 405), method
        assert audit_page(client, sid) == body  # unchanged, and reading wrote nothing (Q3)

    audit_routes = [
        (method.upper(), path)
        for path, item in app.openapi()["paths"].items()
        if "audit" in path
        for method in item
    ]
    assert audit_routes == [("GET", "/api/v1/sessions/{sid}/audit")]  # read-only


def test_the_audit_rows_are_append_only_in_the_real_database(tmp_path: Path) -> None:
    with TestClient(app_on(tmp_path)) as client:
        ask(client, new_session(client))
    connection = sqlite3.connect(tmp_path / "m12.db")
    try:
        with pytest.raises(sqlite3.IntegrityError, match="UPDATE denied"):
            connection.execute("UPDATE audit_records SET actor = 'executor'")
        with pytest.raises(sqlite3.IntegrityError, match="DELETE denied"):
            connection.execute("DELETE FROM audit_records")
        connection.rollback()
        assert connection.execute("SELECT count(*) FROM audit_records").fetchone() == (5,)
        assert connection.execute(
            "SELECT gate_open FROM audit_rotation_gate WHERE gate_id = 1"
        ).fetchone() == (0,)
    finally:
        connection.close()


# -- AC 4: write-time redaction ----------------------------------------------------------------
def test_secrets_in_the_query_never_reach_the_audit_tables(tmp_path: Path) -> None:
    query = f"{S1} Authorization: Bearer sk-live-123 api_key=abc123 token: t0ps3cret"
    with TestClient(app_on(tmp_path)) as client:
        sid = new_session(client)
        ask(client, sid, query)
        page = json.dumps(audit_page(client, sid))
    stored = " ".join(
        str(value)
        for table in ("tool_calls", "audit_records")
        for row in raw_rows(tmp_path / "m12.db", table)
        for value in row
    )
    assert stored  # the turn was audited
    for secret in SECRETS:
        assert stored.count(secret) == 0 and page.count(secret) == 0, secret
    assert query not in stored  # the query text itself is never stored in an audit row


def test_a_secret_that_reaches_a_port_parameter_is_redacted_before_it_is_stored(
    tmp_path: Path,
) -> None:
    # In the entity slot the secret is resolved as an id, so it really is a ``users_port.get``
    # parameter. The test above never gets a secret that far, so it cannot catch a redaction bug.
    query = "Why was student api_key=abc123 denied access to model deepseek-coder?"
    with TestClient(app_on(tmp_path)) as client:
        sid = new_session(client)
        ask(client, sid, query)
        page = json.dumps(audit_page(client, sid))
    connection = sqlite3.connect(tmp_path / "m12.db")
    try:
        params = connection.execute(
            "SELECT params_summary FROM tool_calls WHERE tool_name = 'toolcall.users_port.get'"
        ).fetchall()
    finally:
        connection.close()
    assert [json.loads(p) for (p,) in params] == [{"id": "user#api_key=[REDACTED]"}]  # AC 4 marker
    stored = " ".join(
        str(value)
        for table in ("tool_calls", "audit_records")
        for row in raw_rows(tmp_path / "m12.db", table)
        for value in row
    )
    assert stored.count("abc123") == 0 and page.count("abc123") == 0


# -- AC 5: retention cap -----------------------------------------------------------------------
def test_with_cap_5_two_s1_turns_keep_exactly_the_5_newest_rows(tmp_path: Path) -> None:
    with TestClient(app_on(tmp_path, audit_retention_cap="5")) as client:
        sid = new_session(client)
        ask(client, sid)
        ask(client, sid)
        body = audit_page(client, sid)
    kept = raw_rows(tmp_path / "m12.db", "audit_records")
    assert len(kept) == 5 and body["total"] == 5
    order = sorted((row[4], row[0]) for row in kept)  # (timestamp, audit_id)
    assert [audit_id for _, audit_id in order] == [f"aud-{n:016x}" for n in range(6, 11)]
    removed = [(body["entries"][0]["timestamp"], f"aud-{n:016x}") for n in range(1, 6)]
    assert max(removed) < min(order)  # every remaining row is newer than every removed one
    assert [e["result_summary"]["tool_name"] for e in body["entries"]] == S1_TOOL_CALLS
    calls = {row[0] for row in raw_rows(tmp_path / "m12.db", "tool_calls")}
    assert calls == {f"tc-{n:016x}" for n in range(6, 11)}  # their tool calls went with them


# -- AC 7: state inspection of the S1 evidence ---------------------------------------------------
@pytest.mark.parametrize(
    ("path", "route", "key", "field"),
    [
        ("users/alex", "users", "user#alex", "id"),
        ("catalog/deepseek-coder", "catalog", "model#deepseek-coder", "id"),
        ("policy/catalog.4.2", "policy", "policy#catalog.4.2", "clause_id"),
    ],
)
def test_the_s1_evidence_is_inspectable_field_for_field(
    tmp_path: Path, path: str, route: str, key: str, field: str
) -> None:
    with TestClient(app_on(tmp_path)) as client:
        response = client.get(f"/api/v1/state/{path}")
        assert response.status_code == 200
        assert response.json() == fixture(route, key, field)
        browsed = client.get(f"/api/v1/state/{route}", params={"q": key.upper()})
        assert browsed.status_code == 200
        assert browsed.json()["items"] == [fixture(route, key, field)]


def test_an_unknown_user_is_entity_not_found(tmp_path: Path) -> None:
    with TestClient(app_on(tmp_path)) as client:
        response = client.get("/api/v1/state/users/ghost")
    assert response.status_code == 404
    assert response.json()["message"] == cs.S_ENF.format(ref_list="user#ghost")


# -- NFR-6 + IR-05: concurrent turns through the one writer ---------------------------------------
def test_eight_concurrent_sessions_audit_every_call_with_no_gap_or_lock(tmp_path: Path) -> None:
    operators = 8
    app = app_on(tmp_path)
    with TestClient(app):
        use_cases = app.state.container.port(SessionUseCases)
        sids = [use_cases.create_session("role-operations").value.session_id for _ in range(8)]
        barrier = threading.Barrier(operators)
        results: dict[str, object] = {}

        def operator(sid: str) -> None:
            barrier.wait(timeout=30)
            results[sid] = use_cases.submit_query(sid, S1)

        threads = [threading.Thread(target=operator, args=(sid,)) for sid in sids]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

    assert all(is_ok(results[sid]) for sid in sids), results
    rows = raw_rows(tmp_path / "m12.db", "audit_records")
    per_turn = len(S1_TOOL_CALLS)
    assert len(rows) == operators * per_turn
    audit_ids = sorted(row[0] for row in rows)
    assert audit_ids == [f"aud-{n:016x}" for n in range(1, operators * per_turn + 1)]  # no gap
    tool_calls = sorted(row[0] for row in raw_rows(tmp_path / "m12.db", "tool_calls"))
    assert tool_calls == [f"tc-{n:016x}" for n in range(1, operators * per_turn + 1)]
    for sid in sids:  # each session sees exactly its own turn, in call order
        mine = sorted((r for r in rows if r[2] == sid), key=lambda r: (r[4], r[0]))
        assert [json.loads(r[5])["tool_name"] for r in mine] == S1_TOOL_CALLS
    answers = raw_rows(tmp_path / "m12.db", "answers")
    assert len(answers) == operators
    assert "database is locked" not in repr(results)
