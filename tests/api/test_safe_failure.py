"""Story 4.2 - safe failure on the retrieval dependencies, through the real app (FR-16).

One retrieval port goes down at a time (a typed ``Failure`` or an unexpected exception). The turn
must abort before prose with the safe-failure 503 and leave nothing behind, and the same query must
succeed with the same diagnosis once the port recovers. The fault is a double at an outbound port
(``support.faults``); the app, pipeline, handlers, audit wrappers and routes are real.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from support.faults import Mode, PortFault, install

import src.adapters.outbound.sim.fixtures_adapter as sim
from src.adapters.inbound.app import create_app
from src.config import Settings
from src.domain import canonical_strings as cs
from src.ports.outbound import LlmProsePort

pytestmark = pytest.mark.api

SESSIONS = "/api/v1/sessions"
S1 = "Why was student Alex denied access to model deepseek-coder?"
S1_POLICY = "Why was student Alex denied access to model deepseek-coder under policy#catalog.4.2?"
S2 = "Why can't Group 4 run their fine-tuning job right now?"
EMPTY_CONTEXT = {"resolved_entities": [], "prior_intents": [], "active_answer_ids": []}
NOT_IN_A_FAILURE = {"answers", "claims", "evidence", "recommendation", "diagnosis_class"}

# (read point, Sim adapter class, method, a query that reaches it)
READ_POINTS = [
    ("users.get", sim.SimUsers, "get", S1),
    ("catalog.get", sim.SimCatalog, "get", S1),
    ("policy.for_model", sim.SimPolicy, "for_model", S1),
    ("event_store.query", sim.SimEventStore, "query", S1),
    ("policy.get", sim.SimPolicy, "get", S1_POLICY),
    ("groups.get", sim.SimGroups, "get", S2),
    ("jobs.select", sim.SimJobs, "select", S2),
    ("windows.list", sim.SimWindows, "list", S2),
]


def app_on(directory: Path) -> TestClient:
    directory.mkdir(parents=True, exist_ok=True)
    settings = Settings.from_env({"M12_DB_PATH": str(directory / "m12.db")})
    return TestClient(create_app(settings), raise_server_exceptions=False)


def open_session(client: TestClient) -> str:
    created = client.post(SESSIONS, json={"operator_role": "role-operations"})
    assert created.status_code == 201
    return created.json()["session_id"]


def ask(client: TestClient, sid: str, query: str):
    return client.post(f"{SESSIONS}/{sid}/queries", json={"query_text": query})


def row_counts(client: TestClient) -> dict[str, int]:
    with client.app.state.container.writer.read() as db:
        return {
            table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("answers", "tool_calls", "audit_records")
        }


def normalized(answer: dict) -> str:
    """An answer without its id and with the clock read ids (one per request) neutralized."""
    shown = {k: v for k, v in answer.items() if k != "answer_id"}
    return re.sub(r"clk-[0-9a-f]{16}", "clk-N", json.dumps(shown, sort_keys=True))


def audit_ids(client: TestClient, sid: str) -> list[str]:
    page = client.get(f"{SESSIONS}/{sid}/audit").json()
    return [entry["audit_id"] for entry in page["entries"]]


@pytest.mark.parametrize("mode", ["failure", "raises"])
@pytest.mark.parametrize(
    ("point", "cls", "method", "query"), READ_POINTS, ids=[p[0] for p in READ_POINTS]
)
def test_a_port_outage_aborts_the_turn_and_recovery_is_clean(
    point: str,
    cls: type,
    method: str,
    query: str,
    mode: Mode,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fault = PortFault(mode=mode)
    install(monkeypatch, cls, method, fault)  # before create_app: audited() binds at build time

    with app_on(tmp_path / "clean") as clean:  # the same query on a healthy app is the baseline
        baseline_sid = open_session(clean)
        baseline = ask(clean, baseline_sid, query)
        assert baseline.status_code == 200
        baseline_answer = baseline.json()["answers"][0]
        baseline_audit = audit_ids(clean, baseline_sid)

    with app_on(tmp_path) as client:
        sid = open_session(client)
        prose = client.app.state.container.port(LlmProsePort)
        prose_calls = prose.call_count

        fault.down()
        failed = ask(client, sid, query)

        # AC 1 and 2: the safe-failure 503, never a 500, and nothing fabricated in the body
        body = failed.json()
        assert failed.status_code == 503
        assert body["code"] == "PROVIDER_UNAVAILABLE"
        assert body["message"] == cs.S_PUA
        assert body["retryable"] is True
        # a 5xx never shows the adapter's reason
        assert body["explanation"]["observed_values"] == []
        assert not NOT_IN_A_FAILURE & set(body)
        assert "SimulatedOutage" not in failed.text and "Traceback" not in failed.text
        assert prose.call_count == prose_calls  # aborted before prose
        assert client.get("/healthz").status_code == 200  # the app did not crash

        # AC 4: nothing persisted, no audit row, the session context untouched
        assert row_counts(client) == {"answers": 0, "tool_calls": 0, "audit_records": 0}
        stored = client.get(f"{SESSIONS}/{sid}").json()
        assert stored["turns"] == [] and stored["context"] == EMPTY_CONTEXT

        # AC 5: once the port is back the same query gives the same diagnosis, claim ids and
        # audit ids start at 1 (a failed turn burns neither)
        fault.recover()
        again = ask(client, sid, query)
        assert again.status_code == 200
        answer = again.json()["answers"][0]
        assert normalized(answer) == normalized(baseline_answer)
        assert [c["claim_id"] for c in answer["claims"]] == [
            f"clm-{n:016x}" for n in range(1, len(answer["claims"]) + 1)
        ]
        assert audit_ids(client, sid) == baseline_audit
        assert audit_ids(client, sid)[0] == "aud-0000000000000001"
