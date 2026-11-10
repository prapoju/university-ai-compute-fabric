"""Story 3.3 - ``GET /api/v1/runbooks/{error_code}`` through the real composition root (AD-9)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import Settings
from src.dto import ErrorBody, GetRunbookResponse

pytestmark = pytest.mark.api

FIXTURE = json.loads(
    (Settings.from_env({}).fixtures_dir / "runbooks" / "err-thermal-88.json").read_text(
        encoding="utf-8"
    )
)


def client_for() -> TestClient:
    return TestClient(create_app(Settings.from_env({})), raise_server_exceptions=False)


def test_a_registered_code_returns_steps_and_provenance_as_separate_sections() -> None:
    with client_for() as client:
        response = client.get("/api/v1/runbooks/ERR_THERMAL_88")
    assert response.status_code == 200
    body = GetRunbookResponse.model_validate(response.json())  # extra="forbid"
    assert body.steps == FIXTURE["steps"]  # verbatim, in template order (AD-9)
    assert body.provenance == {"source": FIXTURE["approved_source"], "version": FIXTURE["version"]}
    assert set(response.json()) == {"steps", "provenance"}


def test_an_unknown_code_is_a_404_with_the_canonical_literal_and_no_steps() -> None:
    with client_for() as client:
        response = client.get("/api/v1/runbooks/ERR_NOT_REGISTERED_01")
    assert response.status_code == 404
    body = ErrorBody.model_validate(response.json())
    assert body.code == "RUNBOOK_NOT_FOUND"
    assert body.message == "no runbook available for code ERR_NOT_REGISTERED_01."
    assert "steps" not in response.json()


def test_the_lookup_is_exact_and_never_fuzzy() -> None:
    with client_for() as client:
        response = client.get("/api/v1/runbooks/err_thermal_88")
    assert response.status_code == 404


@pytest.mark.parametrize("code", ["bad!code", "x" * 65])
def test_a_code_outside_the_contract_pattern_is_a_400_before_any_read(code: str) -> None:
    with client_for() as client:
        response = client.get(f"/api/v1/runbooks/{code}")
    assert response.status_code == 400
    assert ErrorBody.model_validate(response.json()).code == "VALIDATION_MALFORMED_BODY"


def test_the_read_is_idempotent() -> None:
    with client_for() as client:
        first = client.get("/api/v1/runbooks/ERR_THERMAL_88").json()
        second = client.get("/api/v1/runbooks/ERR_THERMAL_88").json()
    assert first == second
