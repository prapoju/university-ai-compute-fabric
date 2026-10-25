"""Health probes and the structured error envelope (Impl-1 §1 "health probes")."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import Settings

pytestmark = pytest.mark.api

PROBLEM_LITERAL = "Provider unavailable — cannot answer."


def _client(settings: Settings | None = None, **kwargs) -> TestClient:
    return TestClient(create_app(settings or Settings.from_env({})), **kwargs)


def test_healthz_is_a_liveness_probe_that_needs_no_dependencies(tmp_path: Path) -> None:
    broken = Settings.from_env({"M12_FIXTURES_DIR": str(tmp_path / "absent")})
    response = _client(broken).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_reports_every_check_when_the_service_is_ready() -> None:
    response = _client().get("/readyz")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ready"
    assert body["checks"] == {
        "dependencies": "ok",
        "migrations": "ok",
        "estate": "ok",
        "clock": "ok",
    }


def test_probing_readiness_does_not_consume_clock_read_ids() -> None:
    app = create_app(Settings.from_env({}))
    client = TestClient(app)
    for _ in range(3):
        client.get("/readyz")
    from src.ports.outbound import ClockPort

    first = app.state.container.port(ClockPort).now().value
    assert first.read_id == "clk-0000000000000001"


def test_readyz_is_503_when_the_estate_cannot_load(tmp_path: Path) -> None:
    empty = Settings.from_env({"M12_FIXTURES_DIR": str(tmp_path)})
    body = _client(empty).get("/readyz").json()
    assert body["code"] == "PROVIDER_UNAVAILABLE"
    assert any(o.startswith("estate:") for o in body["explanation"]["observed_values"])


def test_readyz_is_503_with_a_structured_error_when_a_dependency_is_missing(tmp_path: Path) -> None:
    broken = Settings.from_env({"M12_FIXTURES_DIR": str(tmp_path / "absent")})
    response = _client(broken).get("/readyz")
    body = response.json()
    assert response.status_code == 503
    assert body["code"] == "PROVIDER_UNAVAILABLE"
    assert body["status"] == 503
    assert body["retryable"] is True
    assert body["message"] == PROBLEM_LITERAL
    assert "absent" in body["explanation"]["observed_values"][0]


def test_unexpected_errors_never_leak_a_stack_trace() -> None:
    app = create_app(Settings.from_env({}))

    @app.get("/_boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    response = TestClient(app, raise_server_exceptions=False).get("/_boom")
    assert response.status_code == 503
    assert response.json()["code"] == "PROVIDER_UNAVAILABLE"
    assert "secret internal detail" not in response.text
    assert "Traceback" not in response.text


def test_request_validation_errors_use_the_contract_400_envelope() -> None:
    app = create_app(Settings.from_env({}))

    @app.get("/_number/{n}")
    def number(n: int) -> dict[str, int]:
        return {"n": n}

    response = TestClient(app).get("/_number/not-a-number")
    body = response.json()
    assert response.status_code == 400
    assert body["code"] == "VALIDATION_MALFORMED_BODY"
    assert body["retryable"] is False


def test_the_app_refuses_to_start_when_the_runtime_is_fatally_broken(monkeypatch) -> None:
    from src import dependency_check

    monkeypatch.setattr(dependency_check.sqlite3, "sqlite_version", "3.1.0")
    with pytest.raises(dependency_check.DependencyError, match="3.1.0"):
        create_app(Settings.from_env({}))


def test_the_app_starts_without_fixtures_and_says_not_ready(tmp_path: Path) -> None:
    app = create_app(Settings.from_env({"M12_FIXTURES_DIR": str(tmp_path / "absent")}))
    assert TestClient(app).get("/readyz").status_code == 503


def test_unknown_routes_and_wrong_methods_use_the_error_envelope_too() -> None:
    client = _client()
    missing = client.get("/nope")
    assert missing.status_code == 404
    assert missing.json()["code"] == "ENTITY_NOT_FOUND"
    assert set(missing.json()) == {"code", "status", "message", "retryable", "explanation"}
    wrong = client.post("/healthz")
    assert wrong.status_code == 405
    assert wrong.json()["code"] == "VALIDATION_MALFORMED_BODY"
    assert wrong.json()["status"] == 405 and wrong.json()["retryable"] is False


def test_unexpected_errors_are_logged_server_side_but_not_returned(caplog) -> None:
    app = create_app(Settings.from_env({}))

    @app.get("/_boom2")
    def boom() -> None:
        raise RuntimeError("diagnostic detail only for logs")

    with caplog.at_level("ERROR", logger="src"):
        response = TestClient(app, raise_server_exceptions=False).get("/_boom2")
    assert "diagnostic detail only for logs" not in response.text
    assert any("diagnostic detail only for logs" in (r.exc_text or "") for r in caplog.records)
