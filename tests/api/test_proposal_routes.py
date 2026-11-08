"""Story 2.4 - proposal and executor routes beyond the ATDD: bodies, races, a dead database."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.application.unavailable import UnavailableExecutor, UnavailableProposalUseCases
from src.config import Settings
from src.domain.result import Failure
from src.dto import ExecutorRequestDTO, SelectorDTO
from src.ports.outbound import ExecutorPort

pytestmark = pytest.mark.api

CHAT = "/api/v1/copilot/chat"
PROPOSALS = "/api/v1/destructive/proposals"
EXECUTOR = "/executor/v1/proposals"
ANNEX = "Terminate all active jobs for CS-101"
TOKEN = "gt-" + "ab" * 16


@pytest.fixture()
def client():
    with TestClient(create_app(Settings.from_env({})), raise_server_exceptions=False) as client:
        yield client


def proposal(client: TestClient) -> dict:
    return client.post(CHAT, json={"query": ANNEX}).json()["proposal"]


def failed_parent(client: TestClient) -> dict:
    parent = proposal(client)
    executor = client.app.state.container.port(ExecutorPort)
    executor.down = True
    body = {"proposal_id": parent["proposal_id"], "gate_token": parent["gate_token"]}
    assert client.post(PROPOSALS, json=body).status_code == 503
    executor.down = False
    return parent


def redispatch(client: TestClient, pid: str, **override):
    body = {"query_text": "cancel", "action": "cancel_jobs", "target_refs": ["group#CS-101"]}
    return client.post(f"{PROPOSALS}/{pid}/re-dispatches", json={**body, **override})


# -- the re-dispatch body --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "override",
    [
        {"action": "nuke_jobs"},
        {"target_refs": []},
        {"target_refs": [f"node#n{i}" for i in range(51)]},
        {"role": "admin"},
        {"query_text": "   "},
    ],
    ids=["unknown-action", "no-target", "too-many-refs", "extra-field", "blank-query"],
)
def test_a_bad_re_dispatch_request_is_a_400_and_leaves_the_parent_failed(client, override) -> None:
    parent = failed_parent(client)
    response = redispatch(client, parent["proposal_id"], **override)
    assert response.status_code == 400
    after = client.get(f"{PROPOSALS}/{parent['proposal_id']}").json()
    assert after["state"] == "failed"  # the parent is superseded only by a child that exists


def test_a_re_dispatch_naming_nothing_that_exists_is_entity_not_found_and_keeps_the_parent(
    client,
) -> None:
    parent = failed_parent(client)
    response = redispatch(client, parent["proposal_id"], target_refs=["group#nope"])
    assert response.status_code == 200 and response.json()["code"] == "ENTITY_NOT_FOUND"
    assert client.get(f"{PROPOSALS}/{parent['proposal_id']}").json()["state"] == "failed"


def test_only_one_of_two_simultaneous_re_dispatches_of_a_parent_wins(client) -> None:
    parent = failed_parent(client)
    barrier = threading.Barrier(2)

    def run(_: int):
        barrier.wait(timeout=30)
        return redispatch(client, parent["proposal_id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(run, range(2)))
    assert sorted(r.status_code for r in replies) == [200, 409]
    assert client.get(f"{PROPOSALS}/{parent['proposal_id']}").json()["state"] == "superseded"


def test_a_re_dispatch_audits_its_dry_run_and_names_the_parent(client) -> None:
    parent = failed_parent(client)
    child = redispatch(client, parent["proposal_id"]).json()
    entries = client.get(
        f"/api/v1/sessions/{parent['session_id']}/audit", params={"page_size": 100}
    ).json()["entries"]
    head = [
        e
        for e in entries
        if e["result_summary"]["tool_name"] == "toolcall.propose_destructive_action"
    ][-1]
    assert head["result_summary"]["supersedes"] == parent["proposal_id"]
    assert child["supersedes_proposal_id"] == parent["proposal_id"]
    assert child["gate_token"] not in str(entries)


# -- the executor routes ---------------------------------------------------------------------------
def test_the_executor_post_takes_only_the_frozen_request(client) -> None:
    for body in ([], "text", 7, None):
        response = client.post(EXECUTOR, json=body)
        assert response.status_code == 400, body
    assert client.post(EXECUTOR, json={}).json()["code"] == "VALIDATION_MALFORMED_BODY"


def test_the_executor_routes_answer_the_typed_failure_when_the_database_cannot_open(
    tmp_path,
) -> None:
    settings = Settings.from_env({"M12_DB_PATH": str(tmp_path / "missing" / "m12.db")})
    with TestClient(create_app(settings), raise_server_exceptions=False) as broken:
        pid = "prop-0000000000000001"
        for response in (
            broken.get(f"{PROPOSALS}/{pid}"),
            broken.post(f"{PROPOSALS}/{pid}/re-dispatches", json={
                "query_text": "x", "action": "cancel_jobs", "target_refs": ["group#CS-101"]}),
            broken.get(f"{EXECUTOR}/{pid}"),
        ):  # fmt: skip
            assert response.status_code == 503, response.text
        assert broken.get(f"{EXECUTOR}/{pid}").json()["code"] == "EXECUTOR_UNAVAILABLE"


def test_the_unavailable_stand_ins_answer_typed_failures() -> None:
    use_cases = UnavailableProposalUseCases("database down")
    for result in (
        use_cases.get_proposal("prop-0000000000000001"),
        use_cases.post_re_dispatch("prop-0000000000000001", "x", "cancel_jobs", ["g"]),
    ):
        assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    executor = UnavailableExecutor("database down")
    request = ExecutorRequestDTO(
        proposal_id="prop-0000000000000001", action="cancel_jobs",
        selector=SelectorDTO(method="jobs_port.select", params={}), gate_token=TOKEN,
        dry_run_ref={"proposal_id": "prop-0000000000000001"},
    )  # fmt: skip
    for outcome in (executor.dispatch(request), executor.get("prop-0000000000000001")):
        assert isinstance(outcome, Failure) and outcome.code == "EXECUTOR_UNAVAILABLE"
