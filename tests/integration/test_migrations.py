"""The stdlib migration runner applies the contract schema idempotently (Impl-1 §1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.adapters.outbound.db.migrate import MigrationError, apply_migrations
from src.config import PROJECT_ROOT

pytestmark = pytest.mark.integration

MIGRATIONS = PROJECT_ROOT / "migrations"
OWNED_TABLES = {
    "sessions", "answers", "evidence", "claims", "claim_citations",
    "tool_calls", "proposals", "audit_records", "audit_rotation_gate", "audit_events",
}  # fmt: skip


def _tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("select name from sqlite_master where type = 'table'").fetchall()
    return {name for (name,) in rows}


def test_migration_matches_the_contract_schema_byte_for_byte() -> None:
    contract = PROJECT_ROOT / "planning/detailed-design/schemas/001_module12_copilot_schema.sql"
    assert (MIGRATIONS / contract.name).read_bytes() == contract.read_bytes()


def test_applies_every_module12_owned_table_and_nothing_about_the_estate() -> None:
    connection = sqlite3.connect(":memory:")
    applied = apply_migrations(connection, MIGRATIONS)
    tables = _tables(connection)
    assert applied == ["001_module12_copilot_schema.sql"]
    assert OWNED_TABLES <= tables
    # AD-1/AD-13: the operational estate never lives in this database
    assert not {"users", "nodes", "jobs", "catalog", "groups"} & tables


def test_is_idempotent_second_run_applies_nothing() -> None:
    connection = sqlite3.connect(":memory:")
    apply_migrations(connection, MIGRATIONS)
    assert apply_migrations(connection, MIGRATIONS) == []


def test_modified_migration_is_detected_not_silently_reapplied(tmp_path: Path) -> None:
    (tmp_path / "001_a.sql").write_text("create table a (x integer);", encoding="utf-8")
    connection = sqlite3.connect(":memory:")
    apply_migrations(connection, tmp_path)
    (tmp_path / "001_a.sql").write_text("create table a (x integer, y integer);", encoding="utf-8")
    with pytest.raises(MigrationError, match="001_a.sql"):
        apply_migrations(connection, tmp_path)


def test_append_only_audit_trigger_survives_migration() -> None:
    connection = sqlite3.connect(":memory:")
    apply_migrations(connection, MIGRATIONS)
    rows = connection.execute("select name from sqlite_master where type = 'trigger'")
    triggers = {name for (name,) in rows}
    assert {"trg_audit_records_no_update", "trg_audit_records_no_delete"} <= triggers


def test_missing_directory_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(MigrationError, match="not found"):
        apply_migrations(sqlite3.connect(":memory:"), tmp_path / "absent")
