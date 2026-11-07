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
from src.adapters.outbound.sim.clock_adapter import SimClock
from src.config import Settings
from src.domain import canonical_strings as cs
from src.ports.outbound import ClockPort, LlmProsePort

pytestmark = pytest.mark.api

SESSIONS = "/api/v1/sessions"
COPILOT = "/api/v1/copilot/query"
S1 = "Why was student Alex denied access to model deepseek-coder?"
S1_POLICY = "Why was student Alex denied access to model deepseek-coder under policy#catalog.4.2?"
S2 = "Why can't Group 4 run their fine-tuning job right now?"
EMPTY_CONTEXT = {"resolved_entities": [], "prior_intents": [], "active_answer_ids": []}
NOT_IN_A_FAILURE = {"answers", "claims", "evidence", "recommendation", "diagnosis_class"}
TURN_TABLES = ("answers", "tool_calls", "audit_records")

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


def row_counts(client: TestClient, tables: tuple[str, ...] = TURN_TABLES) -> dict[str, int]:
    with client.app.state.container.writer.read() as db:
        return {t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}


def normalized(answer: dict) -> str:
    """An answer without its id and with the clock read ids (one per request) neutralized."""
    shown = {k: v for k, v in answer.items() if k != "answer_id"}
    return re.sub(r"clk-[0-9a-f]{16}", "clk-N", json.dumps(shown, sort_keys=True))


def audit_ids(client: TestClient, sid: str) -> list[str]:
    page = client.get(f"{SESSIONS}/{sid}/audit").json()
    return [entry["audit_id"] for entry in page["entries"]]


def assert_safe_failure(response, code: str) -> None:
    """The safe-failure 503: canonical literal, retryable, no leaked reason, nothing fabricated."""
    body = response.json()
    assert response.status_code == 503
    assert body["code"] == code
    assert body["message"] == cs.S_PUA
    assert body["retryable"] is True
    # a 5xx never shows the adapter's reason
    assert body["explanation"]["observed_values"] == []
    assert not NOT_IN_A_FAILURE & set(body)
    assert "SimulatedOutage" not in response.text and "Traceback" not in response.text


def assert_nothing_persisted(client: TestClient, sid: str) -> None:
    assert row_counts(client) == {"answers": 0, "tool_calls": 0, "audit_records": 0}
    stored = client.get(f"{SESSIONS}/{sid}").json()
    assert stored["turns"] == [] and stored["context"] == EMPTY_CONTEXT


def healthy_baseline(directory: Path, query: str) -> tuple[dict, list[str]]:
    """The same query on a healthy app: the answer and the audit ids a clean first turn gives."""
    with app_on(directory) as clean:
        sid = open_session(clean)
        response = ask(clean, sid, query)
        assert response.status_code == 200
        return response.json()["answers"][0], audit_ids(clean, sid)


def assert_clean_recovery(
    client: TestClient, sid: str, query: str, baseline: tuple[dict, list[str]]
) -> None:
    """The same diagnosis as a healthy app; a failed turn burned no claim id and no audit id."""
    baseline_answer, baseline_audit = baseline
    again = ask(client, sid, query)
    assert again.status_code == 200
    answer = again.json()["answers"][0]
    assert normalized(answer) == normalized(baseline_answer)
    assert [c["claim_id"] for c in answer["claims"]] == [
        f"clm-{n:016x}" for n in range(1, len(answer["claims"]) + 1)
    ]
    assert audit_ids(client, sid) == baseline_audit
    assert audit_ids(client, sid)[0] == "aud-0000000000000001"


# -- AC 1, 2, 4, 5: one retrieval port down, typed or raised -------------------------------------
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
    baseline = healthy_baseline(tmp_path / "clean", query)

    with app_on(tmp_path) as client:
        sid = open_session(client)
        prose = client.app.state.container.port(LlmProsePort)
        prose_calls = prose.call_count

        fault.down()
        assert_safe_failure(ask(client, sid, query), "PROVIDER_UNAVAILABLE")
        assert prose.call_count == prose_calls  # aborted before prose
        assert client.get("/healthz").status_code == 200  # the app did not crash
        assert_nothing_persisted(client, sid)

        fault.recover()
        assert_clean_recovery(client, sid, query, baseline)


# -- AC 3, 4, 5: the clock down, typed or raised --------------------------------------------------
@pytest.mark.parametrize("query", [S1, S2], ids=["S1", "S2"])
@pytest.mark.parametrize(
    ("mode", "code"), [("typed", "CLOCK_UNAVAILABLE"), ("raises", "PROVIDER_UNAVAILABLE")]
)
def test_a_clock_outage_aborts_the_turn_and_recovery_is_clean(
    query: str, mode: str, code: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raising = PortFault(mode="raises")
    if mode == "raises":
        install(monkeypatch, SimClock, "now", raising)
    baseline = healthy_baseline(tmp_path / "clean", query)

    with app_on(tmp_path) as client:
        sid = open_session(client)  # opening a session reads the clock too: do it while it is up
        prose = client.app.state.container.port(LlmProsePort)
        prose_calls = prose.call_count

        clock = client.app.state.container.port(ClockPort)
        clock.fail() if mode == "typed" else raising.down()
        assert_safe_failure(ask(client, sid, query), code)
        assert prose.call_count == prose_calls
        assert_nothing_persisted(client, sid)

        clock.recover() if mode == "typed" else raising.recover()
        assert_clean_recovery(client, sid, query, baseline)


@pytest.mark.parametrize(
    ("mode", "code"), [("typed", "CLOCK_UNAVAILABLE"), ("raises", "PROVIDER_UNAVAILABLE")]
)
def test_opening_a_session_with_the_clock_down_is_the_safe_failure(
    mode: str, code: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raising = PortFault(mode="raises")
    if mode == "raises":
        install(monkeypatch, SimClock, "now", raising)
    with app_on(tmp_path) as client:
        clock = client.app.state.container.port(ClockPort)
        clock.fail() if mode == "typed" else raising.down()
        response = client.post(SESSIONS, json={"operator_role": "role-operations"})
        assert_safe_failure(response, code)
        assert row_counts(client, ("sessions",)) == {"sessions": 0}


# -- AC 6: the Annex 12.1 entry point -------------------------------------------------------------
def test_copilot_query_with_a_port_down_is_the_safe_failure_and_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fault = PortFault()
    install(monkeypatch, sim.SimPolicy, "for_model", fault)
    with app_on(tmp_path) as client:
        fault.down()
        assert_safe_failure(client.post(COPILOT, json={"query": S1}), "PROVIDER_UNAVAILABLE")
        # the session is opened before the turn, so an empty one may remain (story 4.2 D5):
        # what must not exist is any answer, tool call or audit row
        assert row_counts(client) == {"answers": 0, "tool_calls": 0, "audit_records": 0}
        fault.recover()
        recovered = client.post(COPILOT, json={"query": S1})
        assert recovered.status_code == 200
        assert recovered.json()["answers"][0]["diagnosis_class"] == "access_denial_not_in_allowlist"


def test_copilot_query_with_the_clock_down_creates_no_session_and_recovers(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        clock = client.app.state.container.port(ClockPort)
        clock.fail()
        assert_safe_failure(client.post(COPILOT, json={"query": S1}), "CLOCK_UNAVAILABLE")
        assert row_counts(client, ("sessions", *TURN_TABLES)) == {
            "sessions": 0, "answers": 0, "tool_calls": 0, "audit_records": 0,
        }  # fmt: skip
        clock.recover()
        assert client.post(COPILOT, json={"query": S1}).status_code == 200


# -- AC 7: the session-less read routes never answer 500 -----------------------------------------
def test_the_read_routes_answer_the_safe_failure_while_a_provider_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fault = PortFault(mode="raises")
    for cls, method in (
        (sim.SimUsers, "get"),
        (sim.SimUsers, "browse"),
        (sim.SimPolicy, "get"),
    ):
        install(monkeypatch, cls, method, fault)
    with app_on(tmp_path) as client:
        answered = ask(client, open_session(client), S1)  # while everything is up
        assert answered.status_code == 200
        answer_id = answered.json()["answers"][0]["answer_id"]
        assert client.get("/api/v1/state/users/alex").status_code == 200

        fault.down()
        for path in (
            "/api/v1/state/users/alex",
            "/api/v1/state/users",
            "/api/v1/citations/user%23alex",
            "/api/v1/citations/policy%23catalog.4.2",
        ):
            assert_safe_failure(client.get(path), "PROVIDER_UNAVAILABLE")
        # the evidence route reads the rows stored with the answer, not a provider
        assert client.get(f"/api/v1/answers/{answer_id}/evidence").status_code == 200

        fault.recover()
        assert client.get("/api/v1/state/users/alex").status_code == 200
