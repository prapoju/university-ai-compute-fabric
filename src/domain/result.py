"""Typed ``ok | failure`` results (AD-12, contracts.md section 3 ``Q-fail``).

A failure aborts the pipeline before prose and never carries partial data, so callers branch
on the result instead of catching exceptions. Pure value types: no I/O, no framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeGuard, TypeVar, get_args

from src.dto import ErrorCode

T = TypeVar("T")

_CATALOG_CODES = frozenset(get_args(ErrorCode))


@dataclass(frozen=True)
class Ok(Generic[T]):  # noqa: UP046 - kept explicit; PEP 695 syntax adds nothing here
    """A successful read. ``Ok(None)`` is a single-record miss (Q-port-1)."""

    value: T


@dataclass(frozen=True)
class Failure:
    """A typed dependency or validation failure from the section 4 error catalog."""

    code: str
    observed: tuple[str, ...] = ()
    message: str | None = None  # rendered contract message (error_catalog.fail); optional

    def __post_init__(self) -> None:
        if self.code not in _CATALOG_CODES:
            raise ValueError(f"{self.code!r} is not in the typed error catalog (contracts.md s4)")


Result = Ok[T] | Failure


def is_ok(result: object) -> TypeGuard[Ok]:
    return isinstance(result, Ok)


def is_failure(result: object) -> TypeGuard[Failure]:
    return isinstance(result, Failure)
