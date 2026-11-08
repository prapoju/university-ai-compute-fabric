"""Zero hallucinated endpoints: the app serves exactly what openapi.yaml declares."""

from __future__ import annotations

import inspect
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
SERVED_IN_THIS_STORY = {
    ("GET", "/healthz"),
    ("GET", "/readyz"),
    # story 1.2: the session lifecycle
    ("POST", "/api/v1/sessions"),
    ("POST", "/api/v1/sessions/{}/queries"),
    ("GET", "/api/v1/sessions/{}"),
    ("DELETE", "/api/v1/sessions/{}"),
    # Impl-1 annex 12.1: the inbound entry point over the same use cases
    ("POST", "/api/v1/copilot/query"),
    ("POST", "/api/v1/copilot/chat"),  # story 2.1
    ("POST", "/api/v1/destructive/dry-runs"),  # story 2.2
    ("POST", "/api/v1/destructive/proposals"),  # story 2.3
    ("GET", "/api/v1/runbooks/{}"),  # story 3.3: the registry read (annex 12.6)
    ("GET", "/api/v1/destructive/proposals/{}"),  # story 2.4
    ("POST", "/api/v1/destructive/proposals/{}/re-dispatches"),  # story 2.4
    ("POST", "/executor/v1/proposals"),  # story 2.4
    ("GET", "/executor/v1/proposals/{}"),  # story 2.4
    # story 1.4
    ("GET", "/api/v1/answers/{}/evidence"),
    ("GET", "/api/v1/citations/{}"),
    # story 1.5
    ("GET", "/api/v1/sessions/{}/audit"),
    ("GET", "/api/v1/state/{}/{}"),
    ("GET", "/api/v1/state/{}"),
}

# AD-13: the only state-mutating routes the contract may declare. Sessions are Module-12-owned
# state; destructive/executor routes are the propose-only flow. Anything else is a violation.
ALLOWED_MUTATING = {
    ("POST", "/api/v1/sessions"),
    ("POST", "/api/v1/sessions/{}/queries"),
    ("POST", "/api/v1/copilot/query"),  # annex 12.1: owned session state only, never the estate
    ("POST", "/api/v1/copilot/chat"),  # annex 12.4: the same, plus the refusal (story 2.1)
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


def _flatten(routes, prefix: str = ""):
    """Every concrete route, descending into routers included with ``include_router``."""
    for route in routes:
        nested = getattr(route, "original_router", None)  # FastAPI's _IncludedRouter wrapper
        if nested is not None:
            context_prefix = getattr(getattr(route, "include_context", None), "prefix", "") or ""
            yield from _flatten(nested.routes, prefix + context_prefix)
        elif hasattr(route, "methods"):
            yield prefix + route.path, route.methods


def _served_operations() -> set[tuple[str, str]]:
    """Every method+path the app answers, whatever kind of route object serves it."""
    app = create_app(Settings.from_env({}))
    served = {
        (method, _normalise(path))
        for path, methods in _flatten(app.routes)
        for method in methods
        if method not in {"HEAD", "OPTIONS"}
    }
    # cross-check with the schema FastAPI generates from the same routes
    from_schema = {
        (method.upper(), _normalise(path))
        for path, item in app.openapi()["paths"].items()
        for method in item
        if method in HTTP_METHODS
    }
    assert from_schema <= served, (
        f"generated schema lists routes the audit missed: {from_schema - served}"
    )
    return served


def test_every_served_route_is_declared_in_the_contract() -> None:
    undeclared = _served_operations() - _contract_operations()
    assert not undeclared, f"routes not in openapi.yaml: {sorted(undeclared)}"


def test_exactly_the_routes_of_this_story_are_served() -> None:
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
    assert probes == {("GET", "/healthz"), ("GET", "/readyz")}  # both GET: they change no state


def test_every_route_served_in_this_story_is_declared_with_the_same_method() -> None:
    assert SERVED_IN_THIS_STORY <= _contract_operations()


# -- story 1.6 (log I2-35): the parallel read fan-out runs asyncio.run in the worker thread ----
# asyncio.run raises inside a running event loop, so every handler that can reach
# ParallelReads.run must be a sync ``def``. The app has no async route today; this pins it.
FAN_OUT_ROUTES = {
    ("POST", "/api/v1/copilot/query"),
    ("POST", "/api/v1/copilot/chat"),
    ("POST", "/api/v1/sessions/{}/queries"),
}


def _endpoints(routes, prefix: str = ""):
    """(method, normalised path, endpoint) for every concrete route, as in ``_flatten``."""
    for route in routes:
        nested = getattr(route, "original_router", None)
        if nested is not None:
            context_prefix = getattr(getattr(route, "include_context", None), "prefix", "") or ""
            yield from _endpoints(nested.routes, prefix + context_prefix)
        elif hasattr(route, "methods"):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                yield method, _normalise(prefix + route.path), route.endpoint


def test_every_served_handler_is_sync_so_the_read_fan_out_can_run_its_loop() -> None:
    app = create_app(Settings.from_env({}))
    endpoints = list(_endpoints(app.routes))
    async_handlers = sorted(
        (method, path) for method, path, endpoint in endpoints
        if inspect.iscoroutinefunction(endpoint)
    )  # fmt: skip
    assert async_handlers == [], f"async handlers would break ParallelReads.run: {async_handlers}"
    served = {(method, path) for method, path, _ in endpoints}
    assert FAN_OUT_ROUTES <= served, f"fan-out routes not served: {FAN_OUT_ROUTES - served}"
