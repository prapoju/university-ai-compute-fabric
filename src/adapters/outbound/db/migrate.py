"""Tiny stdlib migration runner for the Module-12-owned SQLite stores.

No ORM and no Alembic (ARCHITECTURE "Stack Decisions"): numbered ``*.sql`` files are applied
in filename order and recorded in ``schema_migrations`` with a SHA-256 checksum, so a file
edited after it was applied is reported instead of silently re-run. The operational estate
is deliberately *not* migrated here - it lives behind read-only ports (AD-1, AD-13).
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


class MigrationError(RuntimeError):
    """A migration could not be located, or an applied one was altered."""


_BOOKKEEPING = (
    "create table if not exists schema_migrations ("
    " filename text primary key,"
    " sha256 text not null)"
)


def apply_migrations(connection: sqlite3.Connection, directory: Path) -> list[str]:
    """Apply pending migrations from ``directory``; return the filenames applied now."""
    if not directory.is_dir():
        raise MigrationError(f"Migrations directory not found: {directory}")

    connection.execute(_BOOKKEEPING)
    done = dict(connection.execute("select filename, sha256 from schema_migrations"))

    applied: list[str] = []
    for path in sorted(directory.glob("*.sql")):
        script = path.read_bytes()
        digest = hashlib.sha256(script).hexdigest()
        if path.name in done:
            if done[path.name] != digest:
                raise MigrationError(
                    f"{path.name} changed after it was applied; add a new migration."
                )
            continue
        connection.executescript(script.decode("utf-8"))
        connection.execute(
            "insert into schema_migrations (filename, sha256) values (?, ?)", (path.name, digest)
        )
        connection.commit()
        applied.append(path.name)
    return applied
