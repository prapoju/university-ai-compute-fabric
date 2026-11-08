"""Story 2.3 - the confirm route beyond the ATDD: its body model and a database that cannot open."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.application.unavailable import UnavailableConfirmUseCases
from src.config import Settings
from src.domain.result import Failure

pytestmark = pytest.mark.api

CONFIRMS = "/api/v1/destructive/proposals"
TOKEN = "gt-" + "ab" * 16


@pytest.fixture()
def client():
    with TestClient(create_app(Settings.from_env({})), raise_server_exceptions=False) as client:
        yield client


def test_a_body_without_a_field_or_with_a_wrong_type_is_malformed(client) -> None:
    for body in (
        {},
        {"proposal_id": "prop-0000000000000001"},
        {"gate_token": TOKEN},
        {"proposal_id": 7, "gate_token": TOKEN},
        {"proposal_id": "prop-0000000000000001", "gate_token": 7},
    ):
        response = client.post(CONFIRMS, json=body)
        assert response.status_code == 400, body
        assert response.json()["code"] == "VALIDATION_MALFORMED_BODY"


def test_a_malformed_proposal_id_is_not_found_not_a_schema_error(client) -> None:
    response = client.post(CONFIRMS, json={"proposal_id": "not-an-id", "gate_token": TOKEN})
    assert response.status_code == 404 and response.json()["code"] == "PROPOSAL_NOT_FOUND"


def test_a_confirm_for_an_unknown_proposal_names_it_and_leaks_nothing_else(client) -> None:
    response = client.post(
        CONFIRMS, json={"proposal_id": "prop-00000000000000ff", "gate_token": TOKEN}
    )
    assert response.json()["message"] == "Proposal prop-00000000000000ff not found."
    assert TOKEN not in response.text


def test_the_confirm_route_is_the_typed_failure_when_the_database_cannot_open(tmp_path) -> None:
    settings = Settings.from_env({"M12_DB_PATH": str(tmp_path / "missing" / "m12.db")})
    with TestClient(create_app(settings), raise_server_exceptions=False) as broken:
        response = broken.post(
            CONFIRMS, json={"proposal_id": "prop-0000000000000001", "gate_token": TOKEN}
        )
        assert response.status_code == 503 and response.json()["code"] == "PROVIDER_UNAVAILABLE"


def test_the_unavailable_stand_in_answers_the_typed_failure() -> None:
    result = UnavailableConfirmUseCases("database down").post_confirm(
        "prop-0000000000000001", TOKEN
    )
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert result.observed == ("database down",)
