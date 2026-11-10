"""Switchable faults at the outbound ports (story 4.2, AD-12).

A fault replaces one method of a Sim adapter **class** with a wrapper that consults a switch. It
returns a typed ``Failure`` (``mode="failure"``) or raises (``mode="raises"``) while the switch is
down, and calls the real method otherwise, so one app can go down and recover.

Install it **before** ``create_app``: ``bootstrap.build_container`` wraps each port with
``audited()``, which binds ``getattr(adapter, method)`` once at build time. A patch installed after
the app is built never reaches the wrapped port.

This is a double at an outbound port, which ``docs/impl2-rules.md`` allows. The unit under test
(pipeline, handlers, service, routes, audit wrappers) stays real. The clock has its own switch,
``SimClock.fail()`` / ``recover()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import pytest

from src.domain.result import Failure

Mode = Literal["failure", "raises"]


class SimulatedOutage(RuntimeError):
    """What a port raises in ``raises`` mode: an unexpected error, not a typed ``Failure``."""


@dataclass
class PortFault:
    mode: Mode = "failure"
    active: bool = False

    def down(self) -> None:
        self.active = True

    def recover(self) -> None:
        self.active = False


def install(monkeypatch: pytest.MonkeyPatch, cls: type, method: str, fault: PortFault) -> None:
    """Route ``cls.method`` through ``fault``; the patch is undone at test teardown."""
    original = getattr(cls, method)

    def faulty(self: Any, *args: Any, **kwargs: Any) -> Any:
        if fault.active:
            if fault.mode == "raises":
                raise SimulatedOutage(f"{cls.__name__}.{method} is down")
            return Failure("PROVIDER_UNAVAILABLE", observed=("simulated outage",))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(cls, method, faulty)
