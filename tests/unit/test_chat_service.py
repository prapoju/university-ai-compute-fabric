"""Story 2.2 - the chat composition: refusal first, dry-run second, anything else untouched (D8)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.application.chat_service import ChatService
from src.config import Settings
from src.domain.result import Failure, Ok
from src.dto import ChatRefusalResponse, DryRunSnapshotDTO, ProposalDTO, SelectorDTO
from src.ports.inbound import (
    CanonicalOutcome,
    ChatRefusal,
    DestructiveUseCases,
    DryRunOutcome,
    SessionUseCases,
)

pytestmark = pytest.mark.unit

ANNEX = "Terminate all active jobs for CS-101"
CHAT = "/api/v1/copilot/chat"
DOWN = Failure("PROVIDER_UNAVAILABLE", observed=("down",))


class Sessions(SessionUseCases):
    def __init__(self, outcome) -> None:
        self.outcome, self.created = outcome, 0

    def create_session(self, operator_role):
        self.created += 1
        return Ok(type("S", (), {"session_id": "sess-0000000000000001"})())

    def submit_query(self, session_id, query_text):
        return self.outcome

    def get_session(self, session_id):  # pragma: no cover
        raise NotImplementedError

    def reset_session(self, session_id):  # pragma: no cover
        raise NotImplementedError


class Destructive(DestructiveUseCases):
    def __init__(self, result) -> None:
        self.result, self.requests = result, []

    def post_dry_run(self, *args):  # pragma: no cover
        raise NotImplementedError

    def dry_run_request(self, session_id, request):
        self.requests.append((session_id, request))
        return self.result


def outcome() -> DryRunOutcome:
    proposal = ProposalDTO(
        proposal_id="prop-0000000000000001",
        session_id="sess-0000000000000001",
        state="dry_run",
        action="cancel_jobs",
        dry_run_snapshot=DryRunSnapshotDTO(
            selector=SelectorDTO(method="jobs_port.select", params={}),
            affected_items=[],
            snapshot_timestamp="2026-10-16T15:00:00.000Z",
        ),
        gate_token="gt-" + "a" * 32,
    )
    return DryRunOutcome(proposal, "0 affected items", "2026-10-16T15:01:00.000Z", False)


REFUSED = CanonicalOutcome("ACTION_REFUSED", "Action refused.")


def test_a_refused_destructive_request_gets_its_dry_run_for_the_parsed_request() -> None:
    destructive = Destructive(Ok(outcome()))
    result = ChatService(sessions=Sessions(Ok(REFUSED)), destructive=destructive).chat("r", ANNEX)
    assert isinstance(result.value, ChatRefusal) and result.value.refusal == REFUSED
    [(sid, request)] = destructive.requests
    assert sid == "sess-0000000000000001"
    assert (request.verb, request.target.kind) == ("cancel_jobs", "group")


@pytest.mark.parametrize(
    "submitted",
    [
        Ok(CanonicalOutcome("CLARIFICATION_REQUIRED", "Clarification required: x.")),
        Ok(CanonicalOutcome("ENTITY_NOT_FOUND", "Entity Not Found in State: group#nope.")),
        DOWN,
    ],
)
def test_every_other_outcome_is_returned_untouched_and_runs_no_dry_run(submitted) -> None:
    destructive = Destructive(Ok(outcome()))
    result = ChatService(sessions=Sessions(submitted), destructive=destructive).chat("r", ANNEX)
    assert result == submitted and destructive.requests == []


def test_a_query_that_is_not_a_destructive_request_is_returned_as_the_refusal() -> None:
    destructive = Destructive(Ok(outcome()))
    service = ChatService(sessions=Sessions(Ok(REFUSED)), destructive=destructive)
    assert service.chat("r", "why was alex denied deepseek-coder").value == REFUSED
    assert destructive.requests == []  # nothing to dry-run: stay safe, never invent a target


def test_a_session_that_cannot_open_is_the_typed_failure() -> None:
    class Closed(Sessions):
        def create_session(self, operator_role):
            return DOWN

    service = ChatService(sessions=Closed(Ok(REFUSED)), destructive=Destructive(Ok(outcome())))
    assert service.chat("r", ANNEX) == DOWN


def test_a_failed_dry_run_is_that_failure_and_a_canonical_dry_run_is_passed_on() -> None:
    failed = ChatService(sessions=Sessions(Ok(REFUSED)), destructive=Destructive(DOWN))
    assert failed.chat("r", ANNEX) == DOWN
    gone = Ok(CanonicalOutcome("ENTITY_NOT_FOUND", "Entity Not Found in State: group#cs-101."))
    passed = ChatService(sessions=Sessions(Ok(REFUSED)), destructive=Destructive(gone))
    assert passed.chat("r", ANNEX) == gone


# -- the wire shape ------------------------------------------------------------------------------
@pytest.fixture()
def client():
    with TestClient(create_app(Settings.from_env({})), raise_server_exceptions=False) as client:
        yield client


def test_the_annex_reply_is_a_valid_chat_refusal_response(client) -> None:
    response = client.post(CHAT, json={"query": ANNEX})
    parsed = ChatRefusalResponse.model_validate(response.json())
    assert parsed.refusal.code == "ACTION_REFUSED" and parsed.refusal.status == 200
    assert parsed.proposal.state == "dry_run" and parsed.confirmation_enabled is True


def test_the_chat_route_keeps_the_other_shapes(client) -> None:
    clarification = client.post(CHAT, json={"query": "cancel the jobs of CS-101 and show alex"})
    assert clarification.json()["code"] == "CLARIFICATION_REQUIRED"
    answer = client.post(CHAT, json={"query": "why was alex denied deepseek-coder"})
    assert "answers" in answer.json()
    assert client.post(CHAT, json={"query": "  "}).status_code == 400


def test_the_chat_route_is_the_typed_failure_when_the_database_cannot_open(tmp_path) -> None:
    settings = Settings.from_env({"M12_DB_PATH": str(tmp_path / "missing" / "m12.db")})
    with TestClient(create_app(settings), raise_server_exceptions=False) as broken:
        response = broken.post(CHAT, json={"query": ANNEX})
        assert response.status_code == 503 and response.json()["code"] == "PROVIDER_UNAVAILABLE"
