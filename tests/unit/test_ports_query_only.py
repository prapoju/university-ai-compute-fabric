"""Outbound ports declare exactly the contract's read operations and nothing that mutates.

Scenario: Ports are query-only (AD-1 / AD-13). Method sets mirror contracts.md section 3
OP-1..OP-12; every read returns a typed ``Result`` (AD-12).
"""

from __future__ import annotations

import inspect
import re
from abc import ABC

import pytest

from src.ports import outbound

pytestmark = pytest.mark.unit

# contracts.md section 3 - the only permitted read operations per port.
# NOTE: OP-12 also lists `register`, but a port that mutates breaks AD-1; registration is
# validated at fixture-load time instead (story 1.1, decision 2).
CONTRACT_METHODS: dict[str, set[str]] = {
    "UsersPort": {"get", "browse", "by_ids"},
    "CatalogPort": {"get", "browse"},
    "PolicyPort": {"get", "for_model", "browse"},
    "GroupsPort": {"get", "browse"},
    "JobsPort": {"get", "select", "browse"},
    "NodesPort": {"get", "select", "browse"},
    "ReservationsPort": {"get", "browse"},
    "WindowsPort": {"get", "list"},
    "EventStorePort": {"query"},
    "ClockPort": {"now"},
    "PolicyContentPort": {"get"},
    "RunbookRegistryPort": {"get"},
}

# Ports for the Module-12-OWNED stores and id generation. They are not estate providers, so the
# query-only rule (AD-1/AD-13) does not apply to them: AD-1 protects the operational estate.
#  - IdGenPort is OP-13 and LlmProsePort is OP-14 (contracts.md section 3.1); SessionStorePort is an
#    internal port (story 1.2, decision D6).
OWNED_PORT_METHODS: dict[str, set[str]] = {
    "IdGenPort": {"new_id"},
    "LlmProsePort": {"compose"},
    "SessionStorePort": {
        "create", "get", "list_turns", "append_turn", "mark_expired", "reset", "highest_counters",
    },
}  # fmt: skip
ALL_PORTS = {*CONTRACT_METHODS, *OWNED_PORT_METHODS}

MUTATION_WORDS = re.compile(
    r"(register|set|add|put|post|update|patch|delete|remove|write|create|apply|save|insert"
    r"|cordon|drain|schedule|reserve|enforce|dispatch)",
    re.IGNORECASE,
)


def _port_classes() -> dict[str, type]:
    return {
        name: cls
        for name, cls in vars(outbound).items()
        if inspect.isclass(cls) and issubclass(cls, ABC) and name.endswith("Port")
    }


def _public_methods(cls: type) -> set[str]:
    members = inspect.getmembers(cls, inspect.isfunction)
    return {name for name, _ in members if not name.startswith("_")}


def test_there_is_exactly_one_port_per_contract_operation_group() -> None:
    assert set(_port_classes()) == ALL_PORTS
    assert not set(CONTRACT_METHODS) & set(OWNED_PORT_METHODS)


@pytest.mark.parametrize("port_name", sorted(OWNED_PORT_METHODS))
def test_owned_store_ports_declare_exactly_their_documented_methods(port_name: str) -> None:
    assert _public_methods(_port_classes()[port_name]) == OWNED_PORT_METHODS[port_name]


@pytest.mark.parametrize("port_name", sorted(CONTRACT_METHODS))
def test_method_set_equals_the_contract_read_operations(port_name: str) -> None:
    assert _public_methods(_port_classes()[port_name]) == CONTRACT_METHODS[port_name]


@pytest.mark.parametrize("port_name", sorted(CONTRACT_METHODS))
def test_no_method_name_denotes_mutation_or_control_plane_action(port_name: str) -> None:
    offenders = [m for m in _public_methods(_port_classes()[port_name]) if MUTATION_WORDS.search(m)]
    assert offenders == []


@pytest.mark.parametrize("port_name", sorted(ALL_PORTS))
def test_every_read_returns_a_typed_result_never_a_bare_value(port_name: str) -> None:
    cls = _port_classes()[port_name]
    for method in _public_methods(cls):
        annotation = inspect.signature(getattr(cls, method)).return_annotation
        assert str(annotation).startswith("Result["), f"{port_name}.{method} -> {annotation}"


@pytest.mark.parametrize("port_name", sorted(ALL_PORTS))
def test_ports_are_abstract_so_only_adapters_can_implement_them(port_name: str) -> None:
    cls = _port_classes()[port_name]
    assert inspect.isabstract(cls)
    with pytest.raises(TypeError):
        cls()  # type: ignore[abstract]
