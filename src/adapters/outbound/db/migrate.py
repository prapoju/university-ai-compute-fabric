"""Tiny stdlib migration runner for the Module-12-owned SQLite stores.

No ORM and no Alembic (ARCHITECTURE "Stack Decisions"): numbered ``*.sql`` files are applied
in filename order and recorded in ``schema_migrations`` with a SHA-256 checksum, so a file
edited after it was applied is reported instead of silently re-run. The operational estate
is deliberately *not* migrated here - it lives behind read-only ports (AD-1, AD-13).

Each migration runs in ONE transaction together with its bookkeeping row: either the whole
file is applied and recorded, or nothing is, so a failed or interrupted run can simply be
retried after the file is fixed.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


class MigrationError(RuntimeError):
    """A migration could not be located or applied, or an applied one was altered."""


_BOOKKEEPING = (
    "create table if not exists schema_migrations ("
    " filename text primary key,"
    " sha256 text not null)"
)


def apply_migrations(connection: sqlite3.Connection, directory: Path) -> list[str]:
    """Apply pending migrations from ``directory``; return the filenames applied now."""
    if not directory.is_dir():
        raise MigrationError(f"Migrations directory not found: {directory}")

    try:
        connection.execute(_BOOKKEEPING)
        done = dict(connection.execute("select filename, sha256 from schema_migrations"))
    except sqlite3.Error as exc:
        raise MigrationError(f"cannot read schema_migrations: {exc}") from exc

    files = sorted(directory.glob("*.sql"))
    vanished = sorted(set(done) - {path.name for path in files})
    if vanished:
        raise MigrationError(f"applied migration file(s) missing from {directory}: {vanished}")

    applied: list[str] = []
    for path in files:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if path.name in done:
            if done[path.name] != digest:
                raise MigrationError(
                    f"{path.name} changed after it was applied; add a new migration."
                )
            continue
        _apply_one(connection, path.name, raw, digest)
        applied.append(path.name)
    return applied


def _apply_one(connection: sqlite3.Connection, name: str, raw: bytes, digest: str) -> None:
    try:
        script = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MigrationError(f"{name} is not valid UTF-8: {exc}") from exc

    quoted_name = name.replace("'", "''")
    bookkeeping = (
        f"INSERT INTO schema_migrations (filename, sha256) VALUES ('{quoted_name}', '{digest}');"
    )
    try:
        # executescript() commits any open transaction first, so BEGIN/COMMIT live in the script
        connection.executescript(f"BEGIN;\n{script}\n{bookkeeping}\nCOMMIT;")
    except sqlite3.Error as exc:
        if connection.in_transaction:
            connection.rollback()
        raise MigrationError(f"{name} failed and was rolled back: {exc}") from exc
