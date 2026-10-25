"""Story 1.1 - the adapters hold no write path and reads never change the estate (AD-1, AD-13).

Scenario: Ports are query-only (AD-1 / AD-13)
"""

from __future__ import annotations

import inspect
import re

import pytest

from src.adapters.outbound.sim.fixtures_adapter import SimProviders
from src.domain.result import is_ok
from src.dto import SelectorDTO
from src.ports.outbound import EventWindow

pytestmark = pytest.mark.unit

MUTATION = re.compile(
    r"(register|set|add|put|post|update|patch|delete|remove|write|create|apply|save|insert"
    r"|cordon|drain|schedule|reserve|enforce|dispatch)",
    re.IGNORECASE,
)

PORT_FIELDS = (
    "users", "catalog", "policy", "groups", "jobs", "nodes", "reservations", "windows",
    "event_store", "policy_content", "runbook_registry",
)  # fmt: skip


def _public_methods(obj: object) -> set[str]:
    return {n for n, _ in inspect.getmembers(obj, inspect.ismethod) if not n.startswith("_")}


@pytest.mark.parametrize("field", PORT_FIELDS)
def test_adapters_expose_only_the_port_read_methods(providers: SimProviders, field: str) -> None:
    adapter = getattr(providers, field)
    port_methods = {
        n for base in type(adapter).__mro__[1:] if inspect.isabstract(base)
        for n, _ in inspect.getmembers(base, inspect.isfunction) if not n.startswith("_")
    }  # fmt: skip
    assert _public_methods(adapter) == port_methods
    assert not [m for m in _public_methods(adapter) if MUTATION.search(m)]


def _battery(p: SimProviders) -> list[object]:
    window = EventWindow("2026-10-16T00:00:00.000Z", "2026-10-17T00:00:00.000Z")
    selector = SelectorDTO(method="filter", params={"status": "pending"})
    return [
        p.users.get("user#alex"), p.users.browse("", 1, 100), p.catalog.browse("", 1, 100),
        p.policy.for_model("model#deepseek-coder"), p.groups.browse("", 1, 100),
        p.jobs.select(selector), p.nodes.browse("", 1, 100), p.reservations.browse("", 1, 100),
        p.windows.list(), p.event_store.query("user#alex", "access_denied", window),
        p.policy_content.get("policy#night.2"), p.runbook_registry.get("ERR_THERMAL_88"),
    ]  # fmt: skip


def test_a_battery_of_reads_leaves_the_estate_identical(providers: SimProviders) -> None:
    before = providers.estate_snapshot()
    for _ in range(3):
        assert all(is_ok(r) for r in _battery(providers))
    assert providers.estate_snapshot() == before


def test_mutating_a_returned_record_cannot_corrupt_the_estate(providers: SimProviders) -> None:
    before = providers.estate_snapshot()
    alex = providers.users.get("user#alex").value
    alex.role = "privileged"  # the caller scribbles on its copy
    nodes = providers.nodes.browse("", 1, 100).value
    nodes.clear()
    assert providers.users.get("user#alex").value.role == "student"
    assert len(providers.nodes.browse("", 1, 100).value) == 32
    assert providers.estate_snapshot() == before


def test_loading_twice_gives_identical_ordered_data(providers: SimProviders) -> None:
    again = SimProviders.from_fixtures(providers.fixtures_dir, "2026-10-16T15:00:00.000Z")
    assert again.estate_snapshot() == providers.estate_snapshot()
