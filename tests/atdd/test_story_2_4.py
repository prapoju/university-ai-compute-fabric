"""Story 2.4 ATDD (red phase) - the executor and the dispatch, Annex 12.4.

Written BEFORE any production code, port, adapter or contract change, against the real app:
``create_app(Settings.from_env(...))`` on a file database, the real fixtures, the simulated clock
and the simulated prose writer. The executor is the simulated one that the app wires; its controls
(``down``, ``delay_seconds``, ``apply_only``, ``extra_applied``, ``calls``, ``requests``) are the
story's test seam and are reached through ``ExecutorPort`` lazily, so a missing port is a failed
case and not a collection error. The only other doubles are a switch on ``SimJobs.select`` and a
``SqliteAuditStore.append`` that fails on its Nth call, both at outbound ports and installed before
``create_app``. Time is the real ``SimClock``, moved with ``advance`` or by the executor's simulated
latency; nothing sleeps. Literals are written out on purpose: the codes, the statuses, the applied
records, the audit order and the frozen field set are the contract.

Cases come from the story ("ATDD cases"), ``test/test-design.md`` 6.3.4 and the stub suite
``test/atdd/module12_contracts.test.py``, which is never imported. Cases marked ``regression guard``
already pass on earlier behaviour and must stay unchanged.
"""

from __future__ import annotations

import copy
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

import src.adapters.outbound.sim.fixtures_adapter as sim
from src.adapters.inbound.app import create_app
from src.adapters.outbound.db.audit_store import SqliteAuditStore
from src.config import PROJECT_ROOT, ConfigError, Settings
from src.domain.result import Failure, Ok
from src.dto import ProposalDTO
from src.ports.outbound import ClockPort

pytestmark = pytest.mark.api

SESSIONS = "/api/v1/sessions"
COPILOT_QUERY = "/api/v1/copilot/query"
COPILOT_CHAT = "/api/v1/copilot/chat"
DRY_RUNS = "/api/v1/destructive/dry-runs"
PROPOSALS = "/api/v1/destructive/proposals"
EXECUTOR = "/executor/v1/proposals"
CLOCK = "2026-10-16T15:00:00.000Z"
TOKEN = re.compile(r"^gt-[0-9a-f]{32}$")
ESTATE_TYPES = (
    "users", "catalog", "policy", "groups", "jobs", "nodes", "reservations", "windows", "events"
)  # fmt: skip

ANNEX = "Terminate all active jobs for CS-101"
ANNEX_KEYS = ["job#job-8901", "job#job-8902", "job#job-8903"]
OTHER_TOKEN = "gt-" + "ab" * 16
FROZEN_FIELDS = {"proposal_id", "action", "selector", "gate_token", "dry_run_ref"}
CONTRACT = PROJECT_ROOT / "planning" / "detailed-design" / "schemas" / "openapi.yaml"


# -- helpers -----------------------------------------------------------------------------------
def app_on(tmp_path: Path, **env: str) -> TestClient:
    variables = {
        "M12_DB_PATH": str(tmp_path / "m12.db"),
        **{f"M12_{k.upper()}": v for k, v in env.items()},
    }
    try:
        settings = Settings.from_env(variables)
    except ConfigError as exc:
        pytest.fail(f"configuration is not supported: {exc}")
    return TestClient(create_app(settings), raise_server_exceptions=False)


def executor(client: TestClient):
    """The simulated executor the app wires, or a failed case when there is none yet."""
    try:
        from src.ports.outbound import ExecutorPort
    except ImportError:
        pytest.fail("src.ports.outbound.ExecutorPort does not exist yet", pytrace=False)
    return client.app.state.container.port(ExecutorPort)


def clock(client: TestClient):
    return client.app.state.container.port(ClockPort)


def open_session(client: TestClient) -> str:
    created = client.post(SESSIONS, json={"operator_role": "role-operations"})
    assert created.status_code == 201
    return created.json()["session_id"]


def estate(client: TestClient) -> dict:
    state: dict = {}
    for kind in ESTATE_TYPES:
        items: list = []
        page = 1
        while True:
            params = {"page": page, "page_size": 100}
            body = client.get(f"/api/v1/state/{kind}", params=params).json()
            items += body["items"]
            if len(body["items"]) < 100:
                break
            page += 1
        state[kind] = items
    return state


def with_jobs(before: dict, keys: list[str], **changes) -> dict:
    """``before`` with the named jobs changed: what the executor is expected to have done."""
    after = copy.deepcopy(before)
    for record in after["jobs"]:
        if record["id"] in keys:
            record.update(changes)
    return after


def rows(client: TestClient) -> list[dict]:
    columns = (
        "proposal_id, session_id, state, action, supersedes_proposal_id, confirmed_at, "
        "executor_status, applied_count, executor_timestamp, gate_token"
    )
    with client.app.state.container.writer.read() as db:
        cursor = db.execute(f"SELECT {columns} FROM proposals ORDER BY proposal_id")
        names = [d[0] for d in cursor.description]
        return [dict(zip(names, r, strict=True)) for r in cursor.fetchall()]


def row(client: TestClient, proposal_id: str) -> dict:
    found = [r for r in rows(client) if r["proposal_id"] == proposal_id]
    assert len(found) == 1
    return found[0]


def audit(client: TestClient, sid: str) -> list[dict]:
    params = {"page": 1, "page_size": 100}
    return client.get(f"{SESSIONS}/{sid}/audit", params=params).json()["entries"]


def tools(client: TestClient, sid: str) -> list[str]:
    return [e["result_summary"]["tool_name"] for e in audit(client, sid)]


def dry_run(client: TestClient, query: str = ANNEX) -> dict:
    response = client.post(COPILOT_CHAT, json={"query": query})
    assert response.status_code == 200 and "proposal" in response.json()
    return response.json()["proposal"]


def dry_run_route(client: TestClient, action: str, refs: list[str]) -> dict:
    body = {
        "query_text": "cancel", "action": action, "target_refs": refs,
        "session_id": open_session(client),
    }  # fmt: skip
    response = client.post(DRY_RUNS, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client: TestClient, proposal: dict, token: str | None = None):
    body = {"proposal_id": proposal["proposal_id"], "gate_token": token or proposal["gate_token"]}
    return client.post(PROPOSALS, json=body)


def get_proposal(client: TestClient, proposal_id: str):
    return client.get(f"{PROPOSALS}/{proposal_id}")


def force_state(client: TestClient, proposal_id: str, *states: str) -> None:
    """Walk a stored proposal through the states a request cannot hold still (trigger order)."""
    with client.app.state.container.writer.transaction() as db:
        for state in states:
            if state == "confirmed":
                db.execute(
                    "UPDATE proposals SET state = 'confirmed', confirmed_at = ?"
                    " WHERE proposal_id = ?",
                    (CLOCK, proposal_id),
                )
            else:
                db.execute(
                    "UPDATE proposals SET state = ? WHERE proposal_id = ?", (state, proposal_id)
                )


def executor_body(proposal: dict, **override) -> dict:
    body = {
        "proposal_id": proposal["proposal_id"],
        "action": proposal["action"],
        "selector": proposal["dry_run_snapshot"]["selector"],
        "gate_token": proposal["gate_token"],
        "dry_run_ref": {"proposal_id": proposal["proposal_id"]},
    }
    return {**body, **override}


@dataclass
class JobsDouble:
    frozen: object = (
        None  # a result to answer instead of the live select (the re-validation window)
    )
    capture_next: bool = False
    captured: object = None


def install_jobs(monkeypatch: pytest.MonkeyPatch) -> JobsDouble:
    switch = JobsDouble()
    original = sim.SimJobs.select

    def select(self, selector):
        result = original(self, selector)
        if switch.capture_next and not isinstance(result, Failure):
            switch.captured, switch.capture_next = result, False
        return switch.frozen if switch.frozen is not None else result

    monkeypatch.setattr(sim.SimJobs, "select", select)
    return switch


class NthAppendFails:
    """``SqliteAuditStore.append`` fails on its Nth call after ``arm``; the others run."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.armed, self.seen, self.n = False, 0, 0
        original = SqliteAuditStore.append

        def append(store, entries):
            if self.armed:
                self.seen += 1
                if self.seen == self.n:
                    return Failure("PROVIDER_UNAVAILABLE", observed=("simulated audit outage",))
            return original(store, entries)

        monkeypatch.setattr(SqliteAuditStore, "append", append)

    def arm(self, nth: int) -> None:
        self.armed, self.seen, self.n = True, 0, nth


# -- AC 1, 4: the Annex scenario runs to `executed` -----------------------------------------------
def test_the_annex_runs_to_executed_and_only_the_three_jobs_change(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        before = estate(client)
        response = confirm(client, proposal)
        assert response.status_code == 200
        try:
            done = ProposalDTO.model_validate(response.json())
        except ValidationError as exc:
            pytest.fail(f"the reply is not a contract Proposal: {exc}")
        assert done.state == "executed"
        assert done.confirmation is not None and done.confirmation.confirmed_at == CLOCK
        result = done.executor_result
        assert result is not None
        assert (result.status, result.applied_records, result.applied_count, result.source) == (
            "applied", ANNEX_KEYS, 3, "executor",
        )  # fmt: skip
        stored = row(client, proposal["proposal_id"])
        assert (stored["state"], stored["executor_status"], stored["applied_count"]) == (
            "executed", "applied", 3,
        )  # fmt: skip
        for key in ("job-8901", "job-8902", "job-8903"):
            assert client.get(f"/api/v1/state/jobs/{key}").json()["status"] == "cancelled"
        assert estate(client) == with_jobs(before, ANNEX_KEYS, status="cancelled")


def test_the_session_audit_tells_the_copilots_rows_from_the_executors(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        sid = proposal["session_id"]
        clock(client).advance(seconds=7)
        assert confirm(client, proposal).status_code == 200
        entries = audit(client, sid)
        assert [e["result_summary"]["tool_name"] for e in entries] == [
            "toolcall.answer_query", "toolcall.groups_port.get",
            "toolcall.propose_destructive_action", "toolcall.groups_port.get",
            "toolcall.jobs_port.select",
            "toolcall.confirm_and_dispatch", "toolcall.jobs_port.select",
            "executor.dispatch",
        ]  # fmt: skip
        mine = [e for e in entries if e["actor"] == "executor"]
        assert len(mine) == 1
        last = mine[0]
        assert last["tool_call_id"] is None and last["proposal_id"] == proposal["proposal_id"]
        assert last["result_summary"]["status"] == "applied"
        assert last["result_summary"]["applied_count"] == 3
        assert {e["actor"] for e in entries if e is not last} == {"copilot"}
        assert proposal["gate_token"] not in str(entries)


def test_the_executor_takes_its_own_clock_read_for_its_timestamp(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        executor(client).delay_seconds = 3
        body = confirm(client, proposal).json()
        assert body["confirmation"]["confirmed_at"] == CLOCK
        assert body["executor_result"]["timestamp"] == "2026-10-16T15:00:03.000Z"


# -- AC 2: only the executor mutates --------------------------------------------------------------
def test_regression_guard_a_dry_run_and_a_stale_confirm_change_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = install_jobs(monkeypatch)
    with app_on(tmp_path) as client:
        before = estate(client)
        proposal = dry_run(client)
        assert estate(client) == before
        jobs.frozen = Ok([])  # the re-validation now sees an empty set
        response = confirm(client, proposal)
        assert response.status_code == 409 and response.json()["code"] == "CONFIRMATION_STALE"
        assert estate(client) == before


def test_a_provider_port_cannot_write(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        from src.ports.outbound import JobsPort, NodesPort

        for port in (JobsPort, NodesPort):
            names = {n for n in dir(port) if not n.startswith("_")}
            assert not {n for n in names if n.startswith(("apply", "replace", "remove", "set_"))}
        executor(client)  # and the executor, the only writer, exists


# -- AC 3: exactly one executor call per confirmed proposal ---------------------------------------
@pytest.mark.parametrize("n", [2, 50])
def test_simultaneous_confirms_call_the_executor_once(n: int, tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        barrier = threading.Barrier(n)

        def run(_: int):
            barrier.wait(timeout=60)
            return confirm(client, proposal)

        with ThreadPoolExecutor(max_workers=n) as pool:
            replies = list(pool.map(run, range(n)))
        assert [r.status_code for r in replies] == [200] * n
        assert {r.json()["state"] for r in replies} == {"executed"}
        assert executor(client).calls == 1
        executed = [e for e in audit(client, proposal["session_id"]) if e["actor"] == "executor"]
        assert len(executed) == 1


def test_a_sequential_replay_answers_the_persisted_proposal_and_adds_no_call(
    tmp_path: Path,
) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        first = confirm(client, proposal)
        calls = executor(client).calls
        replay = confirm(client, proposal)
        assert replay.status_code == 200 and replay.json() == first.json()
        assert executor(client).calls == calls


# -- AC 5: the frozen request ---------------------------------------------------------------------
def test_the_dispatcher_forwards_exactly_the_frozen_request(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        confirm(client, proposal)
        [sent] = executor(client).requests
        body = sent.model_dump()
        assert set(body) == FROZEN_FIELDS
        assert body["gate_token"] == proposal["gate_token"]  # verbatim
        assert (
            body["selector"] == proposal["dry_run_snapshot"]["selector"]
        )  # persisted, not rebuilt
        assert body["dry_run_ref"] == {"proposal_id": proposal["proposal_id"]}


@pytest.mark.parametrize(
    "override",
    [
        {"dry_run_ref": {"proposal_id": "prop-00000000000000aa"}},
        {"extra": "field"},
        {"dry_run_ref": None},
    ],
    ids=["ref-mismatch", "extra-field", "no-ref"],
)
def test_a_malformed_executor_request_is_400_and_applies_nothing(
    override: dict, tmp_path: Path
) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        force_state(client, proposal["proposal_id"], "confirmed", "dispatched")
        before = estate(client)
        body = executor_body(proposal, **override)
        if override.get("dry_run_ref", 1) is None:
            body.pop("dry_run_ref")
        response = client.post(EXECUTOR, json=body)
        assert response.status_code == 400
        assert response.json()["code"] == "VALIDATION_MALFORMED_BODY"
        assert estate(client) == before


# -- AC 6: the executor applies the snapshot's keys and skips what changed ------------------------
def test_an_item_that_is_no_longer_running_is_skipped_and_the_result_is_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = install_jobs(monkeypatch)
    with app_on(tmp_path) as client:
        jobs.capture_next = True
        first, second = dry_run(client), dry_run(client)
        assert confirm(client, first).json()["state"] == "executed"  # the three jobs are cancelled
        jobs.frozen = jobs.captured  # the re-validation of the second still sees them running
        response = confirm(client, second)
        assert response.status_code == 502
        body = response.json()
        assert body["state"] == "failed"
        assert body["executor_result"]["status"] == "partial"
        assert body["executor_result"]["applied_count"] == 0
        assert body["executor_result"]["applied_records"] == []


# -- AC 7: an unavailable executor ----------------------------------------------------------------
def test_an_executor_that_is_down_fails_the_proposal_safely_and_is_never_retried(
    tmp_path: Path,
) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        before = estate(client)
        executor(client).down = True
        response = confirm(client, proposal)
        assert response.status_code == 503
        assert response.json()["code"] == "EXECUTOR_UNAVAILABLE"
        stored = get_proposal(client, proposal["proposal_id"]).json()
        assert stored["state"] == "failed" and stored["executor_result"] is None
        assert stored["confirmation"]["confirmed_at"] == CLOCK  # the proposal line is preserved
        assert stored["dry_run_snapshot"] == proposal["dry_run_snapshot"]
        assert [e["actor"] for e in audit(client, proposal["session_id"])] == ["copilot"] * 7
        assert estate(client) == before
        clock(client).advance(minutes=10)
        executor(client).down = False
        replay = confirm(client, proposal)
        assert replay.status_code == 200 and replay.json()["state"] == "failed"
        assert estate(client) == before  # no automatic retry, no second call


# -- AC 8: five seconds on the fake clock ---------------------------------------------------------
@pytest.mark.parametrize(
    ("delay", "status"),
    [(4.999, 200), (5.0, 200), (5.001, 503)],
    ids=["4.999s", "5.000s", "5.001s"],
)
def test_the_executor_has_five_seconds_on_the_clock(
    delay: float, status: int, tmp_path: Path
) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        executor(client).delay_seconds = delay
        response = confirm(client, proposal)
        assert response.status_code == status
        stored = row(client, proposal["proposal_id"])
        if status == 200:
            assert (response.json()["state"], stored["state"]) == ("executed", "executed")
        else:
            assert response.json()["code"] == "EXECUTOR_UNAVAILABLE"
            assert (stored["state"], stored["executor_status"]) == ("failed", None)


def test_a_late_result_is_kept_by_the_executor_and_never_applied_twice(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        executor(client).delay_seconds = 6
        assert confirm(client, proposal).status_code == 503
        late = client.get(f"{EXECUTOR}/{proposal['proposal_id']}")
        assert late.status_code == 200 and late.json()["status"] == "applied"
        assert (
            row(client, proposal["proposal_id"])["state"] == "failed"
        )  # the proposal never changes
        executor(client).delay_seconds = 0
        assert confirm(client, proposal).json()["state"] == "failed"  # a replay, not a second apply
        assert client.get(f"{EXECUTOR}/{proposal['proposal_id']}").json() == late.json()


# -- AC 9: a partial apply is failed and visible --------------------------------------------------
def test_a_partial_apply_is_failed_and_the_502_body_is_the_proposal(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        executor(client).apply_only = 2
        response = confirm(client, proposal)
        assert response.status_code == 502
        body = ProposalDTO.model_validate(response.json())
        assert body.state == "failed"
        assert body.executor_result.status == "partial"
        assert body.executor_result.applied_records == ANNEX_KEYS[:2]
        assert body.executor_result.applied_count == 2
        stored = row(client, proposal["proposal_id"])
        assert (stored["state"], stored["executor_status"], stored["applied_count"]) == (
            "failed", "partial", 2,
        )  # fmt: skip


def test_a_result_larger_than_the_scope_is_never_executed(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        executor(client).extra_applied = ["job#job-9999"]
        response = confirm(client, proposal)
        assert response.status_code == 502
        assert response.json()["state"] == "failed"
        assert row(client, proposal["proposal_id"])["state"] == "failed"


# -- AC 10, 11: the executor routes ---------------------------------------------------------------
def test_the_executor_refuses_a_proposal_that_was_not_confirmed(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        before = estate(client)
        response = client.post(EXECUTOR, json=executor_body(proposal))
        assert response.status_code == 409 and response.json()["code"] == "PROPOSAL_STATE_INVALID"
        assert estate(client) == before
        assert row(client, proposal["proposal_id"])["state"] == "dry_run"


def test_the_executor_checks_the_token_and_the_proposal(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        force_state(client, proposal["proposal_id"], "confirmed", "dispatched")
        before = estate(client)
        wrong = client.post(EXECUTOR, json=executor_body(proposal, gate_token=OTHER_TOKEN))
        assert wrong.status_code == 403 and wrong.json()["code"] == "GATE_TOKEN_INVALID"
        ghost = {**proposal, "proposal_id": "prop-00000000000000ff"}
        missing = client.post(EXECUTOR, json=executor_body(ghost))
        assert missing.status_code == 404 and missing.json()["code"] == "PROPOSAL_NOT_FOUND"
        assert estate(client) == before


def test_an_identical_executor_request_returns_the_stored_result_and_a_differing_one_conflicts(
    tmp_path: Path,
) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        force_state(client, proposal["proposal_id"], "confirmed", "dispatched")
        first = client.post(EXECUTOR, json=executor_body(proposal))
        assert first.status_code == 200 and first.json()["applied_count"] == 3
        after = estate(client)
        again = client.post(EXECUTOR, json=executor_body(proposal))
        assert again.status_code == 200 and again.json() == first.json()
        assert estate(client) == after  # one apply
        other = {"method": "jobs_port.select", "params": {"id": "job#job-8830"}}
        clash = client.post(EXECUTOR, json=executor_body(proposal, selector=other))
        assert clash.status_code == 409 and clash.json()["code"] == "EXECUTOR_DUPLICATE_APPLY"
        assert estate(client) == after


# -- AC 12: the read routes -----------------------------------------------------------------------
def test_get_proposal_answers_the_persisted_proposal_in_every_state(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        listed = get_proposal(client, proposal["proposal_id"])
        assert listed.status_code == 200 and listed.json()["state"] == "dry_run"
        assert listed.json()["executor_result"] is None
        done = confirm(client, proposal).json()
        assert get_proposal(client, proposal["proposal_id"]).json() == done
        assert client.get(f"{EXECUTOR}/{proposal['proposal_id']}").json() == done["executor_result"]


def test_the_read_routes_answer_404_for_an_unknown_proposal(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        for url in (f"{PROPOSALS}/prop-00000000000000ff", f"{EXECUTOR}/prop-00000000000000ff"):
            response = client.get(url)
            assert response.status_code == 404 and response.json()["code"] == "PROPOSAL_NOT_FOUND"


# -- AC 13: re-dispatch ---------------------------------------------------------------------------
def failed_parent(client: TestClient) -> dict:
    parent = dry_run(client)
    executor(client).down = True
    assert confirm(client, parent).status_code == 503
    executor(client).down = False
    return parent


def redispatch(client: TestClient, parent: dict, **override):
    body = {"query_text": "cancel", "action": "cancel_jobs", "target_refs": ["group#CS-101"]}
    return client.post(
        f"{PROPOSALS}/{parent['proposal_id']}/re-dispatches", json={**body, **override}
    )


def test_a_failed_proposal_is_re_dispatched_as_a_new_proposal_through_the_gate(
    tmp_path: Path,
) -> None:
    with app_on(tmp_path) as client:
        parent = failed_parent(client)
        before = estate(client)
        response = redispatch(client, parent)
        assert response.status_code == 200
        child = ProposalDTO.model_validate(response.json())
        assert child.state == "dry_run" and child.supersedes_proposal_id == parent["proposal_id"]
        assert (
            child.proposal_id != parent["proposal_id"] and child.gate_token != parent["gate_token"]
        )
        assert [i.key for i in child.dry_run_snapshot.affected_items] == ANNEX_KEYS
        assert row(client, parent["proposal_id"])["state"] == "superseded"
        assert estate(client) == before  # re-dispatch applies nothing
        bad = confirm(client, child.model_dump(mode="json"), parent["gate_token"])
        assert bad.status_code == 403 and bad.json()["code"] == "GATE_TOKEN_INVALID"
        good = confirm(client, child.model_dump(mode="json"))
        assert good.status_code == 200 and good.json()["state"] == "executed"
        assert estate(client) == with_jobs(before, ANNEX_KEYS, status="cancelled")


def test_a_partly_applied_parent_is_not_superseded(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        parent = dry_run(client)
        executor(client).apply_only = 2
        assert confirm(client, parent).status_code == 502
        executor(client).apply_only = None
        response = redispatch(client, parent)
        assert response.status_code == 200
        assert row(client, parent["proposal_id"])["state"] == "failed"  # it already applied 2


@pytest.mark.parametrize("state", ["dry_run", "executed", "superseded"])
def test_only_a_failed_parent_can_be_re_dispatched(state: str, tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        parent = dry_run(client)
        if state == "executed":
            assert confirm(client, parent).json()["state"] == "executed"
        elif state == "superseded":
            executor(client).down = True
            confirm(client, parent)
            executor(client).down = False
            assert redispatch(client, parent).status_code == 200
        response = redispatch(client, parent)
        assert response.status_code == 409 and response.json()["code"] == "PROPOSAL_STATE_INVALID"


def test_re_dispatch_of_an_unknown_or_empty_parent_is_refused(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        ghost = {"proposal_id": "prop-00000000000000ff"}
        missing = redispatch(client, ghost)
        assert missing.status_code == 404 and missing.json()["code"] == "PROPOSAL_NOT_FOUND"
        empty = dry_run_route(client, "cancel_jobs", ["group#group-2"])
        force_state(client, empty["proposal_id"], "confirmed", "dispatched", "failed")
        response = redispatch(client, empty, target_refs=["group#group-2"])
        assert response.status_code == 409 and response.json()["code"] == "DRY_RUN_EMPTY_SET"


# -- AC 14: nothing half written ------------------------------------------------------------------
def test_a_failing_audit_write_while_recording_the_result_leaves_the_proposal_dispatched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fault = NthAppendFails(monkeypatch)
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        fault.arm(2)  # the claim's rows are the first append, the result's row the second
        response = confirm(client, proposal)
        assert response.status_code == 500 and response.json()["code"] == "AUDIT_WRITE_FAILED"
        stored = row(client, proposal["proposal_id"])
        assert (stored["state"], stored["executor_status"]) == ("dispatched", None)
        replay = confirm(client, proposal)
        assert replay.status_code == 200 and replay.json()["state"] == "dispatched"
        assert executor(client).calls == 1


# -- AC 15: the contract surface is complete ------------------------------------------------------
def flatten(routes, prefix: str = ""):
    """Every concrete route, descending into the routers FastAPI wraps when they are included."""
    for route in routes:
        nested = getattr(route, "original_router", None)
        if nested is not None:
            context = getattr(getattr(route, "include_context", None), "prefix", "") or ""
            yield from flatten(nested.routes, prefix + context)
        elif hasattr(route, "methods"):
            yield prefix + route.path, route.methods


def served_operations(client: TestClient) -> set[tuple[str, str]]:
    served = {
        (method, re.sub(r"\{[^}]+\}", "{}", path))
        for path, methods in flatten(client.app.routes)
        for method in methods
        if method in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    }
    assert ("POST", "/api/v1/copilot/chat") in served  # the helper really sees the routes
    return served


def test_every_contract_operation_but_the_runbook_is_served(tmp_path: Path) -> None:
    declared = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))["paths"]
    wanted = {
        (m.upper(), re.sub(r"\{[^}]+\}", "{}", p))
        for p, ops in declared.items()
        for m in ops
        if m in {"get", "post", "put", "patch", "delete"}
    }
    with app_on(tmp_path) as client:
        missing = wanted - served_operations(client)
        assert missing == {("GET", "/api/v1/runbooks/{}")}


def test_regression_guard_no_mutating_route_outside_the_two_prefixes(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        mutating = {
            path for method, path in served_operations(client)
            if method in {"POST", "PUT", "PATCH", "DELETE"}
        }  # fmt: skip
        allowed = ("/api/v1/destructive/", "/executor/v1/", "/api/v1/sessions", "/api/v1/copilot/")
        assert mutating and all(p.startswith(allowed) for p in mutating), sorted(mutating)


# -- AC 16: regression guards (pass today, must not be edited) ------------------------------------
def test_regression_guard_the_chat_reply_and_the_query_route_keep_their_shape(
    tmp_path: Path,
) -> None:
    with app_on(tmp_path) as client:
        reply = client.post(COPILOT_CHAT, json={"query": ANNEX}).json()
        assert set(reply) == {
            "refusal", "impact_summary", "proposal", "token_expires_at", "confirmation_enabled",
        }  # fmt: skip
        assert reply["proposal"]["state"] == "dry_run"
        refused = client.post(COPILOT_QUERY, json={"query": ANNEX})
        assert refused.json()["code"] == "ACTION_REFUSED" and "gt-" not in refused.text


def test_regression_guard_a_wrong_token_is_still_403(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        response = confirm(client, proposal, OTHER_TOKEN)
        assert response.status_code == 403 and response.json()["code"] == "GATE_TOKEN_INVALID"
        assert row(client, proposal["proposal_id"])["state"] == "dry_run"
