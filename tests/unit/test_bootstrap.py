"""The composition root survives a broken database and reports it through readiness."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from src import bootstrap
from src.bootstrap import build_container
from src.config import Settings

pytestmark = pytest.mark.unit


def _settings(**env: str) -> Settings:
    return Settings.from_env({f"M12_{k.upper()}": v for k, v in env.items()})


def test_a_healthy_container_reports_every_check_ok() -> None:
    container = build_container(_settings())
    assert {name: check() for name, check in container.readiness.items()} == {
        "dependencies": None,
        "migrations": None,
        "estate": None,
        "clock": None,
    }
    container.close()


def test_an_unopenable_database_is_reported_not_raised(tmp_path: Path) -> None:
    container = build_container(_settings(db_path=str(tmp_path / "missing" / "dir" / "m12.db")))
    assert container.connection is None
    problem = container.readiness["migrations"]()
    assert problem is not None and "OperationalError" in problem
    container.close()  # closing a container without a connection must be safe


def test_bad_migration_sql_is_reported_not_raised(tmp_path: Path) -> None:
    (tmp_path / "001_bad.sql").write_text("create table (;", encoding="utf-8")
    container = build_container(_settings(migrations_dir=str(tmp_path)))
    problem = container.readiness["migrations"]()
    assert problem is not None and "001_bad.sql" in problem
    container.close()


def test_readiness_checks_the_live_connection_not_a_boot_time_snapshot() -> None:
    container = build_container(_settings())
    assert container.readiness["migrations"]() is None
    container.connection.execute("drop table schema_migrations")
    problem = container.readiness["migrations"]()
    assert problem is not None and "schema_migrations" in problem
    container.close()


def test_a_failure_while_wiring_closes_the_connection(monkeypatch) -> None:
    closed: list[bool] = []

    class SpyConnection(sqlite3.Connection):
        def close(self) -> None:
            closed.append(True)
            super().close()

    monkeypatch.setattr(
        bootstrap,
        "open_database",
        lambda path: sqlite3.connect(path, factory=SpyConnection, check_same_thread=False),
    )

    def boom(*_args, **_kwargs):
        raise RuntimeError("wiring exploded")

    monkeypatch.setattr(bootstrap.SimProviders, "from_fixtures", boom)
    with pytest.raises(RuntimeError, match="wiring exploded"):
        build_container(_settings())
    assert closed == [True]


def test_log_level_setting_is_applied_to_the_src_logger() -> None:
    build_container(_settings(log_level="DEBUG")).close()
    assert logging.getLogger("src").level == logging.DEBUG
    build_container(_settings(log_level="WARNING")).close()
    assert logging.getLogger("src").level == logging.WARNING


def test_estate_and_database_failures_are_logged(tmp_path: Path, caplog) -> None:
    caplog.set_level(logging.INFO, logger="src")
    build_container(_settings(fixtures_dir=str(tmp_path))).close()
    messages = " ".join(r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR)
    assert "estate" in messages.lower()


def test_a_file_database_migrates_and_reports_ready(tmp_path: Path) -> None:
    container = build_container(_settings(db_path=str(tmp_path / "m12.db")))
    assert container.readiness["migrations"]() is None
    container.close()
