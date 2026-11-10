"""API fixtures: the real FastAPI app with the session use cases wired over a real SQLite store."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.adapters.inbound.sessions import get_session_use_cases
from src.adapters.outbound.db.audit_store import SqliteAuditStore
from src.adapters.outbound.db.migrate import apply_migrations
from src.adapters.outbound.db.session_store import SqliteSessionStore
from src.adapters.outbound.db.sqlite_writer import SqliteWriter
from src.adapters.outbound.sim.clock_adapter import SimClock
from src.adapters.outbound.sim.idgen_adapter import SimIdGen
from src.application.audit_writer import AuditWriter
from src.application.pipeline import AnswerPipeline
from src.application.session_service import SessionService
from src.application.tool_audit import ToolCallRecorder
from src.config import PROJECT_ROOT, Settings

START = "2026-10-16T15:00:00.000Z"


@dataclass
class ApiRig:
    client: TestClient
    clock: SimClock
    store: SqliteSessionStore
    pipeline: AnswerPipeline


@pytest.fixture
def api() -> ApiRig:
    """The app + a TestClient whose session use cases run on an in-memory store and frozen clock.

    ``dependency_overrides`` isolates the REST adapter from the composition root; the real
    wiring is exercised separately in ``test_sessions_wiring.py``.
    """
    writer = SqliteWriter.open(":memory:")
    apply_migrations(writer, PROJECT_ROOT / "migrations")
    store = SqliteSessionStore(writer)
    clock = SimClock(START)
    pipeline = AnswerPipeline()
    idgen = SimIdGen()
    service = SessionService(
        store=store, clock=clock, idgen=idgen, pipeline=pipeline, uow=writer,
        audit=AuditWriter(SqliteAuditStore(writer, 10_000), idgen), recorder=ToolCallRecorder(),
    )  # fmt: skip

    app = create_app(Settings.from_env({}))
    app.dependency_overrides[get_session_use_cases] = lambda: service
    return ApiRig(TestClient(app, raise_server_exceptions=False), clock, store, pipeline)
