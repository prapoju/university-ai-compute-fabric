"""Story 1.2 - the real composition root serves the session API end to end (no overrides).

Covers the lifecycle over HTTP, persistence across a service restart on a file database, id
seeding after the restart, and the safe 503 behaviour when the database is unavailable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import Settings

pytestmark = pytest.mark.api

BASE = "/api/v1/sessions"
S1 = "why was alex denied deepseek-coder"


def client_for(**env: str) -> TestClient:
    settings = Settings.from_env({f"M12_{k.upper()}": v for k, v in env.items()})
    return TestClient(create_app(settings), raise_server_exceptions=False)


def test_the_full_lifecycle_works_through_the_real_container() -> None:
    with client_for() as client:
        created = client.post(BASE, json={"operator_role": "role-operations"})
        assert created.status_code == 201
        sid = created.json()["session_id"]
        assert (
            sid == "sess-0000000000000001"
            and created.json()["created_at"] == "2026-10-16T15:00:00.000Z"
        )

        answer = client.post(f"{BASE}/{sid}/queries", json={"query_text": S1}).json()["answers"][0]
        assert (answer["intent"], answer["answer_id"]) == (
            "diagnose_access_denial",
            "ans-0000000000000001",
        )

        session = client.get(f"{BASE}/{sid}").json()
        assert session["context"]["prior_intents"] == ["diagnose_access_denial"]
        assert [t["answer_id"] for t in session["turns"]] == ["ans-0000000000000001"]

        assert client.delete(f"{BASE}/{sid}").status_code == 204
        assert client.get(f"{BASE}/{sid}").json()["status"] == "reset"


def test_readiness_now_includes_the_session_store() -> None:
    with client_for() as client:
        body = client.get("/readyz").json()
    assert body["checks"]["sessions"] == "ok"


def test_sessions_and_turns_survive_a_restart_and_new_ids_never_collide(tmp_path: Path) -> None:
    database = str(tmp_path / "m12.db")
    with client_for(db_path=database) as first:
        sid = first.post(BASE, json={"operator_role": "role-operations"}).json()["session_id"]
        first.post(f"{BASE}/{sid}/queries", json={"query_text": S1})
        first.post(f"{BASE}/{sid}/queries", json={"query_text": "what's the weather?"})

    with client_for(db_path=database) as second:  # a brand-new process on the same file
        session = second.get(f"{BASE}/{sid}")
        assert session.status_code == 200
        assert [t["answer_id"] for t in session.json()["turns"]] == [
            "ans-0000000000000001",
            "ans-0000000000000002",
        ]
        assert session.json()["context"]["prior_intents"] == [
            "diagnose_access_denial",
            "clarification",
        ]
        # ids continue after everything already stored: no primary-key collision, no reuse
        new_sid = second.post(BASE, json={"operator_role": "role-operations"})
        assert (
            new_sid.status_code == 201 and new_sid.json()["session_id"] == "sess-0000000000000002"
        )
        answer = second.post(f"{BASE}/{sid}/queries", json={"query_text": S1})
        assert answer.json()["answers"][0]["answer_id"] == "ans-0000000000000003"


def test_an_unavailable_database_gives_503_on_every_session_route_and_not_ready(
    tmp_path: Path,
) -> None:
    unreachable = str(tmp_path / "no" / "such" / "dir" / "m12.db")
    with client_for(db_path=unreachable) as client:
        sid = "sess-0000000000000001"
        responses = [
            client.post(BASE, json={"operator_role": "role-operations"}),
            client.post(f"{BASE}/{sid}/queries", json={"query_text": S1}),
            client.get(f"{BASE}/{sid}"),
            client.delete(f"{BASE}/{sid}"),
        ]
        for response in responses:
            body = response.json()
            assert response.status_code == 503 and body["code"] == "PROVIDER_UNAVAILABLE"
            assert body["message"] == "Provider unavailable — cannot answer."
            assert "OperationalError" not in response.text
        ready = client.get("/readyz")
        assert ready.status_code == 503
        assert any(
            o.startswith("sessions:") for o in ready.json()["explanation"]["observed_values"]
        )
