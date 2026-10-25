"""Composition root: the only place that wires adapters to the application (R3).

Everything the service needs is built here from :class:`~src.config.Settings`, so the
FastAPI app and the tests construct the system the same way. Ports are registered by their
interface type, which is the extension seam for new entity types (NFR-10): a new fixture set,
one query-only port and one adapter are added with :meth:`Container.register_port` - nothing
that already exists changes. Readiness checks are registered by name.

A broken database or estate never crashes the build: it is logged and surfaces as a failing
readiness check, so an operator can see what is wrong through ``/readyz``.
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

# A readiness check returns None when healthy, otherwise a human-readable problem.
ReadinessCheck = Callable[[], str | None]

P = TypeVar("P")


@dataclass
class Container:
    settings: Settings
    connection: sqlite3.Connection | None
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
        if self.connection is not None:
            self.connection.close()


def configure_logging(level: str) -> None:
    """Apply ``M12_LOG_LEVEL`` to the ``src`` logger tree (one console handler if none exists)."""
    root = logging.getLogger("src")
    root.setLevel(level)
    if not root.handlers and not logging.getLogger().handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)


def build_container(settings: Settings) -> Container:
    configure_logging(settings.log_level)

    connection: sqlite3.Connection | None = None
    database_problem: str | None = None
    try:
        connection = open_database(settings.db_path)
        apply_migrations(connection, settings.migrations_dir)
    except (MigrationError, sqlite3.Error, OSError) as exc:
        database_problem = f"{type(exc).__name__}: {exc}"
        logger.error("database/migrations unavailable: %s", database_problem)

    try:
        providers = SimProviders.from_fixtures(settings.fixtures_dir, settings.clock_start)
    except BaseException:
        if connection is not None:
            connection.close()
        raise

    if is_failure(providers.estate):
        logger.error("estate failed to load: %s", "; ".join(providers.estate.observed))

    def dependencies() -> str | None:
        problems = dependency_check.check(settings)
        return "; ".join(problems) if problems else None

    def migrations() -> str | None:
        """Live check: the connection answers and every migration file is recorded."""
        if database_problem or connection is None:
            return database_problem or "database connection unavailable"
        try:
            applied = {
                row[0] for row in connection.execute("select filename from schema_migrations")
            }
        except sqlite3.Error as exc:
            return f"schema_migrations unreadable: {exc}"
        expected = {path.name for path in settings.migrations_dir.glob("*.sql")}
        pending = sorted(expected - applied)
        return f"pending migrations: {pending}" if pending else None

    def estate() -> str | None:
        if is_failure(providers.estate):
            return "; ".join(providers.estate.observed) or providers.estate.code
        return None

    def clock() -> str | None:
        # Probing must not consume a read id: that would change the deterministic sequence.
        return None if providers.clock.available else "CLOCK_UNAVAILABLE"

    logger.info("container built (fixtures=%s)", settings.fixtures_dir)
    return Container(
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
