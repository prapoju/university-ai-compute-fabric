"""Story 2.2 ATDD (red phase) - the dry-run, Annex 12.4.

Written BEFORE any production code, fixture or contract change, against the real app:
``create_app(Settings.from_env(...))`` on a file database, the real fixtures, the simulated clock
and the simulated prose writer. Nothing is mocked except one outbound port in the outage case
(``support.faults``). Every case asserts the resulting state and what did NOT happen: no estate
change, no extra proposal row, no token on a refusal-only route. Literals are written out on
purpose: the summary, the selector JSON and the ids are the contract.

Cases come from the story ("ATDD cases"), ``test/test-design.md`` 6.3.2 and the stub suite
``test/atdd/module12_contracts.test.py`` (``test_post_dry_run_*``), which is never imported.
Confirmation, expiry and dispatch belong to stories 2-3 and 2-4: nothing here asks for them.

Cases marked ``regression guard`` already pass on earlier behaviour and must stay unchanged.
"""

from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from support.faults import PortFault, install

import src.adapters.outbound.sim.fixtures_adapter as sim
from src.adapters.inbound.app import create_app
from src.config import ConfigError, Settings
from src.domain import canonical_strings as cs
from src.dto import ProposalDTO, SelectorDTO
from src.ports.outbound import JobsPort

pytestmark = pytest.mark.api

SESSIONS = "/api/v1/sessions"
COPILOT_QUERY = "/api/v1/copilot/query"
COPILOT_CHAT = "/api/v1/copilot/chat"
DRY_RUNS = "/api/v1/destructive/dry-runs"
CLOCK = "2026-10-16T15:00:00.000Z"
TOKEN = re.compile(r"^gt-[0-9a-f]{32}$")
ESTATE_TYPES = (
    "users", "catalog", "policy", "groups", "jobs", "nodes", "reservations", "windows", "events"
)  # fmt: skip

ANNEX = "Terminate all active jobs for CS-101"
ANNEX_SUMMARY = "3 active jobs will be terminated across nodes ws-gpu-02, ws-gpu-05, ws-gpu-08"
ANNEX_SELECTOR = {
    "method": "jobs_port.select",
    "params": {"group_id": "group#CS-101", "status": "running"},
}
ANNEX_KEYS = ["job#job-8901", "job#job-8902", "job#job-8903"]
S1 = "Why was student Alex denied access to model deepseek-coder?"
S2 = "Why can't Group 4 run their fine-tuning job right now?"


# -- helpers -----------------------------------------------------------------------------------
def app_on(tmp_path: Path, **env: str) -> TestClient:
    variables = {
        "M12_DB_PATH": str(tmp_path / "m12.db"),
        **{f"M12_{k.upper()}": v for k, v in env.items()},
    }
    try:
        settings = Settings.from_env(variables)
    except (
        ConfigError
    ) as exc:  # a setting this story adds is not known yet: a failure, not an error
        pytest.fail(f"configuration is not supported yet: {exc}")
    return TestClient(create_app(settings), raise_server_exceptions=False)


def open_session(client: TestClient) -> str:
    created = client.post(SESSIONS, json={"operator_role": "role-operations"})
    assert created.status_code == 201
    return created.json()["session_id"]


def chat(client: TestClient, query: str):
    return client.post(COPILOT_CHAT, json={"query": query})


def estate(client: TestClient) -> dict:
    """Every record of the nine read-only stores, through the real state routes."""
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


def proposal_rows(client: TestClient) -> list[dict]:
    columns = (
        "proposal_id, session_id, state, action, selector, affected_items, snapshot_timestamp, "
        "gate_token"
    )
    with client.app.state.container.writer.read() as db:
        cursor = db.execute(f"SELECT {columns} FROM proposals ORDER BY proposal_id")
        names = [d[0] for d in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def only_session(client: TestClient) -> str:
    with client.app.state.container.writer.read() as db:
        rows = db.execute("SELECT session_id FROM sessions ORDER BY session_id").fetchall()
    assert len(rows) == 1, f"expected one session, found {len(rows)}"
    return rows[0][0]


def reply(client: TestClient, query: str) -> dict:
    """The body of a chat reply that carries a dry-run (an assertion if it does not)."""
    response = chat(client, query)
    body = response.json()
    assert response.status_code == 200
    assert "proposal" in body, f"no dry-run in the reply, got {sorted(body)}"
    return body


def item_triples(proposal: dict) -> list[tuple]:
    items = proposal["dry_run_snapshot"]["affected_items"]
    assert all(i["actionable_field"] == "status" for i in items)
    return [(i["key"], i["actionable_value"], i["actionable"]) for i in items]


# -- AC 1: the Annex scenario, in one reply ----------------------------------------------------
def test_the_annex_scenario_answers_refusal_summary_and_token_in_one_reply(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        before = estate(client)
        response = chat(client, ANNEX)
        body = response.json()
        assert response.status_code == 200
        assert body.get("refusal", {}).get("code") == "ACTION_REFUSED"
        assert body["refusal"]["message"] == "Action refused."
        assert body.get("impact_summary") == ANNEX_SUMMARY

        proposal = body["proposal"]
        assert proposal["state"] == "dry_run" and proposal["action"] == "cancel_jobs"
        assert proposal["confirmation"] is None and proposal["executor_result"] is None
        assert TOKEN.fullmatch(proposal["gate_token"])
        snapshot = proposal["dry_run_snapshot"]
        assert snapshot["selector"] == ANNEX_SELECTOR
        assert item_triples(proposal) == [(key, "running", True) for key in ANNEX_KEYS]
        assert snapshot["snapshot_timestamp"] == CLOCK
        assert body["token_expires_at"] == "2026-10-16T15:01:00.000Z"  # snapshot + 60 s
        assert body["confirmation_enabled"] is True

        assert estate(client) == before  # cluster state unchanged
        assert len(proposal_rows(client)) == 1


def test_the_persisted_row_matches_the_reply_and_its_selector_re_executes(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = reply(client, ANNEX)["proposal"]
        rows = proposal_rows(client)
        assert len(rows) == 1
        row = rows[0]
        assert (row["state"], row["action"]) == ("dry_run", "cancel_jobs")
        assert row["gate_token"] == proposal["gate_token"]
        assert row["proposal_id"] == proposal["proposal_id"]
        assert row["snapshot_timestamp"] == CLOCK
        selector = json.loads(row["selector"])
        assert selector == ANNEX_SELECTOR
        assert json.loads(row["affected_items"]) == proposal["dry_run_snapshot"]["affected_items"]
        assert "Terminate" not in json.dumps(row)  # the query text is stored nowhere

        # the stored selector is enough to enumerate the same set again, without the query text
        jobs = client.app.state.container.port(JobsPort)
        again = jobs.select(SelectorDTO(method="filter", params=selector["params"]))
        assert [r.id for r in again.value] == ANNEX_KEYS


def test_the_refusal_turn_and_the_audit_of_a_chat_reply(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        reply(client, ANNEX)
        sid = only_session(client)
        turns = client.get(f"{SESSIONS}/{sid}").json()["turns"]
        assert [t["canonical"] for t in turns] == ["ACTION_REFUSED"]
        audit = client.get(f"{SESSIONS}/{sid}/audit").json()
        assert [e["result_summary"]["tool_name"] for e in audit["entries"]] == [
            "toolcall.answer_query",
            "toolcall.groups_port.get",
            "toolcall.propose_destructive_action",
            "toolcall.groups_port.get",
            "toolcall.jobs_port.select",
        ]
        assert {e["operator_role"] for e in audit["entries"]} == {"role-operations"}
        assert {e["timestamp"] for e in audit["entries"]} == {CLOCK}


# -- AC 2, 7: CS-101 resolves exactly, anything else is Entity Not Found --------------------------
@pytest.mark.parametrize(
    "query",
    [ANNEX, "terminate all active jobs for cs-101", "TERMINATE ALL ACTIVE JOBS FOR Cs-101"],
)
def test_cs_101_resolves_in_any_case(query: str, tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = reply(client, query)["proposal"]
        assert proposal["action"] == "cancel_jobs"
        assert [k for k, _, _ in item_triples(proposal)] == ANNEX_KEYS


@pytest.mark.parametrize(
    ("query", "named"),
    [
        ("Terminate all active jobs for CS101", "group#cs101"),
        ("delete all pending jobs for cs201", "group#cs201"),
        ("delete all pending jobs for group 99", "group#group-99"),
        ("cordon ws-gpu-99", "node#ws-gpu-99"),
    ],
)
def test_regression_guard_an_unresolved_target_is_named_before_any_dry_run(
    query: str, named: str, tmp_path: Path
) -> None:
    """regression guard: story 2.1 already answers this, and 2.2 must not create a proposal."""
    with app_on(tmp_path) as client:
        response = chat(client, query)
        body = response.json()
        assert response.status_code == 200 and body["code"] == "ENTITY_NOT_FOUND"
        assert body["message"] == cs.S_ENF.format(ref_list=named)
        assert "gt-" not in response.text
        assert proposal_rows(client) == []


# -- AC 4, 5, 6, 8: items, the status filter by action, node actions, fleet scopes --------------
CASES = [
    (  # a group, delete: the PENDING jobs of that group, a job with no node
        "delete all pending jobs for group 2", "delete_jobs",
        {"method": "jobs_port.select",
         "params": {"group_id": "group#group-2", "status": "pending"}},
        [("job#job-8824", "pending", True)], "1 pending job will be deleted", True,
    ),
    (  # a single job: its id, whatever its status
        "cancel job 8823", "cancel_jobs",
        {"method": "jobs_port.select", "params": {"id": "job#job-8823"}},
        [("job#job-8823", "pending", True)], "1 job will be terminated", True,
    ),
    (  # a job already in a terminal status is listed, not actionable
        "cancel job 8801", "cancel_jobs",
        {"method": "jobs_port.select", "params": {"id": "job#job-8801"}},
        [("job#job-8801", "cancelled", False)], "0 affected items", False,
    ),
    (
        "cordon ws-gpu-02", "cordon_node",
        {"method": "nodes_port.select", "params": {"node_ids": ["node#ws-gpu-02"]}},
        [("node#ws-gpu-02", "available", True)], "1 node will be cordoned", True,
    ),
    (
        "drain ws-gpu-05", "drain_node",
        {"method": "nodes_port.select", "params": {"node_ids": ["node#ws-gpu-05"]}},
        [("node#ws-gpu-05", "reserved", True)], "1 node will be drained", True,
    ),
    (  # a node in fault is already out of service
        "cordon ws-gpu-11", "cordon_node",
        {"method": "nodes_port.select", "params": {"node_ids": ["node#ws-gpu-11"]}},
        [("node#ws-gpu-11", "fault", False)], "0 affected items", False,
    ),
    (  # a group with nothing running: an empty set, confirmation disabled
        "cancel all running jobs for group 2", "cancel_jobs",
        {"method": "jobs_port.select",
         "params": {"group_id": "group#group-2", "status": "running"}},
        [], "0 affected items", False,
    ),
    (  # a fleet scope has a selector too
        "Delete all pending jobs", "delete_jobs",
        {"method": "jobs_port.select", "params": {"status": "pending"}},
        [("job#job-8823", "pending", True), ("job#job-8824", "pending", True),
         ("job#job-8825", "pending", True)], "3 pending jobs will be deleted", True,
    ),
]  # fmt: skip


@pytest.mark.parametrize(
    ("query", "action", "selector", "triples", "summary", "enabled"),
    CASES,
    ids=[c[0] for c in CASES],
)
def test_the_dry_run_enumerates_every_item_with_its_own_status(
    query: str, action: str, selector: dict, triples: list, summary: str, enabled: bool,
    tmp_path: Path,
) -> None:  # fmt: skip
    with app_on(tmp_path) as client:
        before = estate(client)
        body = reply(client, query)
        proposal = body["proposal"]
        assert proposal["action"] == action and proposal["state"] == "dry_run"
        assert proposal["dry_run_snapshot"]["selector"] == selector
        assert item_triples(proposal) == triples
        assert body["impact_summary"] == summary
        assert body["confirmation_enabled"] is enabled
        assert TOKEN.fullmatch(proposal["gate_token"])
        rows = proposal_rows(client)
        assert len(rows) == 1  # an empty set still creates the row (contracts Q-fail)
        assert json.loads(rows[0]["selector"]) == selector
        assert (
            json.loads(rows[0]["affected_items"]) == proposal["dry_run_snapshot"]["affected_items"]
        )
        assert estate(client) == before


def test_a_fleet_wide_cordon_lists_every_node_and_skips_the_one_in_fault(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        body = reply(client, "cordon entire lab")
        proposal = body["proposal"]
        assert proposal["dry_run_snapshot"]["selector"] == {
            "method": "nodes_port.select", "params": {},
        }  # fmt: skip
        items = proposal["dry_run_snapshot"]["affected_items"]
        assert [i["key"] for i in items] == [f"node#ws-gpu-{n:02d}" for n in range(1, 33)]
        assert [i["key"] for i in items if not i["actionable"]] == ["node#ws-gpu-11"]
        assert body["impact_summary"] == "31 nodes will be cordoned"
        assert body["confirmation_enabled"] is True


# -- AC 4: the fixtures the Annex scenario needs ---------------------------------------------------
@pytest.mark.parametrize(
    ("job", "node"),
    [
        ("job-8901", "node#ws-gpu-02"),
        ("job-8902", "node#ws-gpu-05"),
        ("job-8903", "node#ws-gpu-08"),
    ],
)
def test_the_cs_101_jobs_are_running_on_their_nodes(job: str, node: str, tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        group = client.get("/api/v1/state/groups/CS-101")
        assert group.status_code == 200 and group.json()["id"] == "group#CS-101"
        record = client.get(f"/api/v1/state/jobs/{job}")
        assert record.status_code == 200
        assert record.json()["group_id"] == "group#CS-101"
        assert (record.json()["status"], record.json().get("node")) == ("running", node)


def test_a_job_with_no_node_reports_a_null_node_never_a_made_up_one(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        record = client.get("/api/v1/state/jobs/job-8830").json()
        assert record.get("node", "the field is missing") is None


# -- AC 9: POST /destructive/dry-runs ------------------------------------------------------------
def dry_run_body(sid: str, **override) -> dict:
    body = {
        "query_text": "terminate all active jobs for CS-101",
        "action": "cancel_jobs",
        "target_refs": ["group#CS-101"],
        "session_id": sid,
    }
    return {**body, **override}


def test_the_dry_run_route_answers_the_contract_proposal(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        sid = open_session(client)
        response = client.post(DRY_RUNS, json=dry_run_body(sid))
        assert response.status_code == 200
        try:
            proposal = ProposalDTO.model_validate(response.json())
        except ValidationError as exc:
            pytest.fail(f"the reply is not a contract Proposal: {exc}")
        assert (proposal.state, proposal.action, proposal.session_id) == (
            "dry_run", "cancel_jobs", sid,
        )  # fmt: skip
        assert [i.key for i in proposal.dry_run_snapshot.affected_items] == ANNEX_KEYS
        assert proposal.dry_run_snapshot.selector.model_dump() == ANNEX_SELECTOR
        assert len(proposal_rows(client)) == 1
        audit = client.get(f"{SESSIONS}/{sid}/audit").json()
        assert [e["result_summary"]["tool_name"] for e in audit["entries"]] == [
            "toolcall.propose_destructive_action",
            "toolcall.groups_port.get",
            "toolcall.jobs_port.select",
        ]


@pytest.mark.parametrize(
    ("override", "status", "code"),
    [
        ({"session_id": "sess-00000000000000ff"}, 404, "SESSION_NOT_FOUND"),
        ({"action": "nuke_jobs"}, 400, "VALIDATION_MALFORMED_BODY"),
        ({"target_refs": []}, 400, "VALIDATION_MALFORMED_BODY"),
        ({"action": "cordon_node"}, 400, "VALIDATION_BAD_ACTION"),
        ({"target_refs": ["group#nope"]}, 200, "ENTITY_NOT_FOUND"),
        ({"query_text": "show the jobs of CS-101 and cancel them"}, 200, "CLARIFICATION_REQUIRED"),
    ],
    ids=["no-session", "unknown-action", "no-target", "wrong-kind", "unresolved", "compound"],
)
def test_a_dry_run_that_cannot_be_built_creates_no_proposal(
    override: dict, status: int, code: str, tmp_path: Path
) -> None:
    with app_on(tmp_path) as client:
        sid = open_session(client)
        response = client.post(DRY_RUNS, json=dry_run_body(sid, **override))
        assert response.status_code == status
        assert response.json()["code"] == code
        assert "gt-" not in response.text
        assert proposal_rows(client) == []


# -- AC 10: one proposal and one token per dry-run, under concurrency --------------------------
def test_two_dry_runs_on_one_session_are_two_proposals_with_two_tokens(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        sid = open_session(client)
        barrier = threading.Barrier(2)
        replies: list = []

        def run() -> None:
            barrier.wait(timeout=30)
            replies.append(client.post(DRY_RUNS, json=dry_run_body(sid)))

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        assert [r.status_code for r in replies] == [200, 200]
        rows = proposal_rows(client)
        assert len(rows) == 2
        assert len({r["proposal_id"] for r in rows}) == 2
        assert len({r["gate_token"] for r in rows}) == 2
        assert {r.json()["gate_token"] for r in replies} == {r["gate_token"] for r in rows}


def test_fifty_concurrent_dry_runs_give_fifty_unique_tokens_and_no_server_error(
    tmp_path: Path,
) -> None:
    with app_on(tmp_path) as client:
        sessions = [open_session(client) for _ in range(50)]
        barrier = threading.Barrier(50)

        def run(sid: str) -> int:
            barrier.wait(timeout=60)
            return client.post(DRY_RUNS, json=dry_run_body(sid)).status_code

        with ThreadPoolExecutor(max_workers=50) as pool:
            statuses = list(pool.map(run, sessions))

        assert statuses == [200] * 50  # no 500, no "database is locked"
        rows = proposal_rows(client)
        assert len(rows) == 50
        assert len({r["gate_token"] for r in rows}) == 50
        assert all(TOKEN.fullmatch(r["gate_token"]) for r in rows)
        # the ids as a set: which request got which id is not the point (test design 6.3.2)
        assert {r["proposal_id"] for r in rows} == {f"prop-{n:016x}" for n in range(1, 51)}


# -- AC 11, 12: the token source and the token lifetime ----------------------------------------
def test_the_real_app_issues_a_different_token_on_every_start(tmp_path: Path) -> None:
    tokens = []
    for name in ("first", "second"):
        (tmp_path / name).mkdir()
        with app_on(tmp_path / name) as client:
            token = reply(client, ANNEX)["proposal"]["gate_token"]
            assert TOKEN.fullmatch(token)
            tokens.append(token)
    assert tokens[0] != tokens[1]  # a deterministic source would repeat itself (IR-06)


def test_the_token_lifetime_is_a_setting(tmp_path: Path) -> None:
    with app_on(tmp_path, gate_token_ttl_seconds="5") as client:
        body = reply(client, ANNEX)
        assert body["proposal"]["dry_run_snapshot"]["snapshot_timestamp"] == CLOCK
        assert body["token_expires_at"] == "2026-10-16T15:00:05.000Z"


# -- AC 13: a provider failure leaves no partial snapshot ---------------------------------------
def test_a_jobs_outage_persists_nothing_and_keeps_the_refusal_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fault = PortFault()
    install(monkeypatch, sim.SimJobs, "select", fault)  # before create_app: audited() binds then
    with app_on(tmp_path) as client:
        fault.down()
        response = chat(client, ANNEX)
        assert response.status_code == 503
        assert response.json()["code"] == "PROVIDER_UNAVAILABLE"
        assert "gt-" not in response.text and "proposal" not in response.json()
        assert proposal_rows(client) == []  # no partial snapshot, no token
        sid = only_session(client)
        turns = client.get(f"{SESSIONS}/{sid}").json()["turns"]
        assert [t["canonical"] for t in turns] == ["ACTION_REFUSED"]  # the refusal turn stays

        fault.recover()
        assert len(reply(client, ANNEX)["proposal"]["dry_run_snapshot"]["affected_items"]) == 3
        assert len(proposal_rows(client)) == 1


def test_the_dry_run_route_answers_a_jobs_outage_as_a_safe_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fault = PortFault()
    install(monkeypatch, sim.SimJobs, "select", fault)
    with app_on(tmp_path) as client:
        sid = open_session(client)
        fault.down()
        response = client.post(DRY_RUNS, json=dry_run_body(sid))
        assert response.status_code == 503
        assert response.json()["code"] == "PROVIDER_UNAVAILABLE"
        assert proposal_rows(client) == []


# -- AC 14: /copilot/query stays refusal-only (I2-07) ---------------------------------------------
def test_copilot_query_stays_refusal_only(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        response = client.post(COPILOT_QUERY, json={"query": ANNEX})
        body = response.json()
        assert response.status_code == 200
        assert body["code"] == "ACTION_REFUSED" and body["message"] == "Action refused."
        assert "proposal" not in body and "gt-" not in response.text
        assert proposal_rows(client) == []


# -- AC 15: regression guards (they pass on earlier behaviour and must not be edited) ----------
def test_regression_guard_the_existing_groups_and_jobs_are_untouched(tmp_path: Path) -> None:
    """regression guard (IR-12): group-2, -4, -7 and the S1/S2 jobs keep their records."""
    with app_on(tmp_path) as client:
        get = lambda route: client.get(f"/api/v1/state/{route}").json()  # noqa: E731
        assert get("groups/group-4") == {
            "id": "group#group-4", "name": "Group 4",
            "members": ["user#mateo", "user#lucas", "user#alex"],
        }  # fmt: skip
        assert get("groups/group-2")["members"] == ["user#sofia"]
        job = {k: v for k, v in get("jobs/job-8823").items() if k != "node"}
        assert (job["group_id"], job["course"], job["status"]) == (
            "group#group-4",
            "CS201",
            "pending",
        )
        running = {k: v for k, v in get("jobs/job-8830").items() if k != "node"}
        assert (running["group_id"], running["status"]) == ("group#group-4", "running")


def test_regression_guard_the_mandatory_queries_answer_as_before(tmp_path: Path) -> None:
    """regression guard: S1 and S2 are untouched by the new group and jobs."""
    with app_on(tmp_path) as client:
        sid = open_session(client)
        s1 = client.post(f"{SESSIONS}/{sid}/queries", json={"query_text": S1}).json()
        s2 = client.post(f"{SESSIONS}/{sid}/queries", json={"query_text": S2}).json()
        assert s1["answers"][0]["diagnosis_class"] == "access_denial_not_in_allowlist"
        assert s2["answers"][0]["diagnosis_class"] == "schedule_window_restricted"


def test_regression_guard_a_refusal_on_the_query_route_is_still_the_story_2_1_envelope(
    tmp_path: Path,
) -> None:
    """regression guard: `/copilot/query` and the sessions route are unchanged by this story."""
    with app_on(tmp_path) as client:
        before = estate(client)
        response = client.post(COPILOT_QUERY, json={"query": "delete all pending jobs for group 2"})
        assert response.json()["code"] == "ACTION_REFUSED"
        assert "proposal" not in response.json()
        assert estate(client) == before and proposal_rows(client) == []
