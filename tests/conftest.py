"""Module 12 test harness — fixture registry.

Mandatory fixtures (required by the harness contract):

  - ``fake_clock``     deterministic, advanceable clock (OP-10)
  - ``seed_fleet``     seeded GPU estate: many 1x24 GB + one 2x48 GB, all HEALTHY
  - ``sim_telemetry``  scripted GPU/heartbeat/metric injector with fault generation
  - ``db``             ephemeral SQLite migrated from ``001_module12_copilot_schema.sql``
  - ``explain_assert`` helper asserting a decision carries >= 1 rule id + observed values

Supporting fixtures: ``ids``, ``sample``, ``schema_path``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make ``support`` importable regardless of how pytest is invoked.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from support import explain as explain_module  # noqa: E402
from support.builders import SampleData  # noqa: E402
from support.clock import FakeClock  # noqa: E402
from support.db import TestDatabase, connect_ephemeral, default_schema_path  # noqa: E402
from support.fleet import Fleet, build_fleet  # noqa: E402
from support.ids import IdFactory  # noqa: E402
from support.telemetry import SimTelemetry  # noqa: E402


# -- time ---------------------------------------------------------------
@pytest.fixture
def fake_clock() -> FakeClock:
    """A fresh deterministic clock at the scenario 'now' (2026-10-16T15:00:00.000Z)."""
    return FakeClock()


# -- ids / sample data --------------------------------------------------
@pytest.fixture
def ids() -> IdFactory:
    return IdFactory()


@pytest.fixture
def sample(ids: IdFactory, fake_clock: FakeClock) -> SampleData:
    """Row/record factories bound to the test's id source and frozen 'now'."""
    return SampleData(ids=ids, now=fake_clock.current)


# -- estate -------------------------------------------------------------
@pytest.fixture
def seed_fleet() -> Fleet:
    """Seeded heterogeneous GPU estate: many 1x24 GB nodes + one 2x48 GB node, all healthy."""
    return build_fleet()


@pytest.fixture
def sim_telemetry(seed_fleet: Fleet, fake_clock: FakeClock) -> SimTelemetry:
    """Scripted telemetry injector wired to ``seed_fleet`` and ``fake_clock``."""
    return SimTelemetry(seed_fleet, fake_clock)


# -- database -----------------------------------------------------------
@pytest.fixture
def schema_path() -> Path:
    return default_schema_path()


@pytest.fixture
def db(schema_path: Path) -> TestDatabase:
    """Migrated, isolated database (in-memory by default; ``TEA_DB_PATH`` to override)."""
    database = connect_ephemeral(schema_file=schema_path)
    try:
        yield database
    finally:
        database.close()


# -- assertions ---------------------------------------------------------
@pytest.fixture
def explain_assert():
    """Helper asserting a decision carries >= 1 rule id + the observed values.

    Returns ``support.explain.explain_assert``; use it as
    ``explain_assert(decision, rule_id=..., values={...})``.
    """
    return explain_module.explain_assert
