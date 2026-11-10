"""The composition root survives a broken database and reports it through readiness."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

from src import bootstrap
from src.adapters.outbound.db.sqlite_writer import SqliteWriter
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
        "audit": None,
    }
    container.close()


def test_an_unopenable_database_is_reported_not_raised(tmp_path: Path) -> None:
    container = build_container(_settings(db_path=str(tmp_path / "missing" / "dir" / "m12.db")))
    assert container.writer is None
    problem = container.readiness["migrations"]()
    assert problem is not None and "OperationalError" in problem
    container.close()  # closing a container without a writer must be safe


def test_bad_migration_sql_is_reported_not_raised(tmp_path: Path) -> None:
    (tmp_path / "001_bad.sql").write_text("create table (;", encoding="utf-8")
    container = build_container(_settings(migrations_dir=str(tmp_path)))
    problem = container.readiness["migrations"]()
    assert problem is not None and "001_bad.sql" in problem
    container.close()


def test_readiness_checks_the_live_connection_not_a_boot_time_snapshot() -> None:
    container = build_container(_settings())
    assert container.readiness["migrations"]() is None
    with container.writer.transaction() as db:
        db.execute("drop table schema_migrations")
    problem = container.readiness["migrations"]()
    assert problem is not None and "schema_migrations" in problem
    container.close()


def test_a_failure_while_wiring_closes_the_writer(monkeypatch) -> None:
    closed: list[bool] = []

    class SpyWriter(SqliteWriter):
        def close(self) -> None:
            closed.append(True)
            super().close()

    monkeypatch.setattr(bootstrap, "SqliteWriter", SpyWriter)

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


def test_tool_call_and_audit_ids_continue_above_a_file_database_after_restart(tmp_path) -> None:
    from src.ports.inbound import SessionUseCases
    from src.ports.outbound import AuditStorePort, IdGenPort

    database = str(tmp_path / "m12.db")
    first = build_container(_settings(db_path=database))
    use_cases = first.port(SessionUseCases)
    sid = use_cases.create_session("role-operations").value.session_id
    use_cases.submit_query(sid, "why was alex denied deepseek-coder")  # 5 audited tool calls
    use_cases.reset_session(sid)  # 1 more
    first.close()

    second = build_container(_settings(db_path=database))
    entries, total = second.port(AuditStorePort).page(sid, 0, 100).value
    assert total == 6 and entries[-1].audit_id == "aud-0000000000000006"
    idgen = second.port(IdGenPort)
    assert idgen.new_id("tool_call").value == "tc-0000000000000007"
    assert idgen.new_id("audit").value == "aud-0000000000000007"
    second.close()


def test_the_container_never_binds_the_deterministic_token_source() -> None:
    from src.adapters.outbound.token_idgen import SecureTokenIdGen
    from src.ports.outbound import IdGenPort

    first, second = build_container(_settings()), build_container(_settings())
    ids = first.port(IdGenPort)
    assert isinstance(ids, SecureTokenIdGen)  # IR-06: a deterministic token could be predicted
    assert ids.new_id("gate_token").value != second.port(IdGenPort).new_id("gate_token").value
    assert ids.new_id("session").value == "sess-0000000000000001"  # the rest stays reproducible
    first.close()
    second.close()


def test_proposal_ids_are_unguessable_and_never_collide_after_a_restart(tmp_path) -> None:
    from src.adapters.outbound.db.proposal_store import SqliteProposalStore
    from src.dto import AffectedItemDTO, DryRunSnapshotDTO, ProposalDTO, SelectorDTO
    from src.ports.inbound import SessionUseCases
    from src.ports.outbound import IdGenPort, ProposalStorePort

    database = str(tmp_path / "m12.db")
    first = build_container(_settings(db_path=database))
    sid = first.port(SessionUseCases).create_session("role-operations").value.session_id
    item = AffectedItemDTO(
        key="job#j", actionable=True, actionable_field="status", actionable_value="running"
    )
    snapshot = DryRunSnapshotDTO(
        selector=SelectorDTO(method="jobs_port.select", params={}),
        affected_items=[item],
        snapshot_timestamp="2026-10-16T15:00:00.000Z",
    )
    stored = ProposalDTO(
        proposal_id="prop-0000000000000009",
        session_id=sid,
        state="dry_run",
        action="cancel_jobs",
        dry_run_snapshot=snapshot,
        gate_token="gt-" + "0" * 32,
    )
    assert isinstance(first.port(ProposalStorePort), SqliteProposalStore)
    assert first.port(ProposalStorePort).add(stored, "2026-10-16T15:00:00.000Z").value is None
    first.close()

    second = build_container(_settings(db_path=database))
    fresh = second.port(IdGenPort).new_id("proposal").value
    assert fresh != "prop-0000000000000009" and fresh != "prop-000000000000000a"
    assert re.fullmatch(r"prop-[0-9a-f]{16}", fresh)  # random: no sequence to seed above
    second.close()


def test_the_registered_provider_ports_are_the_audited_wrappers() -> None:
    from src.application.tool_audit import TOOL_PORT_NAMES, ToolCallRecorder
    from src.ports.outbound import AuditStorePort, ClockPort, UnitOfWorkPort, UsersPort

    container = build_container(_settings())
    for port_type in TOOL_PORT_NAMES:
        assert type(container.port(port_type)).__name__ == f"Audited{port_type.__name__}"
    assert not type(container.port(ClockPort)).__name__.startswith("Audited")
    assert container.port(UnitOfWorkPort) is container.writer
    assert container.port(AuditStorePort) is not None
    recorder = container.port(ToolCallRecorder)
    with recorder.turn() as calls:
        container.port(UsersPort).get("user#alex")
    assert [c.tool_name for c in calls] == ["toolcall.users_port.get"]
    container.close()


def test_without_a_database_the_audit_readiness_check_fails(tmp_path) -> None:
    container = build_container(_settings(db_path=str(tmp_path / "missing" / "m12.db")))
    assert container.readiness["audit"]() is not None
    container.close()


def test_a_broken_audit_table_is_reported_by_readiness() -> None:
    container = build_container(_settings())
    assert container.readiness["audit"]() is None
    with container.writer.transaction() as db:
        db.execute("ALTER TABLE audit_records RENAME TO audit_records_gone")
    assert container.readiness["audit"]() == "PROVIDER_UNAVAILABLE"
    container.close()
