"""Composition root: the only place that wires adapters to the application (R3).

Everything the service needs is built here from :class:`~src.config.Settings`, so the
FastAPI app and the tests construct the system the same way. Ports are registered by their
interface type, which is the extension seam for new entity types (NFR-10): a new fixture set,
one query-only port and one adapter are added with :meth:`Container.register_port` - nothing
that already exists changes. Readiness checks are registered by name.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

from src import dependency_check
from src.adapters.outbound.db.connection import open_database
from src.adapters.outbound.db.migrate import MigrationError, apply_migrations
from src.adapters.outbound.sim.fixtures_adapter import SimProviders
from src.config import Settings
from src.domain.result import is_failure

# A readiness check returns None when healthy, otherwise a human-readable problem.
ReadinessCheck = Callable[[], str | None]

P = TypeVar("P")


@dataclass
class Container:
    settings: Settings
    connection: sqlite3.Connection
    ports: dict[type, object] = field(default_factory=dict)
    readiness: dict[str, ReadinessCheck] = field(default_factory=dict)

    def register_port(
        self, port_type: type[P], adapter: P, check: ReadinessCheck | None = None
    ) -> None:
        """Register ``adapter`` as the implementation of ``port_type``."""
        if not isinstance(adapter, port_type):
            raise TypeError(f"{type(adapter).__name__} does not implement {port_type.__name__}")
        self.ports[port_type] = adapter
        if check is not None:
            self.readiness[port_type.__name__] = check

    def port(self, port_type: type[P]) -> P:
        try:
            return self.ports[port_type]  # type: ignore[return-value]
        except KeyError:
            raise KeyError(f"no adapter registered for {port_type.__name__}") from None

    def close(self) -> None:
        self.connection.close()


def build_container(settings: Settings) -> Container:
    connection = open_database(settings.db_path)

    migration_problem: str | None = None
    try:
        apply_migrations(connection, settings.migrations_dir)
    except MigrationError as exc:
        migration_problem = str(exc)

    providers = SimProviders.from_fixtures(settings.fixtures_dir, settings.clock_start)

    def dependencies() -> str | None:
        problems = dependency_check.check(settings)
        return "; ".join(problems) if problems else None

    def migrations() -> str | None:
        return migration_problem

    def estate() -> str | None:
        if is_failure(providers.estate):
            return "; ".join(providers.estate.observed) or providers.estate.code
        return None

    def clock() -> str | None:
        # Probing must not consume a read id: that would change the deterministic sequence.
        return None if providers.clock.available else "CLOCK_UNAVAILABLE"

    container = Container(
        settings=settings,
        connection=connection,
        ports=providers.as_ports(),
        readiness={
            "dependencies": dependencies,
            "migrations": migrations,
            "estate": estate,
            "clock": clock,
        },
    )
    return container
