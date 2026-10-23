"""Ephemeral SQLite, migrated from the real Module 12 schema ``001_*.sql``.

The project's store is SQLite (``ARCHITECTURE.md`` Stack Decisions: stdlib ``sqlite3``,
WAL, single writer). The harness therefore runs against **in-memory** SQLite migrated
from ``planning/detailed-design/schemas/001_module12_copilot_schema.sql`` — the exact
DDL, triggers and partial indexes the running prototype will use, with zero external
services. Set ``TEA_DB_PATH`` to a file path to opt into a temp-file database instead.

AD-10 requires SQLite >= 3.35 (RETURNING + upsert) and JSON1; this module asserts the
engine version so a wrong interpreter fails loudly here rather than mid-suite.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

MIN_SQLITE_VERSION = (3, 35, 0)

SCHEMA_RELATIVE = Path(
    "planning/detailed-design/schemas/001_module12_copilot_schema.sql"
)

# tables owned by Module 12 (§2.2), for existence assertions
OWNED_TABLES = (
    "sessions",
    "answers",
    "evidence",
    "claims",
    "claim_citations",
    "tool_calls",
    "proposals",
    "audit_records",
    "audit_rotation_gate",
    "audit_events",
)


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for parent in [here, *here.parents]:
        if (parent / "planning").is_dir():
            return parent
    raise RuntimeError("could not locate the repository root (no planning/ directory)")


def default_schema_path() -> Path:
    env = os.environ.get("TEA_SCHEMA_PATH")
    if env:
        return Path(env)
    path = repo_root() / SCHEMA_RELATIVE
    if not path.is_file():
        raise FileNotFoundError(f"schema not found: {path}")
    return path


def require_sqlite_version(connection: sqlite3.Connection | None = None) -> tuple[int, ...]:
    raw = (connection or sqlite3.connect(":memory:")).execute("select sqlite_version()").fetchone()[0]
    version = tuple(int(part) for part in raw.split(".")[:3])
    if version < MIN_SQLITE_VERSION:
        raise RuntimeError(
            f"SQLite {raw} < {'.'.join(map(str, MIN_SQLITE_VERSION))} (AD-10: RETURNING + JSON1)"
        )
    return version


def migrate(connection: sqlite3.Connection, schema_file: Path | None = None) -> sqlite3.Connection:
    """Apply the Module 12 DDL to ``connection`` (idempotent per fresh connection)."""
    schema_file = schema_file or default_schema_path()
    connection.executescript(schema_file.read_text(encoding="utf-8"))
    connection.execute("PRAGMA foreign_keys = ON")
    connection.commit()
    return connection


class TestDatabase:
    """Thin wrapper: schema-valid helpers over a raw ``sqlite3.Connection``."""

    def __init__(self, connection: sqlite3.Connection, schema_file: Path) -> None:
        self.connection = connection
        self.schema_file = schema_file
        self.connection.row_factory = sqlite3.Row

    # -- raw passthrough ---------------------------------------------------
    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        cur = self.connection.execute(sql, params)
        self.connection.commit()
        return cur

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> sqlite3.Cursor:
        cur = self.connection.executemany(sql, rows)
        self.connection.commit()
        return cur

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return list(self.connection.execute(sql, params).fetchall())

    def fetchone(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        return self.connection.execute(sql, params).fetchone()

    # -- convenience -------------------------------------------------------
    def insert(self, table: str, row: Mapping[str, Any]) -> None:
        columns = ", ".join(row)
        placeholders = ", ".join(["?"] * len(row))
        self.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(row.values()))

    def count(self, table: str) -> int:
        return int(self.fetchone(f"SELECT COUNT(*) AS n FROM {table}")["n"])

    def tables(self) -> list[str]:
        rows = self.query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [r["name"] for r in rows]

    def triggers(self) -> list[str]:
        rows = self.query("SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name")
        return [r["name"] for r in rows]

    def indexes(self) -> list[str]:
        rows = self.query("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
        return [r["name"] for r in rows]

    # -- D42 rotation gate (needed to exercise the audit delete trigger) ---
    def open_rotation_gate(self) -> None:
        self.execute("UPDATE audit_rotation_gate SET gate_open = 1 WHERE gate_id = 1")

    def close_rotation_gate(self) -> None:
        self.execute("UPDATE audit_rotation_gate SET gate_open = 0 WHERE gate_id = 1")

    def gate_open(self) -> bool:
        return bool(self.fetchone("SELECT gate_open FROM audit_rotation_gate WHERE gate_id = 1")["gate_open"])

    def close(self) -> None:
        self.connection.close()


def connect_ephemeral(
    *,
    schema_file: Path | None = None,
    path: str | None = None,
) -> TestDatabase:
    """Open a fresh, migrated database. Defaults to in-memory (function-scoped)."""
    schema_file = schema_file or default_schema_path()
    db_path = path or os.environ.get("TEA_DB_PATH", ":memory:")
    require_sqlite_version()
    connection = sqlite3.connect(db_path)
    migrate(connection, schema_file)
    return TestDatabase(connection, schema_file)
