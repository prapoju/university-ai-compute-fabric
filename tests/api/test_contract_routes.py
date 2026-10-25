"""Zero hallucinated endpoints: the app serves exactly what openapi.yaml declares."""

from __future__ import annotations

import re

import pytest
import yaml
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import PROJECT_ROOT, Settings

pytestmark = pytest.mark.api

CONTRACT = PROJECT_ROOT / "planning/detailed-design/schemas/openapi.yaml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}

# Routes added by this story (Impl-1 probes). Grows only when a story adds a contract route.
SERVED_IN_THIS_STORY = {("GET", "/healthz"), ("GET", "/readyz")}

# AD-13: the only state-mutating routes the contract may declare. Sessions are Module-12-owned
# state; destructive/executor routes are the propose-only flow. Anything else is a violation.
ALLOWED_MUTATING = {
    ("POST", "/api/v1/sessions"),
    ("POST", "/api/v1/sessions/{}/queries"),
    ("DELETE", "/api/v1/sessions/{}"),
    ("POST", "/api/v1/destructive/dry-runs"),
    ("POST", "/api/v1/destructive/proposals"),
    ("POST", "/api/v1/destructive/proposals/{}/re-dispatches"),
    ("POST", "/executor/v1/proposals"),
}


def _normalise(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def _contract_operations() -> set[tuple[str, str]]:
    spec = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    return {
        (method.upper(), _normalise(path))
        for path, item in spec["paths"].items()
        for method in item
        if method in HTTP_METHODS
    }


def _served_operations() -> set[tuple[str, str]]:
    """Every method+path the app answers, whatever kind of route object serves it."""
    app = create_app(Settings.from_env({}))
    return {
        (method, _normalise(route.path))
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
    }


def test_every_served_route_is_declared_in_the_contract() -> None:
    undeclared = _served_operations() - _contract_operations()
    assert not undeclared, f"routes not in openapi.yaml: {sorted(undeclared)}"


def test_exactly_the_ops_probes_are_served_in_this_story() -> None:
    assert _served_operations() == SERVED_IN_THIS_STORY


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"])
def test_framework_generated_documentation_routes_are_not_served(path: str) -> None:
    client = TestClient(create_app(Settings.from_env({})))
    assert client.get(path).status_code == 404


def test_the_contract_declares_no_mutating_route_outside_the_allowed_flows() -> None:
    mutating = {
        (m, p) for m, p in _contract_operations() if m in {"POST", "PUT", "PATCH", "DELETE"}
    }
    assert mutating - ALLOWED_MUTATING == set(), "AD-13: undeclared mutating route"
    assert mutating <= ALLOWED_MUTATING


def test_health_probes_are_read_only() -> None:
    probes = {op for op in _contract_operations() if op[1] in {"/healthz", "/readyz"}}
    assert probes == SERVED_IN_THIS_STORY  # both GET: they change no state
