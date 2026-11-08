"""Story 2.2 - the dry-run route beyond the ATDD: refs, kinds, sessions and the audit (D11, D12)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.application.unavailable import UnavailableDestructiveUseCases
from src.config import Settings
from src.domain.result import Failure
from src.domain.safety import DestructiveRequest, Fleet, Target

pytestmark = pytest.mark.api

DRY_RUNS = "/api/v1/destructive/dry-runs"
SESSIONS = "/api/v1/sessions"
QUERY = "cancel the jobs"


@pytest.fixture()
def client():
    with TestClient(create_app(Settings.from_env({})), raise_server_exceptions=False) as client:
        yield client


def open_session(client: TestClient) -> str:
    return client.post(SESSIONS, json={"operator_role": "role-operations"}).json()["session_id"]


def post(client: TestClient, sid: str, action: str, refs: list[str], text: str = QUERY):
    body = {"query_text": text, "action": action, "target_refs": refs, "session_id": sid}
    return client.post(DRY_RUNS, json=body)


def keys(response) -> list[str]:
    return [i["key"] for i in response.json()["dry_run_snapshot"]["affected_items"]]


def selector(response) -> dict:
    return response.json()["dry_run_snapshot"]["selector"]


# -- bare refs resolve for the action (D11) --------------------------------------------------------
def test_a_bare_group_ref_resolves_as_a_group(client) -> None:
    response = post(client, open_session(client), "cancel_jobs", ["CS-101"])
    assert response.status_code == 200
    assert selector(response)["params"] == {"group_id": "group#CS-101", "status": "running"}
    assert len(keys(response)) == 3


def test_a_bare_ref_that_is_not_a_group_resolves_as_a_job(client) -> None:
    response = post(client, open_session(client), "cancel_jobs", ["job-8830"])
    assert selector(response) == {"method": "jobs_port.select", "params": {"id": "job#job-8830"}}
    assert keys(response) == ["job#job-8830"]


def test_a_bare_ref_for_a_node_verb_is_a_node(client) -> None:
    response = post(client, open_session(client), "cordon_node", ["ws-gpu-02"])
    assert selector(response) == {
        "method": "nodes_port.select",
        "params": {"node_ids": ["node#ws-gpu-02"]},
    }


def test_a_bare_ref_that_names_nothing_is_entity_not_found(client) -> None:
    response = post(client, open_session(client), "cancel_jobs", ["nowhere"])
    assert response.status_code == 200 and response.json()["code"] == "ENTITY_NOT_FOUND"
    assert "nowhere" in response.json()["message"]


# -- several refs ------------------------------
def test_several_refs_of_one_kind_give_a_list_filter(client) -> None:
    response = post(
        client, open_session(client), "cordon_node", ["node#ws-gpu-02", "node#ws-gpu-05"]
    )
    assert selector(response)["params"] == {"node_ids": ["node#ws-gpu-02", "node#ws-gpu-05"]}
    assert keys(response) == ["node#ws-gpu-02", "node#ws-gpu-05"]


def test_refs_of_different_kinds_are_a_clarification(client) -> None:
    sid = open_session(client)
    response = post(client, sid, "cancel_jobs", ["group#CS-101", "job#job-8830"])
    assert response.status_code == 200 and response.json()["code"] == "CLARIFICATION_REQUIRED"
    assert "different kinds" in response.json()["message"]
    typed_and_bare = post(client, sid, "cancel_jobs", ["group#CS-101", "job-8830"])
    assert typed_and_bare.json()["code"] == "CLARIFICATION_REQUIRED"


def test_every_unresolved_ref_is_named_once_in_input_order(client) -> None:
    response = post(
        client, open_session(client), "cordon_node", ["node#b", "node#ws-gpu-02", "node#a"]
    )
    assert response.json()["code"] == "ENTITY_NOT_FOUND"
    assert response.json()["message"].index("node#b") < response.json()["message"].index("node#a")


def test_an_unknown_kind_prefix_is_not_a_target(client) -> None:
    response = post(client, open_session(client), "cancel_jobs", ["user#alex"])
    assert response.json()["code"] == "ENTITY_NOT_FOUND"


# -- review P-1, P-2: a request reads and audits each distinct ref once ---------------------------
def audit_tools(client: TestClient, sid: str) -> list[str]:
    entries = client.get(f"{SESSIONS}/{sid}/audit", params={"page_size": 100}).json()["entries"]
    return [e["result_summary"]["tool_name"] for e in entries]


def test_a_repeated_ref_is_one_target_and_one_read(client) -> None:
    sid = open_session(client)
    response = post(client, sid, "cordon_node", ["node#ws-gpu-02", "node#ws-gpu-02", "ws-gpu-02"])
    assert selector(response)["params"] == {"node_ids": ["node#ws-gpu-02"]}
    assert audit_tools(client, sid).count("toolcall.nodes_port.get") == 2  # typed once, bare once


def test_a_bare_group_ref_is_looked_up_once(client) -> None:
    sid = open_session(client)
    post(client, sid, "cancel_jobs", ["CS-101"])
    assert audit_tools(client, sid) == [
        "toolcall.propose_destructive_action",
        "toolcall.groups_port.get",
        "toolcall.jobs_port.select",
    ]


def test_a_bare_job_ref_costs_one_group_miss_and_one_job_hit(client) -> None:
    sid = open_session(client)
    post(client, sid, "cancel_jobs", ["job-8830"])
    assert audit_tools(client, sid) == [
        "toolcall.propose_destructive_action",
        "toolcall.groups_port.get",
        "toolcall.jobs_port.get",
        "toolcall.jobs_port.select",
    ]


def test_a_request_may_name_fifty_refs_and_not_fifty_one(client) -> None:
    sid = open_session(client)
    refs = [f"node#ws-gpu-{n:02d}" for n in range(1, 33)] + [f"node#x{n}" for n in range(18)]
    assert len(refs) == 50
    assert post(client, sid, "cordon_node", refs).json()["code"] == "ENTITY_NOT_FOUND"
    too_many = post(client, sid, "cordon_node", [*refs, "node#one-more"])
    assert too_many.status_code == 400 and too_many.json()["code"] == "VALIDATION_MALFORMED_BODY"
    assert audit_tools(client, sid) == []  # nothing is read for a request that is too large


def test_the_audit_of_a_huge_request_cannot_grow_with_its_repeats(client) -> None:
    sid = open_session(client)
    refs = [f"node#ws-gpu-{n:02d}" for n in range(1, 6)] * 10  # 50 refs, 5 distinct
    assert post(client, sid, "cordon_node", refs).status_code == 200
    assert len(audit_tools(client, sid)) == 1 + 5 + 1  # head, 5 gets, 1 select


# -- the request and the session ------------------------------
def test_a_blank_query_text_is_the_empty_query_error(client) -> None:
    response = post(client, open_session(client), "cancel_jobs", ["group#CS-101"], text="   ")
    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_EMPTY_QUERY"


def test_an_extra_field_is_a_malformed_body(client) -> None:
    body = {"query_text": QUERY, "action": "cancel_jobs", "target_refs": ["x"], "session_id": "s",
            "role": "admin"}  # fmt: skip
    assert client.post(DRY_RUNS, json=body).status_code == 400


def test_a_reset_session_takes_no_dry_run(client) -> None:
    sid = open_session(client)
    client.delete(f"{SESSIONS}/{sid}")
    response = post(client, sid, "cancel_jobs", ["group#CS-101"])
    assert response.status_code == 410 and response.json()["code"] == "SESSION_EXPIRED"


def test_a_verb_that_does_not_fit_the_kind_is_refused_and_writes_nothing(client) -> None:
    sid = open_session(client)
    response = post(client, sid, "drain_node", ["job#job-8830"])
    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_BAD_ACTION"
    assert client.get(f"{SESSIONS}/{sid}/audit").json()["entries"] == []


# -- the audit of a successful dry-run (D12) ------------------------------
def test_the_dry_run_audit_never_holds_the_token_or_the_query(client) -> None:
    sid = open_session(client)
    response = post(client, sid, "cancel_jobs", ["group#CS-101"], text="terminate all active jobs")
    token = response.json()["gate_token"]
    audit = client.get(f"{SESSIONS}/{sid}/audit")
    assert token not in audit.text and "terminate all active jobs" not in audit.text
    head = audit.json()["entries"][0]["result_summary"]
    assert head["tool_name"] == "toolcall.propose_destructive_action"
    assert head["affected_count"] == 3 and head["state"] == "dry_run"


def test_an_empty_set_is_a_proposal_with_no_items(client) -> None:
    response = post(client, open_session(client), "cancel_jobs", ["group#group-2"])
    assert response.status_code == 200
    assert keys(response) == []  # group-2 has no running job
    assert response.json()["state"] == "dry_run"


# -- the use case the chat drives ------------------------------
def test_the_parsed_request_entry_takes_a_named_target_and_a_fleet(client) -> None:
    from src.ports.inbound import DestructiveUseCases, DryRunOutcome

    use_cases = client.app.state.container.port(DestructiveUseCases)
    sid = open_session(client)
    named = use_cases.dry_run_request(
        sid, DestructiveRequest("cancel_jobs", Target("group", "CS-101"))
    ).value
    assert isinstance(named, DryRunOutcome) and named.confirmation_enabled
    assert named.token_expires_at == "2026-10-16T15:01:00.000Z"
    fleet = use_cases.dry_run_request(sid, DestructiveRequest("cordon_node", Fleet("nodes"))).value
    assert fleet.impact_summary == "31 nodes will be cordoned"
    wrong = use_cases.dry_run_request(sid, DestructiveRequest("cancel_jobs", Fleet("nodes")))
    assert isinstance(wrong, Failure) and wrong.code == "VALIDATION_BAD_ACTION"


def test_without_a_database_the_use_case_is_a_typed_failure() -> None:
    use_cases = UnavailableDestructiveUseCases("database down")
    for result in (
        use_cases.post_dry_run(QUERY, "cancel_jobs", ["x"], "sess-0000000000000001"),
        use_cases.dry_run_request(
            "sess-0000000000000001", DestructiveRequest("cancel_jobs", Fleet("jobs"))
        ),
    ):
        assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
