"""Composition root: the only place that wires adapters to the application (R3).

Everything the service needs is built here from :class:`~src.config.Settings`, so the
FastAPI app and the tests construct the system the same way. Readiness checks are
registered by name; later tasks add the estate and clock checks without touching callers.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field

from src import dependency_check
from src.adapters.outbound.db.connection import open_database
from src.adapters.outbound.db.migrate import MigrationError, apply_migrations
from src.config import Settings

# A readiness check returns None when healthy, otherwise a human-readable problem.
ReadinessCheck = Callable[[], str | None]


@dataclass
class Container:
    settings: Settings
    connection: sqlite3.Connection
    readiness: dict[str, ReadinessCheck] = field(default_factory=dict)

    def close(self) -> None:
        self.connection.close()


def build_container(settings: Settings) -> Container:
    connection = open_database(settings.db_path)

    migration_problem: str | None = None
    try:
        apply_migrations(connection, settings.migrations_dir)
    except MigrationError as exc:
        migration_problem = str(exc)

    def dependencies() -> str | None:
        problems = dependency_check.check(settings)
        return "; ".join(problems) if problems else None

    def migrations() -> str | None:
        return migration_problem

    return Container(
        settings=settings,
        connection=connection,
        readiness={"dependencies": dependencies, "migrations": migrations},
    )
