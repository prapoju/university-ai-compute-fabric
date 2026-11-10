"""Story 1.6 ATDD (red phase) - concurrent multi-tool diagnostics, on the real app.

Written BEFORE any production code, against the real app: ``create_app(Settings.from_env(...))``
on a file database, the real fixtures, the simulated clock and the simulated prose writer. The
only doubles are at outbound ports, installed on the Sim adapter classes BEFORE ``create_app``
(``bootstrap`` binds each port method once, through ``audited()``):

* ``Gate`` forces the completion order of the two independent reads (``policy.for_model`` and
  ``event_store.query``, review D-2.1). It waits on ``threading.Event`` / ``threading.Barrier``
  with an upper bound, so an implementation that cannot overlap the reads fails instead of
  hanging. Nothing sleeps.
* ``PortFault`` (``support/faults.py``) makes a read raise, for the typed-503 case.

Every case asserts resulting state and what did not happen. Cases marked ``regression guard``
already pass on the current sequential behaviour and must stay unchanged. The rest fail until
the dispatcher exists.

Not covered here, on purpose: the k6 run itself (an external process; only the script is checked
statically), the route-audit assertion (added in the dev step, per the approved plan), and the
cross-store interleaving case, which belongs to the writer's integration suite.

Cases come from ``planning/epics.md`` story 1.6, ``test/test-design.md`` 6.3.5 and the review
decisions D-2.1 to D-2.6. The two independent reads are the only ones that can overlap (review
section 2), so the seeded permutations of the test design reduce to the two completion orders.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from support.faults import PortFault, install

from src.adapters.inbound.app import create_app
from src.adapters.outbound.sim.clock_adapter import SimClock
from src.adapters.outbound.sim.fixtures_adapter import SimEventStore, SimPolicy
from src.config import PROJECT_ROOT, ConfigError, Settings
from src.domain import canonical_strings as cs
from src.domain.result import Failure

pytestmark = pytest.mark.api

COPILOT_QUERY = "/api/v1/copilot/query"
SESSIONS = "/api/v1/sessions"
S1 = "Why was student Alex denied access to model deepseek-coder?"
S1_TOOL_CALLS = [
    "toolcall.users_port.get",
    "toolcall.catalog_port.get",
    "toolcall.policy_port.for_model",
    "toolcall.event_store_port.query",
]
LOAD_SCRIPT = PROJECT_ROOT / "tests" / "nfr" / "copilot-load.js"
WAIT = 2.0  # upper bound on every gate: a build that cannot overlap the reads fails, not hangs


class GateNeverOpened(RuntimeError):
    """A read waited for a gate that never opened: the reads ran one after the other."""


class Gate:
    """Forces the completion order of the two independent reads of one S1 turn (review D-2.1).

    ``order``: ``none`` (no constraint), ``forward`` (policy completes before events),
    ``reverse`` (events completes before policy), ``together`` (both reads must be in flight at
    once, through a barrier), ``stall`` (events does not return until ``release`` is set).
    ``failing`` names the reads that return a typed ``Failure`` instead of their value.
    """

    def __init__(self) -> None:
        self.order = "none"
        self.failing: set[str] = set()
        self.policy_done = threading.Event()
        self.events_done = threading.Event()
        self.release = threading.Event()
        self.together = threading.Barrier(2, timeout=WAIT)
        self.started: list[str] = []
        self.stalls: list[str] = []  # gates that never opened: the reads did not run as ordered
        self._lock = threading.Lock()

    def begin(self, order: str) -> None:
        self.order = order
        self.failing = set()
        self.started = []
        self.stalls = []
        for event in (self.policy_done, self.events_done, self.release):
            event.clear()
        self.together = threading.Barrier(2, timeout=WAIT)

    def enter(self, name: str) -> None:
        with self._lock:
            self.started.append(name)

    def await_(self, event: threading.Event, message: str) -> None:
        if not event.wait(WAIT):
            self.stalls.append(message)
            raise GateNeverOpened(message)

    def meet(self) -> None:
        try:
            self.together.wait()
        except threading.BrokenBarrierError:
            self.stalls.append("the policy and events reads were never in flight at once")
            raise


def _gated_policy(gate: Gate, original):
    def for_model(self, *args, **kwargs):
        gate.enter("policy")
        if gate.order == "together":
            gate.meet()
        if gate.order == "reverse":
            gate.await_(
                gate.events_done, "reverse order: the policy read waited for the events read"
            )
        result = (
            Failure("PROVIDER_UNAVAILABLE", observed=("policy read",))
            if "policy" in gate.failing
            else original(self, *args, **kwargs)
        )
        gate.policy_done.set()
        return result

    return for_model


def _gated_events(gate: Gate, original):
    def query(self, *args, **kwargs):
        gate.enter("events")
        if gate.order == "together":
            gate.meet()
        if gate.order == "forward":
            gate.await_(
                gate.policy_done, "forward order: the events read waited for the policy read"
            )
        if gate.order == "stall":
            gate.await_(gate.release, "stall: the events read waited for the test to release it")
        result = (
            Failure("PROVIDER_UNAVAILABLE", observed=("events read",))
            if "events" in gate.failing
            else original(self, *args, **kwargs)
        )
        gate.events_done.set()
        return result

    return query


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Gate:
    """Installed on the Sim classes before any app is built in the test."""
    forced = Gate()
    monkeypatch.setattr(SimPolicy, "for_model", _gated_policy(forced, SimPolicy.for_model))
    monkeypatch.setattr(SimEventStore, "query", _gated_events(forced, SimEventStore.query))
    return forced


@pytest.fixture
def clock_reads(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """One entry per ``SimClock.now`` call, installed before any app is built."""
    reads: list[int] = []
    original = SimClock.now

    def counted(self):
        reads.append(1)
        return original(self)

    monkeypatch.setattr(SimClock, "now", counted)
    return reads


# -- helpers -----------------------------------------------------------------------------------
def app_on(tmp_path: Path, **env: str):
    variables = {
        "M12_DB_PATH": str(tmp_path / "m12.db"),
        **{f"M12_{k.upper()}": v for k, v in env.items()},
    }
    try:
        settings = Settings.from_env(variables)
    except ConfigError as exc:
        pytest.fail(f"configuration is not supported yet: {exc}", pytrace=False)
    return create_app(settings)


def copilot(client: TestClient, query: str = S1):
    return client.post(COPILOT_QUERY, json={"query": query})


def shape(answer: dict) -> dict:
    """What a turn returns, without the ids the process counters hand out (clock included)."""
    evidence = [e for e in answer["evidence"] if e["source_type"] != "clock"]
    return {
        "evidence": [
            (e["citation_id"], e["source_type"], e["snippet"], e["position"])
            for e in evidence
        ],
        "claims": [(c["text"], c["claim_citations"]) for c in answer["claims"]],
        "chain": answer["answer_chain"],
        "diagnosis_class": answer["diagnosis_class"],
    }


def open_session(client: TestClient) -> str:
    created = client.post(SESSIONS, json={"operator_role": "role-operations"})
    assert created.status_code == 201, created.json()
    return created.json()["session_id"]


def turn(client: TestClient, sid: str, query: str = S1):
    return client.post(f"{SESSIONS}/{sid}/queries", json={"query_text": query})


def audit_entries(client: TestClient, sid: str) -> list[dict]:
    response = client.get(f"{SESSIONS}/{sid}/audit", params={"page_size": 100})
    assert response.status_code == 200, response.json()
    return response.json()["entries"]


def turn_entries(client: TestClient, sid: str) -> list[dict]:
    """The tool calls of the turn, without the ``toolcall.answer_query`` row."""
    return [
        e for e in audit_entries(client, sid)
        if e["result_summary"]["tool_name"] != "toolcall.answer_query"
    ]  # fmt: skip


def tool_names(client: TestClient, sid: str) -> list[str]:
    return [e["result_summary"]["tool_name"] for e in turn_entries(client, sid)]


def ordinal(tool_call_id: str) -> int:
    return int(tool_call_id.rsplit("-", 1)[1], 16)  # the ids are hexadecimal (tc-000000000000000a)


def raw_count(database: Path, table: str) -> int:
    connection = sqlite3.connect(database)
    try:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        connection.close()


# -- AC 4: the budget is a setting with a documented default -----------------------------------
def test_the_fan_out_budget_defaults_to_half_a_second() -> None:
    try:
        settings = Settings.from_env({})
    except ConfigError as exc:
        pytest.fail(f"configuration is not supported yet: {exc}", pytrace=False)
    assert getattr(settings, "tool_fanout_budget_seconds", None) == 0.5, (
        "M12_TOOL_FANOUT_BUDGET_SECONDS must exist and default to 0.5 s (log I2-35)"
    )


# -- AC 1: the independent reads run concurrently ----------------------------------------------
def test_the_policy_and_events_reads_are_in_flight_at_the_same_time(
    tmp_path: Path, gate: Gate
) -> None:
    # an explicit wall budget that cannot expire while the gates order the reads
    client = TestClient(
        app_on(tmp_path, tool_fanout_budget_seconds="5"), raise_server_exceptions=False
    )
    gate.begin("together")
    response = copilot(client)
    assert not gate.stalls, gate.stalls
    assert response.status_code == 200, (
        f"both reads must be in flight at once; got {response.status_code} "
        f"(the sequential path cannot pass the barrier)"
    )


# -- AC 1 + EvidenceSet order: the sequential order under every completion order ----------------
def test_the_evidence_matches_the_sequential_order_under_forward_and_reverse_completion(
    tmp_path: Path, gate: Gate
) -> None:
    # an explicit wall budget that cannot expire while the gates order the reads
    client = TestClient(
        app_on(tmp_path, tool_fanout_budget_seconds="5"), raise_server_exceptions=False
    )
    shapes: dict[str, dict] = {}
    for order in ("none", "forward", "reverse"):
        gate.begin(order)
        response = copilot(client)
        assert not gate.stalls, f"{order} completion: {gate.stalls}"
        assert response.status_code == 200, (
            f"{order} completion: HTTP {response.status_code}, expected 200"
        )
        answer = response.json()["answers"][0]
        positions = [e["position"] for e in answer["evidence"]]
        assert positions == list(range(len(positions))), f"{order}: positions {positions}"
        shapes[order] = shape(answer)
    assert shapes["forward"] == shapes["none"], "forward completion changed the evidence"
    assert shapes["reverse"] == shapes["none"], "reverse completion changed the evidence"


# -- B-04: the recorder slots are reserved from the arguments, before the gather ---------------
def test_the_audit_lists_the_tool_calls_in_argument_order_whatever_the_completion_order(
    tmp_path: Path, gate: Gate
) -> None:
    # an explicit wall budget that cannot expire while the gates order the reads
    client = TestClient(
        app_on(tmp_path, tool_fanout_budget_seconds="5"), raise_server_exceptions=False
    )
    for order in ("forward", "reverse"):
        gate.begin(order)
        response = copilot(client)
        assert not gate.stalls, f"{order} completion: {gate.stalls}"
        assert response.status_code == 200, f"{order}: HTTP {response.status_code}"
        sid = response.json()["answers"][0]["session_id"]
        assert tool_names(client, sid) == S1_TOOL_CALLS, f"{order} completion"


def test_the_tool_call_ids_are_minted_in_fixed_order_under_both_completion_orders(
    tmp_path: Path, gate: Gate
) -> None:
    # an explicit wall budget that cannot expire while the gates order the reads
    client = TestClient(
        app_on(tmp_path, tool_fanout_budget_seconds="5"), raise_server_exceptions=False
    )
    for order in ("forward", "reverse"):
        gate.begin(order)
        response = copilot(client)
        assert not gate.stalls, f"{order} completion: {gate.stalls}"
        assert response.status_code == 200, f"{order}: HTTP {response.status_code}"
        sid = response.json()["answers"][0]["session_id"]
        entries = turn_entries(client, sid)
        ids = [ordinal(e["tool_call_id"]) for e in entries]
        first = ids[0]
        assert [i - first for i in ids] == [0, 1, 2, 3], (
            f"{order} completion minted tool-call ids {ids}, expected consecutive in argument order"
        )
        names = [e["result_summary"]["tool_name"] for e in entries]
        assert names == S1_TOOL_CALLS, f"{order} completion: the ids follow the completion order"


# -- AC 2: a fan-out past its wall budget is the typed 503, with no partial evidence -----------
def test_a_fan_out_past_its_budget_checks_status_code_and_clock_count(
    tmp_path: Path, gate: Gate, clock_reads: list[int]
) -> None:
    app = app_on(tmp_path, tool_fanout_budget_seconds="0.2")
    client = TestClient(app, raise_server_exceptions=False)
    sid = open_session(client)
    clock_reads.clear()
    gate.begin("stall")
    try:
        response = turn(client, sid)
    finally:
        gate.release.set()
    body = response.json()
    assert response.status_code == 503, f"HTTP {response.status_code}, expected 503"
    assert (body["code"], body["message"]) == ("PROVIDER_UNAVAILABLE", cs.S_PUA)
    assert "answers" not in body and "claims" not in body, "partial evidence was rendered"
    assert len(clock_reads) == 1, f"the budget read the clock: {len(clock_reads)} reads"


# -- AC 2: the budget is wall time, so each turn still takes exactly one clock read ------------
def test_each_turn_takes_exactly_one_clock_read_whatever_the_completion_order(
    tmp_path: Path, gate: Gate, clock_reads: list[int]
) -> None:
    # an explicit wall budget that cannot expire while the gates order the reads
    client = TestClient(
        app_on(tmp_path, tool_fanout_budget_seconds="5"), raise_server_exceptions=False
    )
    sid = open_session(client)  # opening a session reads the clock too; only the turn is counted
    for order in ("none", "forward", "reverse"):
        gate.begin(order)
        clock_reads.clear()
        response = turn(client, sid)
        assert not gate.stalls, f"{order} completion: {gate.stalls}"
        assert response.status_code == 200, f"{order}: HTTP {response.status_code}"
        assert len(clock_reads) == 1, f"{order} completion took {len(clock_reads)} clock reads"


# -- F-6 (review): a read still running at the budget is a 503, and records nothing later ------
def test_a_read_still_running_at_the_budget_is_a_503_and_records_nothing_afterwards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No wall-clock assertion: the read is blocked on an event. The 503 must arrive while the read
    has not returned, and a read that finishes afterwards must add no tool call to the audit."""
    released = threading.Event()  # the test decides when the blocked read may return
    finished = threading.Event()  # set by the read after it returned, so the test can wait for it
    original = SimEventStore.query

    def blocked(self, *args, **kwargs):
        released.wait(WAIT)
        result = original(self, *args, **kwargs)
        finished.set()
        return result

    monkeypatch.setattr(SimEventStore, "query", blocked)
    app = app_on(tmp_path, tool_fanout_budget_seconds="0.05")
    client = TestClient(app, raise_server_exceptions=False)
    sid = open_session(client)
    response = turn(client, sid)
    assert not finished.is_set(), "the 503 arrived only after the blocked read had returned"
    assert response.status_code == 503, f"HTTP {response.status_code}, expected 503"
    assert response.json()["code"] == "PROVIDER_UNAVAILABLE"
    released.set()
    assert finished.wait(WAIT), "the blocked read never finished"
    assert audit_entries(client, sid) == [], "a read that outlived the turn recorded a tool call"


# -- F-7 (review): each read raising alone, and both raising, is one typed 503 -----------------
def test_an_events_read_that_raises_gives_the_typed_503_body_with_its_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(monkeypatch, SimEventStore, "query", PortFault(mode="raises", active=True))
    client = TestClient(app_on(tmp_path), raise_server_exceptions=False)
    response = copilot(client)
    assert response.status_code == 503, f"HTTP {response.status_code}, expected 503"
    assert response.json()["code"] == "PROVIDER_UNAVAILABLE"


def test_both_reads_that_raise_are_one_typed_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(monkeypatch, SimPolicy, "for_model", PortFault(mode="raises", active=True))
    install(monkeypatch, SimEventStore, "query", PortFault(mode="raises", active=True))
    client = TestClient(app_on(tmp_path), raise_server_exceptions=False)
    response = copilot(client)
    assert response.status_code == 503, f"HTTP {response.status_code}, expected 503"
    assert response.json()["code"] == "PROVIDER_UNAVAILABLE"


# -- AC 2: a read that raises gives the typed 503 body ---------------------------------------------
def test_a_read_that_raises_gives_the_typed_503_body_with_its_code(  # regression guard (AD-12)
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(monkeypatch, SimPolicy, "for_model", PortFault(mode="raises", active=True))
    client = TestClient(app_on(tmp_path), raise_server_exceptions=False)
    response = copilot(client)
    assert response.status_code == 503, f"HTTP {response.status_code}, expected 503"
    assert response.json()["code"] == "PROVIDER_UNAVAILABLE"


# -- AC 2 + D-2.4: two failures report the first in argument order, in both completion orders --
def test_two_failing_reads_report_the_same_body_in_both_completion_orders(
    tmp_path: Path, gate: Gate
) -> None:
    # an explicit wall budget that cannot expire while the gates order the reads
    client = TestClient(
        app_on(tmp_path, tool_fanout_budget_seconds="5"), raise_server_exceptions=False
    )
    bodies = {}
    for order in ("forward", "reverse"):
        gate.begin(order)
        gate.failing = {"policy", "events"}
        response = copilot(client)
        assert not gate.stalls, f"{order} completion: {gate.stalls}"
        assert response.status_code == 503, f"{order}: HTTP {response.status_code}, expected 503"
        bodies[order] = response.json()
    assert bodies["forward"] == bodies["reverse"], "the failure depends on completion order"
    assert bodies["forward"]["code"] == "PROVIDER_UNAVAILABLE"


# -- AC 1 (AD-1): no tool call writes ----------------------------------------------------------
# regression guard (AD-1)
def test_every_tool_call_of_the_s1_turn_is_a_read(tmp_path: Path) -> None:
    client = TestClient(app_on(tmp_path), raise_server_exceptions=False)
    response = copilot(client)
    assert response.status_code == 200
    sid = response.json()["answers"][0]["session_id"]
    assert tool_names(client, sid) == S1_TOOL_CALLS


# -- AC 3: 50 operators, released together on one file database --------------------------------
def test_fifty_operators_released_together_get_cited_answers_and_no_lock_errors(  # regression guard
    tmp_path: Path,
) -> None:
    database = tmp_path / "m12.db"
    app = app_on(tmp_path)
    clients = [TestClient(app, raise_server_exceptions=False) for _ in range(50)]
    release = threading.Barrier(50, timeout=WAIT * 5)

    def operator(client: TestClient):
        release.wait()
        return copilot(client)

    with ThreadPoolExecutor(max_workers=50) as pool:
        responses = list(pool.map(operator, clients))

    statuses = [r.status_code for r in responses]
    assert statuses.count(200) == 50, f"statuses: {sorted(set(statuses))}"
    answers = [r.json()["answers"][0] for r in responses]
    assert len({a["answer_id"] for a in answers}) == 50, "answer ids are not distinct"
    for answer in answers:
        cited = {c for claim in answer["claims"] for c in claim["claim_citations"]}
        assert {"policy#catalog.4.2", "model#deepseek-coder"} <= cited
        assert "RULE-CAT-04" in json.dumps(answer), "RULE-CAT-04 is not in the answer"
    assert raw_count(database, "tool_calls") == 50 * (len(S1_TOOL_CALLS) + 1), (
        "audit rows are missing or duplicated"
    )
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        connection.close()


# -- AC 3, AC 5: the k6 script holds the story's budget and never sleeps -----------------------
def test_the_load_script_declares_the_story_thresholds_and_never_sleeps() -> None:
    assert LOAD_SCRIPT.exists(), "tests/nfr/copilot-load.js does not exist yet"
    text = LOAD_SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"\bvus\s*:\s*50\b", text), "the script must run 50 VUs"
    assert re.search(r"http_req_failed['\"]?\s*:\s*\[\s*['\"]rate==0['\"]", text)
    assert re.search(r"http_req_duration['\"]?\s*:\s*\[\s*['\"]p\(95\)<800['\"]", text)
    assert re.search(r"checks['\"]?\s*:\s*\[\s*['\"]rate==1", text)
    for citation in ("RULE-CAT-04", "policy#catalog.4.2", "deepseek-coder"):
        assert citation in text, f"the script must check {citation}"
    assert not re.search(r"\bsleep\s*\(", text), "k6 must not pause with a sleep call"
