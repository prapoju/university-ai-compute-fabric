"""Startup dependency validation fails fast with readable messages (Impl-1 §1)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src import dependency_check
from src.config import Settings

pytestmark = pytest.mark.unit


def _settings(tmp_path: Path) -> Settings:
    (tmp_path / "fixtures").mkdir()
    return Settings.from_env({"M12_FIXTURES_DIR": str(tmp_path / "fixtures")})


def test_healthy_environment_reports_no_problems(tmp_path: Path) -> None:
    assert dependency_check.check(_settings(tmp_path)) == []


def test_old_sqlite_is_reported_with_the_required_version(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(dependency_check.sqlite3, "sqlite_version", "3.34.1")
    problems = dependency_check.check(_settings(tmp_path))
    assert len(problems) == 1
    assert "3.35" in problems[0] and "3.34.1" in problems[0]


def test_old_python_is_reported(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(dependency_check, "_python_version", lambda: (3, 10, 4))
    problems = dependency_check.check(_settings(tmp_path))
    assert any("Python 3.11" in p and "3.10.4" in p for p in problems)


def test_missing_fixtures_directory_is_reported(tmp_path: Path) -> None:
    settings = Settings.from_env({"M12_FIXTURES_DIR": str(tmp_path / "nope")})
    problems = dependency_check.check(settings)
    assert any("fixtures" in p and "nope" in p for p in problems)


def test_missing_required_package_is_reported(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "fastapi", None)  # makes `import fastapi` raise ImportError
    problems = dependency_check.check(_settings(tmp_path))
    assert any("fastapi" in p for p in problems)


def test_require_raises_one_error_listing_every_fatal_problem(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(dependency_check.sqlite3, "sqlite_version", "3.1.0")
    monkeypatch.setattr(dependency_check, "_python_version", lambda: (3, 9, 1))
    with pytest.raises(dependency_check.DependencyError) as excinfo:
        dependency_check.require()
    message = str(excinfo.value)
    assert "3.1.0" in message and "3.9.1" in message


def test_missing_fixtures_alone_are_not_fatal_the_service_starts_and_reports_not_ready(
    tmp_path: Path,
) -> None:
    settings = Settings.from_env({"M12_FIXTURES_DIR": str(tmp_path / "nope")})
    assert dependency_check.fatal_problems() == []
    assert any("nope" in p for p in dependency_check.check(settings))
    dependency_check.require()  # must not raise
