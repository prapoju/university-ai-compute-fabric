"""Story 1.2 ports: id generation (OP-13), the session store and the inbound use cases."""

from __future__ import annotations

import inspect
from abc import ABC

import pytest

from src.ports.inbound import SessionUseCases
from src.ports.inbound.session_use_cases import CanonicalOutcome
from src.ports.outbound import IdGenPort, SessionStorePort, StoredSession

pytestmark = pytest.mark.unit


def _methods(cls: type) -> set[str]:
    return {n for n, _ in inspect.getmembers(cls, inspect.isfunction) if not n.startswith("_")}


def test_the_session_use_cases_are_exactly_the_four_session_operations() -> None:
    assert issubclass(SessionUseCases, ABC) and inspect.isabstract(SessionUseCases)
    assert _methods(SessionUseCases) == {
        "create_session",
        "submit_query",
        "get_session",
        "reset_session",
    }


@pytest.mark.parametrize("cls", [SessionUseCases, SessionStorePort, IdGenPort])
def test_every_operation_returns_a_typed_result(cls: type) -> None:
    for name in _methods(cls):
        annotation = str(inspect.signature(getattr(cls, name)).return_annotation)
        assert annotation.startswith("Result["), f"{cls.__name__}.{name} -> {annotation}"


def test_the_inbound_ports_signatures_carry_primitives_and_dtos_only() -> None:
    # R4: no framework object (Request/Response) may appear in a port signature
    for name in _methods(SessionUseCases):
        for parameter in inspect.signature(getattr(SessionUseCases, name)).parameters.values():
            assert "Request" not in str(parameter.annotation)
            assert "Response" not in str(parameter.annotation)


def test_value_types_are_immutable_dataclasses() -> None:
    outcome = CanonicalOutcome(code="CLARIFICATION_REQUIRED", message="m")
    with pytest.raises(AttributeError):
        outcome.code = "x"  # type: ignore[misc]
    stored = StoredSession(session=None, last_turn_at=None)  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        stored.last_turn_at = "x"  # type: ignore[misc]
