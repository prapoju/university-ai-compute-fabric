"""Story 2.1 review D-1 - a destructive verb aimed at something unnamed is clarified, end to end.

Added after the red commit, so it lives beside the ATDD file instead of inside it. Real app, file
database. The point is what does NOT happen: no refusal that pretends the target was understood, no
proposal row, no gate token, no change to the estate.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import Settings
from src.domain import canonical_strings as cs

pytestmark = pytest.mark.api

SESSIONS = "/api/v1/sessions"
ESTATE = (
    "users",
    "catalog",
    "policy",
    "groups",
    "jobs",
    "nodes",
    "reservations",
    "windows",
    "events",
)


def app_on(tmp_path: Path) -> TestClient:
    settings = Settings.from_env({"M12_DB_PATH": str(tmp_path / "m12.db")})
    return TestClient(create_app(settings), raise_server_exceptions=False)


def estate(client: TestClient) -> dict:
    return {
        kind: client.get(f"/api/v1/state/{kind}", params={"page_size": 100}).json()["items"]
        for kind in ESTATE
    }


@pytest.mark.parametrize(
    "query",
    [
        "delete alex's jobs",
        "kill jobs 8823",
        "remove user alex",
        "delete them",
        "wipe the database",
    ],
)
def test_an_unnamed_target_is_clarified_and_changes_nothing(query: str, tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        before = estate(client)
        sid = client.post(SESSIONS, json={"operator_role": "role-operations"}).json()["session_id"]
        response = client.post(f"{SESSIONS}/{sid}/queries", json={"query_text": query})
        body = response.json()
        assert response.status_code == 200
        assert body["code"] == "CLARIFICATION_REQUIRED"
        assert body["message"] == cs.clarification(cs.R_MISSING_TARGET)
        assert "Action refused." not in response.text and "gt-" not in response.text
        assert estate(client) == before
        with client.app.state.container.writer.read() as db:
            assert db.execute("SELECT count(*) FROM proposals").fetchone()[0] == 0
