"""Story 2.3 ATDD (red phase) - the confirmation gate, Annex 12.4.

Written BEFORE any production code or contract change, against the real app:
``create_app(Settings.from_env(...))`` on a file database, the real fixtures, the simulated clock
and the simulated prose writer. Doubles exist only at outbound ports: one on ``SimJobs.select``
(a switch that outages it, counts its calls and changes what it answers, because the estate has no
write path) and one on ``SqliteAuditStore.append`` (a switch that fails it). The clock is the real
``SimClock``, moved with ``advance``; nothing sleeps. Literals are written out on purpose: the
caption, the codes, the statuses, the delta text and the instants are the contract.

This story stops at ``confirmed``: there is no executor, so "Exec = 1" of the test design reads
here as one ``dry_run -> confirmed`` transition and one set of audit rows. Dispatch belongs to 2-4.

Cases come from the story ("ATDD cases"), ``test/test-design.md`` 6.3.3 and the stub suite
``test/atdd/module12_contracts.test.py`` (``test_post_confirm_*``, ``test_confirm_and_dispatch_*``),
which is never imported. Cases marked ``regression guard`` already pass on earlier behaviour and
must stay unchanged.
"""

from __future__ import annotations

import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from support.faults import PortFault, install

import src.adapters.outbound.sim.fixtures_adapter as sim
from src.adapters.inbound.app import create_app
from src.adapters.outbound.db.audit_store import SqliteAuditStore
from src.config import ConfigError, Settings
from src.domain.result import Failure
from src.dto import ProposalDTO
from src.ports.outbound import ClockPort

pytestmark = pytest.mark.api

SESSIONS = "/api/v1/sessions"
COPILOT_QUERY = "/api/v1/copilot/query"
COPILOT_CHAT = "/api/v1/copilot/chat"
DRY_RUNS = "/api/v1/destructive/dry-runs"
CONFIRMS = "/api/v1/destructive/proposals"
CLOCK = "2026-10-16T15:00:00.000Z"
CAPTION = "This confirms a proposal for delegation. It does not grant or assert authorization."
TOKEN = re.compile(r"^gt-[0-9a-f]{32}$")
ESTATE_TYPES = (
    "users", "catalog", "policy", "groups", "jobs", "nodes", "reservations", "windows", "events"
)  # fmt: skip

ANNEX = "Terminate all active jobs for CS-101"
ANNEX_KEYS = ["job#job-8901", "job#job-8902", "job#job-8903"]
OTHER_TOKEN = "gt-" + "ab" * 16
UNKNOWN_PROPOSAL = "prop-00000000000000ff"
STALE_LAST_LINE = "confirmation disabled: run a new dry-run"


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


def open_session(client: TestClient) -> str:
    created = client.post(SESSIONS, json={"operator_role": "role-operations"})
    assert created.status_code == 201
    return created.json()["session_id"]


def clock(client: TestClient):
    return client.app.state.container.port(ClockPort)


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


def rows(client: TestClient) -> list[dict]:
    columns = "proposal_id, session_id, state, action, affected_items, confirmed_at, gate_token"
    with client.app.state.container.writer.read() as db:
        cursor = db.execute(f"SELECT {columns} FROM proposals ORDER BY proposal_id")
        names = [d[0] for d in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def row(client: TestClient, proposal_id: str) -> dict:
    found = [r for r in rows(client) if r["proposal_id"] == proposal_id]
    assert len(found) == 1, f"expected one row for {proposal_id}, found {len(found)}"
    return found[0]


def audit(client: TestClient, sid: str) -> list[dict]:
    body = client.get(f"{SESSIONS}/{sid}/audit", params={"page": 1, "page_size": 100}).json()
    return body["entries"]


def tools(client: TestClient, sid: str) -> list[str]:
    return [e["result_summary"]["tool_name"] for e in audit(client, sid)]


def dry_run(client: TestClient, query: str = ANNEX) -> dict:
    """The proposal a chat reply carries (an assertion if it does not)."""
    response = client.post(COPILOT_CHAT, json={"query": query})
    assert response.status_code == 200
    assert "proposal" in response.json(), f"no dry-run in the reply: {sorted(response.json())}"
    return response.json()["proposal"]


def dry_run_route(client: TestClient, action: str, refs: list[str], query: str = "cancel") -> dict:
    sid = open_session(client)
    body = {"query_text": query, "action": action, "target_refs": refs, "session_id": sid}
    response = client.post(DRY_RUNS, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client: TestClient, proposal_id: str, token: str):
    return client.post(CONFIRMS, json={"proposal_id": proposal_id, "gate_token": token})


def confirm_proposal(client: TestClient, proposal: dict):
    return confirm(client, proposal["proposal_id"], proposal["gate_token"])


@dataclass
class JobsDouble:
    """A switch on ``SimJobs.select``: it counts calls, can outage and can change the answer."""

    mode: str = "same"  # same | finished_and_new | status_changed | removed
    down: bool = False
    calls: int = 0
    seen: list = field(default_factory=list)


def install_jobs(monkeypatch: pytest.MonkeyPatch) -> JobsDouble:
    """Install **before** ``create_app``: ``audited()`` binds the method at build time."""
    switch = JobsDouble()
    original = sim.SimJobs.select

    def select(self, selector):
        switch.calls += 1
        if switch.down:
            return Failure("PROVIDER_UNAVAILABLE", observed=("simulated outage",))
        result = original(self, selector)
        if isinstance(result, Failure) or switch.mode == "same":
            return result
        records = list(result.value)
        if switch.mode == "finished_and_new" and records:
            first = records[0]  # one job leaves the set, a new one joins it
            records = [*records[1:], first.model_copy(update={"id": "job#job-8904"})]
        elif switch.mode == "removed" and records:
            records = records[1:]
        elif switch.mode == "status_changed":
            records = [r.model_copy(update={"status": "succeeded"}) for r in records]
        return type(result)(records)

    monkeypatch.setattr(sim.SimJobs, "select", select)
    return switch


# -- AC 1: a distinct confirmation ends in `confirmed` ---------------------------------------------
def test_the_annex_dry_run_then_a_distinct_confirm_answers_a_confirmed_proposal(
    tmp_path: Path,
) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        before = estate(client)
        response = confirm_proposal(client, proposal)
        assert response.status_code == 200
        try:
            confirmed = ProposalDTO.model_validate(response.json())
        except ValidationError as exc:
            pytest.fail(f"the reply is not a contract Proposal: {exc}")
        assert confirmed.state == "confirmed" and confirmed.action == "cancel_jobs"
        assert confirmed.proposal_id == proposal["proposal_id"]
        assert confirmed.gate_token == proposal["gate_token"]
        assert confirmed.dry_run_snapshot.model_dump() == proposal["dry_run_snapshot"]
        assert confirmed.confirmation is not None
        assert confirmed.confirmation.confirmed_at == CLOCK
        assert confirmed.confirmation.caption == CAPTION
        assert confirmed.executor_result is None
        stored = row(client, proposal["proposal_id"])
        assert (stored["state"], stored["confirmed_at"]) == ("confirmed", CLOCK)
        assert estate(client) == before  # zero writes to simulated state


# -- AC 2: no identity, no role, no session context -----------------------------------------------
@pytest.mark.parametrize("claim", ["role", "user", "session_id", "operator_role", "identity"])
def test_a_confirm_body_with_an_identity_claim_is_malformed_and_changes_nothing(
    claim: str, tmp_path: Path
) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        body = {
            "proposal_id": proposal["proposal_id"],
            "gate_token": proposal["gate_token"],
            claim: "role-admin" if claim != "session_id" else proposal["session_id"],
        }
        response = client.post(CONFIRMS, json=body)
        assert response.status_code == 400
        assert response.json()["code"] == "VALIDATION_MALFORMED_BODY"
        stored = row(client, proposal["proposal_id"])
        assert (stored["state"], stored["confirmed_at"]) == ("dry_run", None)


def test_a_session_reset_between_the_dry_run_and_the_confirm_changes_nothing(
    tmp_path: Path,
) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        assert client.delete(f"{SESSIONS}/{proposal['session_id']}").status_code == 204
        response = confirm_proposal(client, proposal)
        assert response.status_code == 200
        assert response.json()["state"] == "confirmed"  # the context is never consulted


def test_the_confirmation_records_no_identity_of_its_own(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        body = confirm_proposal(client, proposal).json()
        assert set(body) <= set(ProposalDTO.model_fields)  # no extra identity field in the reply
        assert set(body["confirmation"]) == {"confirmed_at", "caption"}
        entries = audit(client, proposal["session_id"])
        assert {e["operator_role"] for e in entries} == {"role-operations"}  # the session's own


# -- AC 3: the token lives 60 s on the fake clock -------------------------------------------------
@pytest.mark.parametrize(
    ("elapsed", "status"),
    [(59.999, 200), (60.0, 200), (60.001, 409)],
    ids=["+59.999s", "+60.000s", "+60.001s"],
)
def test_the_token_is_accepted_up_to_sixty_seconds_and_not_after(
    elapsed: float, status: int, tmp_path: Path
) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        clock(client).advance(seconds=elapsed)
        response = confirm_proposal(client, proposal)
        assert response.status_code == status
        stored = row(client, proposal["proposal_id"])
        if status == 200:
            assert (response.json()["state"], stored["state"]) == ("confirmed", "confirmed")
        else:
            assert response.json()["code"] == "CONFIRMATION_STALE"
            assert "token expired" in response.json()["message"]
            assert (stored["state"], stored["confirmed_at"]) == ("dry_run", None)


@pytest.mark.parametrize(("elapsed", "status"), [(5.0, 200), (5.001, 409)], ids=["+5s", "+5.001s"])
def test_the_token_lifetime_is_the_setting_in_force(
    elapsed: float, status: int, tmp_path: Path
) -> None:
    with app_on(tmp_path, gate_token_ttl_seconds="5") as client:
        proposal = dry_run(client)
        clock(client).advance(seconds=elapsed)
        assert confirm_proposal(client, proposal).status_code == status


# -- AC 4: single use, and a replay is harmless ---------------------------------------------------
def test_an_identical_replay_answers_the_persisted_proposal_and_changes_nothing(
    tmp_path: Path,
) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        first = confirm_proposal(client, proposal)
        assert first.status_code == 200
        rows_before = rows(client)
        audit_before = tools(client, proposal["session_id"])
        second = confirm_proposal(client, proposal)
        assert second.status_code == 200
        assert second.json() == first.json()
        assert rows(client) == rows_before  # no second transition, the same confirmed_at
        assert tools(client, proposal["session_id"]) == audit_before  # no new audit row


def test_an_identical_replay_after_the_token_lifetime_still_answers_the_persisted_proposal(
    tmp_path: Path,
) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        first = confirm_proposal(client, proposal)
        clock(client).advance(seconds=120)
        replay = confirm_proposal(client, proposal)
        assert replay.status_code == 200
        assert replay.json() == first.json()  # P5 is evaluated before P2 (OP-I2-1)


# -- AC 5: a wrong token, a conflict and a bad request are told apart -----------------------------
def test_an_unknown_proposal_is_not_found(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        response = confirm(client, UNKNOWN_PROPOSAL, OTHER_TOKEN)
        assert response.status_code == 404
        assert response.json()["code"] == "PROPOSAL_NOT_FOUND"
        assert rows(client) == []


def test_a_wrong_token_is_forbidden_and_the_proposal_stays_in_dry_run(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        audit_before = tools(client, proposal["session_id"])
        response = confirm(client, proposal["proposal_id"], OTHER_TOKEN)
        assert response.status_code == 403
        assert response.json()["code"] == "GATE_TOKEN_INVALID"
        stored = row(client, proposal["proposal_id"])
        assert (stored["state"], stored["confirmed_at"]) == ("dry_run", None)
        assert tools(client, proposal["session_id"]) == audit_before


def test_another_proposals_token_is_forbidden(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        first, second = dry_run(client), dry_run(client)
        response = confirm(client, first["proposal_id"], second["gate_token"])
        assert response.status_code == 403 and response.json()["code"] == "GATE_TOKEN_INVALID"
        assert [r["state"] for r in rows(client)] == ["dry_run", "dry_run"]


def test_a_different_token_on_a_confirmed_proposal_is_a_conflict(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        assert confirm_proposal(client, proposal).status_code == 200
        response = confirm(client, proposal["proposal_id"], OTHER_TOKEN)
        assert response.status_code == 409
        assert response.json()["code"] == "CONFIRMATION_CONFLICT"
        assert row(client, proposal["proposal_id"])["state"] == "confirmed"


@pytest.mark.parametrize("token", ["nope", "gt-short", "GT-" + "ab" * 16, "gt-" + "AB" * 16, ""])
def test_a_malformed_token_is_a_malformed_body(token: str, tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        response = confirm(client, proposal["proposal_id"], token)
        assert response.status_code == 400
        assert response.json()["code"] == "VALIDATION_MALFORMED_BODY"
        assert row(client, proposal["proposal_id"])["state"] == "dry_run"


def test_a_proposal_in_the_refused_state_cannot_be_confirmed(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        sid = open_session(client)
        proposal_id, token = "prop-00000000000000aa", "gt-" + "cd" * 16
        with client.app.state.container.writer.transaction() as db:
            db.execute(
                "INSERT INTO proposals (proposal_id, session_id, state, action, selector,"
                " affected_items, snapshot_timestamp, gate_token, created_at, updated_at)"
                " VALUES (?, ?, 'refused', 'cancel_jobs',"
                ' \'{"method": "jobs_port.select", "params": {}}\', \'[]\', ?, ?, ?, ?)',
                (proposal_id, sid, CLOCK, token, CLOCK, CLOCK),
            )
        response = confirm(client, proposal_id, token)
        assert response.status_code == 409
        assert response.json()["code"] == "PROPOSAL_STATE_INVALID"
        assert row(client, proposal_id)["state"] == "refused"


# -- AC 6: nothing to confirm is refused before any provider read ---------------------------------
@pytest.mark.parametrize(
    ("action", "refs", "why"),
    [
        ("cancel_jobs", ["group#group-2"], "empty set"),
        ("cancel_jobs", ["job#job-8801"], "a cancelled job is listed and not actionable"),
        ("cancel_jobs", ["job#job-8812"], "a succeeded job is listed and not actionable"),
        ("cordon_node", ["node#ws-gpu-11"], "a node in fault is listed and not actionable"),
    ],
    ids=["empty", "cancelled-job", "succeeded-job", "fault-node"],
)
def test_a_set_with_nothing_actionable_is_refused_without_a_provider_read(
    action: str, refs: list[str], why: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = install_jobs(monkeypatch)
    with app_on(tmp_path) as client:
        proposal = dry_run_route(client, action, refs)
        assert not any(i["actionable"] for i in proposal["dry_run_snapshot"]["affected_items"])
        calls = jobs.calls
        response = confirm_proposal(client, proposal)
        assert response.status_code == 409, why
        assert response.json()["code"] == "DRY_RUN_EMPTY_SET"
        assert jobs.calls == calls  # P4 comes before the re-validation read
        assert row(client, proposal["proposal_id"])["state"] == "dry_run"


# -- AC 7: the stored selector is re-executed and the set must still match ------------------------
def test_a_job_that_left_the_set_and_a_new_one_that_joined_it_make_the_confirmation_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = install_jobs(monkeypatch)
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        items_before = row(client, proposal["proposal_id"])["affected_items"]
        jobs.mode = "finished_and_new"
        response = confirm_proposal(client, proposal)
        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "CONFIRMATION_STALE"
        assert body["message"].startswith("Snapshot stale: ")
        assert "added job#job-8904" in body["message"]
        assert "removed job#job-8901" in body["message"]
        lines = body["explanation"]["observed_values"]
        assert "added job#job-8904" in lines and "removed job#job-8901" in lines
        assert lines[-1] == STALE_LAST_LINE  # confirmation is disabled
        stored = row(client, proposal["proposal_id"])
        assert (stored["state"], stored["confirmed_at"]) == ("dry_run", None)
        assert stored["affected_items"] == items_before  # the snapshot is never rewritten


def test_a_status_that_changed_makes_the_confirmation_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = install_jobs(monkeypatch)
    with app_on(tmp_path) as client:
        proposal = dry_run_route(client, "cancel_jobs", ["job#job-8830"])
        jobs.mode = "status_changed"
        response = confirm_proposal(client, proposal)
        assert response.status_code == 409 and response.json()["code"] == "CONFIRMATION_STALE"
        assert "job#job-8830 running -> succeeded" in response.json()["message"]
        assert row(client, proposal["proposal_id"])["state"] == "dry_run"


def test_a_removed_item_makes_the_confirmation_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = install_jobs(monkeypatch)
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        jobs.mode = "removed"
        response = confirm_proposal(client, proposal)
        assert response.status_code == 409 and response.json()["code"] == "CONFIRMATION_STALE"
        assert response.json()["message"] == "Snapshot stale: removed job#job-8901."


def test_an_unchanged_set_is_confirmed_after_the_selector_is_re_executed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = install_jobs(monkeypatch)
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        calls = jobs.calls
        response = confirm_proposal(client, proposal)
        assert response.status_code == 200 and response.json()["state"] == "confirmed"
        assert jobs.calls == calls + 1  # the stored selector ran once more, on the real port


# -- AC 8: a provider failure during re-validation is a safe failure ------------------------------
def test_a_jobs_outage_during_revalidation_is_a_safe_failure_and_recovery_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = install_jobs(monkeypatch)
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        audit_before = tools(client, proposal["session_id"])
        jobs.down = True
        response = confirm_proposal(client, proposal)
        assert response.status_code == 503
        assert response.json()["code"] == "PROVIDER_UNAVAILABLE"
        stored = row(client, proposal["proposal_id"])
        assert (stored["state"], stored["confirmed_at"]) == ("dry_run", None)
        assert tools(client, proposal["session_id"]) == audit_before

        jobs.down = False
        assert confirm_proposal(client, proposal).json()["state"] == "confirmed"


# -- AC 9: concurrent confirms make one transition ------------------------------------------------
def hammer(client: TestClient, proposal: dict, n: int) -> list:
    barrier = threading.Barrier(n)

    def run(_: int):
        barrier.wait(timeout=60)
        return confirm_proposal(client, proposal)

    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(run, range(n)))


@pytest.mark.parametrize("n", [2, 50])
def test_simultaneous_identical_confirms_make_exactly_one_transition(
    n: int, tmp_path: Path
) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        replies = hammer(client, proposal, n)
        assert [r.status_code for r in replies] == [200] * n  # 0 HTTP 500, 0 "database is locked"
        assert {r.json()["state"] for r in replies} == {"confirmed"}
        assert {r.json()["confirmation"]["confirmed_at"] for r in replies} == {CLOCK}
        stored = row(client, proposal["proposal_id"])
        assert (stored["state"], stored["confirmed_at"]) == ("confirmed", CLOCK)
        assert tools(client, proposal["session_id"]).count("toolcall.confirm_and_dispatch") == 1


def test_an_identical_confirm_raced_with_one_that_has_another_token_never_transitions_twice(
    tmp_path: Path,
) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        barrier = threading.Barrier(2)

        def run(token: str):
            barrier.wait(timeout=60)
            return confirm(client, proposal["proposal_id"], token)

        with ThreadPoolExecutor(max_workers=2) as pool:
            good = pool.submit(run, proposal["gate_token"])
            other = pool.submit(run, OTHER_TOKEN)
        assert good.result().status_code == 200
        assert other.result().status_code in {403, 409}
        assert tools(client, proposal["session_id"]).count("toolcall.confirm_and_dispatch") == 1
        assert row(client, proposal["proposal_id"])["state"] == "confirmed"


def test_a_confirm_that_goes_first_wins_and_a_state_change_that_goes_first_makes_it_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = install_jobs(monkeypatch)
    with app_on(tmp_path) as client:
        first, second = dry_run(client), dry_run(client)
        assert confirm_proposal(client, first).status_code == 200  # order A: confirm, then change
        jobs.mode = "finished_and_new"
        assert row(client, first["proposal_id"])["state"] == "confirmed"
        response = confirm_proposal(client, second)  # order B: the change came first
        assert response.status_code == 409 and response.json()["code"] == "CONFIRMATION_STALE"
        assert row(client, second["proposal_id"])["state"] == "dry_run"


# -- AC 10: the claim and its audit commit together -----------------------------------------------
def test_a_failing_audit_write_leaves_the_proposal_in_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fault = PortFault()
    install(monkeypatch, SqliteAuditStore, "append", fault)
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        fault.down()
        response = confirm_proposal(client, proposal)
        assert response.status_code == 500
        assert response.json()["code"] == "AUDIT_WRITE_FAILED"
        stored = row(client, proposal["proposal_id"])
        assert (stored["state"], stored["confirmed_at"]) == ("dry_run", None)

        fault.recover()
        assert confirm_proposal(client, proposal).json()["state"] == "confirmed"


# -- AC 11: the confirmation is audited once ------------------------------------------------------
def test_the_audit_after_a_confirm_has_the_head_and_the_revalidation_read(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        sid = proposal["session_id"]
        assert tools(client, sid) == [
            "toolcall.answer_query", "toolcall.groups_port.get",
            "toolcall.propose_destructive_action", "toolcall.groups_port.get",
            "toolcall.jobs_port.select",
        ]  # fmt: skip
        clock(client).advance(seconds=7)
        assert confirm_proposal(client, proposal).status_code == 200
        entries = audit(client, sid)
        assert [e["result_summary"]["tool_name"] for e in entries[-2:]] == [
            "toolcall.confirm_and_dispatch",
            "toolcall.jobs_port.select",
        ]
        assert len(entries) == 7
        assert {e["timestamp"] for e in entries[-2:]} == {"2026-10-16T15:00:07.000Z"}
        assert {e["operator_role"] for e in entries} == {"role-operations"}
        assert proposal["gate_token"] not in str(entries)  # the token is never audited


def test_a_replay_and_a_rejection_add_no_audit_row(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        proposal = dry_run(client)
        sid = proposal["session_id"]
        assert confirm_proposal(client, proposal).status_code == 200
        settled = tools(client, sid)
        assert settled[-2:] == ["toolcall.confirm_and_dispatch", "toolcall.jobs_port.select"]
        assert confirm_proposal(client, proposal).status_code == 200  # replay
        assert confirm(client, proposal["proposal_id"], OTHER_TOKEN).status_code == 409  # conflict
        assert tools(client, sid) == settled


# -- AC 12: the Annex scenario reaches `confirmed` ------------------------------------------------
def test_annex_12_4_end_to_end_up_to_confirmed(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        before = estate(client)
        reply = client.post(COPILOT_CHAT, json={"query": ANNEX}).json()
        assert reply["refusal"]["code"] == "ACTION_REFUSED"
        assert reply["impact_summary"].startswith("3 active jobs will be terminated across nodes")
        proposal = reply["proposal"]
        assert TOKEN.fullmatch(proposal["gate_token"])
        assert [i["key"] for i in proposal["dry_run_snapshot"]["affected_items"]] == ANNEX_KEYS

        response = confirm_proposal(client, proposal)  # a separate request, only id and token
        assert response.status_code == 200
        assert response.json()["state"] == "confirmed"
        assert response.json()["confirmation"] == {"confirmed_at": CLOCK, "caption": CAPTION}
        assert estate(client) == before  # the cluster state is identical, nothing was dispatched
        assert [r["state"] for r in rows(client)] == ["confirmed"]


# -- AC 13: nothing that already works changes (regression guards) --------------------------------
def test_regression_guard_the_dry_run_route_and_the_chat_reply_keep_their_shape(
    tmp_path: Path,
) -> None:
    with app_on(tmp_path) as client:
        reply = client.post(COPILOT_CHAT, json={"query": ANNEX}).json()
        assert set(reply) == {
            "refusal", "impact_summary", "proposal", "token_expires_at", "confirmation_enabled",
        }  # fmt: skip
        assert reply["proposal"]["state"] == "dry_run"
        assert reply["proposal"]["confirmation"] is None
        assert TOKEN.fullmatch(reply["proposal"]["gate_token"])


def test_regression_guard_copilot_query_stays_refusal_only(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        response = client.post(COPILOT_QUERY, json={"query": ANNEX})
        assert response.status_code == 200 and response.json()["code"] == "ACTION_REFUSED"
        assert "gt-" not in response.text
        assert rows(client) == []


def test_regression_guard_a_dry_run_for_an_unknown_session_is_still_404(tmp_path: Path) -> None:
    with app_on(tmp_path) as client:
        body = {
            "query_text": "cancel", "action": "cancel_jobs", "target_refs": ["group#CS-101"],
            "session_id": "sess-00000000000000ff",
        }  # fmt: skip
        response = client.post(DRY_RUNS, json=body)
        assert response.status_code == 404 and response.json()["code"] == "SESSION_NOT_FOUND"
        assert rows(client) == []
