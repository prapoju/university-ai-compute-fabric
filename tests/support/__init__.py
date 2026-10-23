"""Shared test doubles and helpers for the Module 12 harness.

Import from submodules directly (``from support.clock import FakeClock``) or use the
fixtures declared in ``tests/conftest.py``.
"""

from support.builders import SampleData
from support.clock import ClockRead, FakeClock, format_instant, parse_instant
from support.db import TestDatabase, connect_ephemeral
from support.explain import Explanation, coerce_explanation, explain_assert
from support.fleet import Fleet, NodeRecord, NodeSpec, build_fleet
from support.ids import IdFactory, ID_KINDS, is_valid_id
from support.telemetry import Sample, SimTelemetry

__all__ = [
    "ClockRead",
    "Explanation",
    "FakeClock",
    "Fleet",
    "IdFactory",
    "ID_KINDS",
    "NodeRecord",
    "NodeSpec",
    "Sample",
    "SampleData",
    "SimTelemetry",
    "TestDatabase",
    "build_fleet",
    "coerce_explanation",
    "connect_ephemeral",
    "explain_assert",
    "format_instant",
    "is_valid_id",
    "parse_instant",
]
