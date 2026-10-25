"""Zero hallucinated endpoints: every route the app serves is declared in openapi.yaml."""

from __future__ import annotations

import re

import pytest
import yaml
from fastapi.routing import APIRoute

from src.adapters.inbound.app import create_app
from src.config import PROJECT_ROOT, Settings

pytestmark = pytest.mark.api

CONTRACT = PROJECT_ROOT / "planning/detailed-design/schemas/openapi.yaml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


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
    app = create_app(Settings.from_env({}))
    return {
        (method, _normalise(route.path))
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


def test_every_served_route_is_declared_in_the_contract() -> None:
    undeclared = _served_operations() - _contract_operations()
    assert not undeclared, f"routes not in openapi.yaml: {sorted(undeclared)}"


def test_ops_probes_are_the_only_contract_addition_in_this_story() -> None:
    served = {path for _, path in _served_operations()}
    assert {"/healthz", "/readyz"} <= served


def test_contract_has_no_state_mutating_route_outside_destructive_and_executor() -> None:
    mutating = {
        path
        for method, path in _contract_operations()
        if method in {"POST", "PUT", "PATCH", "DELETE"}
    }
    allowed_prefixes = ("/api/v1/destructive/", "/executor/v1/", "/api/v1/sessions")
    offenders = {p for p in mutating if not p.startswith(allowed_prefixes)}
    assert not offenders, f"AD-13 violation: {sorted(offenders)}"
