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
        "sessions": None,
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


def test_the_container_wires_the_session_ring() -> None:
    from src.application.pipeline import AnswerPipeline
    from src.ports.inbound import SessionUseCases
    from src.ports.outbound import IdGenPort, SessionStorePort

    container = build_container(_settings())
    assert container.port(SessionStorePort) is not None
    assert container.port(IdGenPort).new_id("session").value == "sess-0000000000000001"
    assert isinstance(container.port(AnswerPipeline), AnswerPipeline)
    created = container.port(SessionUseCases).create_session("role-operations")
    assert created.value.session_id == "sess-0000000000000002"  # the id call above consumed #1
    container.close()


def test_the_id_generator_is_seeded_above_what_a_file_database_already_holds(tmp_path) -> None:
    from src.ports.inbound import SessionUseCases

    database = str(tmp_path / "m12.db")
    first = build_container(_settings(db_path=database))
    for _ in range(3):
        first.port(SessionUseCases).create_session("role-operations")
    first.close()
    second = build_container(_settings(db_path=database))
    created = second.port(SessionUseCases).create_session("role-operations")
    assert created.value.session_id == "sess-0000000000000004"
    second.close()


def test_without_a_database_sessions_fail_safely_and_readiness_says_so(tmp_path) -> None:
    from src.domain.result import Failure
    from src.ports.inbound import SessionUseCases

    container = build_container(_settings(db_path=str(tmp_path / "missing" / "m12.db")))
    results = container.port(SessionUseCases).create_session("role-operations")
    assert isinstance(results, Failure) and results.code == "PROVIDER_UNAVAILABLE"
    assert container.readiness["sessions"]() is not None
    container.close()
