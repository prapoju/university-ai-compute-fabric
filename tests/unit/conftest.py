"""Fixtures for the story 1.1 unit tests: the simulated provider ring over the real estate."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from src.adapters.outbound.sim.fixtures_adapter import SimProviders
from src.config import PROJECT_ROOT

FROZEN_NOW = "2026-10-16T15:00:00.000Z"
REAL_FIXTURES = PROJECT_ROOT / "fixtures"


@pytest.fixture
def providers() -> SimProviders:
    """All twelve read-only ports, offline, with the clock frozen at the scenario 'now'."""
    return SimProviders.from_fixtures(REAL_FIXTURES, FROZEN_NOW)


@pytest.fixture
def fixtures_copy(tmp_path: Path) -> Path:
    """A throw-away copy of the fixtures that a test may corrupt."""
    target = tmp_path / "fixtures"
    shutil.copytree(REAL_FIXTURES, target)
    return target


@pytest.fixture
def providers_from() -> Callable[[Path], SimProviders]:
    return lambda directory: SimProviders.from_fixtures(directory, FROZEN_NOW)
