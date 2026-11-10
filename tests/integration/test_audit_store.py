"""SqliteAuditStore on the real migrated schema (AD-10, FR-11, I14, I20, D42, D50).

The append-only guarantee is the schema's, not the code's: ``UPDATE`` and gate-closed ``DELETE``
on ``audit_records`` are rejected by the triggers of ``migrations/001_*.sql`` whatever path issues
them. Rotation is the only delete, and the gate is closed after every commit and every rollback.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

import pytest

from src.adapters.outbound.db.audit_store import SqliteAuditStore
from src.adapters.outbound.db.migrate import apply_migrations
from src.adapters.outbound.db.session_store import SqliteSessionStore
from src.adapters.outbound.db.sqlite_writer import SqliteWriter
from src.config import PROJECT_ROOT
from src.domain.result import Failure, Ok, is_ok
from src.dto import AuditRecordDTO, SessionContextDTO, SessionDTO, ToolCallDTO
from src.ports.outbound import AuditEntry

pytestmark = pytest.mark.integration

SID = "sess-0000000000000001"
OTHER = "sess-0000000000000002"
T0 = "2026-10-16T15:00:00.000Z"
UPDATE_DENIED = re.escape("audit_records is append-only (AD-10): UPDATE denied")
DELETE_DENIED = re.escape(
    "audit_records is append-only (AD-10): DELETE denied; D42 rotation gate closed"
)


def at(minute: int) -> str:
    return f"2026-10-16T15:{minute:02d}:00.000Z"


def entry(
    n: int, *, sid: str = SID, timestamp: str = T0, tool: str = "toolcall.answer_query"
) -> AuditEntry:
    tool_call_id = f"tc-{n:016x}"
    return AuditEntry(
        tool_call=ToolCallDTO(
            tool_call_id=tool_call_id,
            session_id=sid,
            tool_name=tool,
            params_summary={"key": "user#alex", "n": n},
            timestamp=timestamp,
            status="ok",
        ),
        record=AuditRecordDTO(
            audit_id=f"aud-{n:016x}",
            tool_call_id=tool_call_id,
            session_id=sid,
            operator_role="role-operations",
            timestamp=timestamp,
            result_summary={"tool_name": tool, "status": "ok", "result_count": 1},
            actor="copilot",
        ),
    )


def ok(result):
    assert is_ok(result), result
    return result.value


@pytest.fixture(params=["memory", "file"])
def writer(request, tmp_path: Path) -> SqliteWriter:
    path = ":memory:" if request.param == "memory" else str(tmp_path / "m12.db")
    box = SqliteWriter.open(path)
    apply_migrations(box, PROJECT_ROOT / "migrations")
    sessions = SqliteSessionStore(box)
    for sid in (SID, OTHER):
        context = SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[])
        session = SessionDTO(
            session_id=sid, created_at=T0, operator_role="role-operations", context=context,
            status="active",
        )  # fmt: skip
        ok(sessions.create(session, T0))
    yield box
    box.close()


def store_on(writer: SqliteWriter, cap: int = 10_000) -> SqliteAuditStore:
    return SqliteAuditStore(writer, cap)


def scalar(writer: SqliteWriter, sql: str, params: tuple = ()) -> object:
    with writer.read() as db:
        return db.execute(sql, params).fetchone()[0]


def audit_ids(writer: SqliteWriter) -> list[str]:
    with writer.read() as db:
        return [a for (a,) in db.execute("SELECT audit_id FROM audit_records ORDER BY audit_id")]


def tool_call_ids(writer: SqliteWriter) -> list[str]:
    with writer.read() as db:
        return [t for (t,) in db.execute("SELECT tool_call_id FROM tool_calls ORDER BY 1")]


def gate(writer: SqliteWriter) -> int:
    return scalar(writer, "SELECT gate_open FROM audit_rotation_gate WHERE gate_id = 1")


# -- round trip --------------------------------------------------------------------------------
def test_an_append_round_trips_both_tables(writer: SqliteWriter) -> None:
    store = store_on(writer)
    assert store.append([entry(1), entry(2, timestamp=at(1))]) == Ok(None)
    entries, total = ok(store.page(SID, 0, 20))
    assert total == 2
    assert entries == [entry(1).record, entry(2, timestamp=at(1)).record]
    with writer.read() as db:
        row = db.execute(
            "SELECT session_id, tool_name, params_summary, timestamp, status, created_at"
            " FROM tool_calls WHERE tool_call_id = 'tc-0000000000000001'"
        ).fetchone()
    # stored JSON is sorted, so the bytes are deterministic
    assert row == (SID, "toolcall.answer_query", '{"key": "user#alex", "n": 1}', T0, "ok", T0)


def test_an_executor_row_without_a_tool_call_is_stored(writer: SqliteWriter) -> None:
    store = store_on(writer)
    ok(store.append([entry(1)]))
    with writer.transaction() as db:  # a proposal row for the executor record to reference
        db.execute(
            "INSERT INTO proposals (proposal_id, session_id, state, action, selector,"
            " snapshot_timestamp, gate_token, created_at, updated_at) VALUES"
            " ('prop-0000000000000001', ?, 'dry_run', 'cancel_jobs',"
            " '{\"method\": \"jobs_port.select\"}', ?, ?, ?, ?)",
            (SID, T0, "gt-" + "0" * 32, T0, T0),
        )
    executor = AuditEntry(
        tool_call=None,
        record=AuditRecordDTO(
            audit_id="aud-0000000000000002", session_id=SID, timestamp=at(1),
            result_summary={"applied": 0}, actor="executor", proposal_id="prop-0000000000000001",
        ),
    )  # fmt: skip
    assert store.append([executor]) == Ok(None)
    assert [e.actor for e in ok(store.page(SID, 0, 20))[0]] == ["copilot", "executor"]


# -- AD-10: append-only, enforced by the real schema ---------------------------------------------
def test_update_on_an_audit_row_fails_through_the_trigger(writer: SqliteWriter) -> None:
    ok(store_on(writer).append([entry(1)]))
    with pytest.raises(sqlite3.IntegrityError, match=UPDATE_DENIED), writer.transaction() as db:
        db.execute("UPDATE audit_records SET result_summary = '{}' WHERE audit_id = ?",
                   ("aud-0000000000000001",))  # fmt: skip
    with pytest.raises(sqlite3.IntegrityError, match=UPDATE_DENIED), writer.transaction() as db:
        db.execute("UPDATE audit_records SET operator_role = NULL")  # even a bulk update
    assert ok(store_on(writer).page(SID, 0, 20))[0] == [entry(1).record]  # row unchanged


def test_delete_on_an_audit_row_fails_while_the_gate_is_closed(writer: SqliteWriter) -> None:
    ok(store_on(writer).append([entry(1), entry(2)]))
    assert gate(writer) == 0
    with pytest.raises(sqlite3.IntegrityError, match=DELETE_DENIED), writer.transaction() as db:
        db.execute("DELETE FROM audit_records WHERE audit_id = 'aud-0000000000000001'")
    with pytest.raises(sqlite3.IntegrityError, match=DELETE_DENIED), writer.transaction() as db:
        db.execute("DELETE FROM audit_records")
    assert audit_ids(writer) == ["aud-0000000000000001", "aud-0000000000000002"]


def test_the_triggers_hold_outside_the_writer_too(tmp_path: Path) -> None:
    """A second raw connection (no writer, no app code) is refused by the same schema."""
    path = str(tmp_path / "m12.db")
    writer = SqliteWriter.open(path)
    apply_migrations(writer, PROJECT_ROOT / "migrations")
    context = SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[])
    session = SessionDTO(
        session_id=SID, created_at=T0, operator_role="role-operations", context=context,
        status="active",
    )  # fmt: skip
    ok(SqliteSessionStore(writer).create(session, T0))
    ok(store_on(writer).append([entry(1)]))
    writer.close()
    raw = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError, match=UPDATE_DENIED):
        raw.execute("UPDATE audit_records SET actor = 'executor'")
    with pytest.raises(sqlite3.IntegrityError, match=DELETE_DENIED):
        raw.execute("DELETE FROM audit_records")
    raw.rollback()
    assert raw.execute("SELECT count(*) FROM audit_records").fetchone() == (1,)
    raw.close()


def test_the_store_exposes_no_update_or_delete_operation() -> None:
    public = {name for name in dir(SqliteAuditStore) if not name.startswith("_")}
    assert public == {"append", "page", "highest_counters"}


# -- C8: one row per tool call -----------------------------------------------------------------
def test_a_duplicate_tool_call_fails_and_the_whole_batch_rolls_back(writer: SqliteWriter) -> None:
    store = store_on(writer)
    ok(store.append([entry(1)]))
    duplicate = AuditEntry(
        tool_call=None,
        record=entry(3).record.model_copy(update={"tool_call_id": "tc-0000000000000001"}),
    )
    result = store.append([entry(2), duplicate])
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert "ux_audit_tool_call" in result.observed[0] or "UNIQUE" in result.observed[0]
    assert audit_ids(writer) == ["aud-0000000000000001"]
    assert tool_call_ids(writer) == ["tc-0000000000000001"]  # entry 2's tool call is gone too


# -- I20 retention -----------------------------------------------------------------------------
def test_rotation_keeps_exactly_the_newest_rows_and_their_tool_calls(
    writer: SqliteWriter, caplog
) -> None:
    caplog.set_level(logging.INFO, logger="src")
    store = store_on(writer, cap=5)
    ok(store.append([entry(n, timestamp=at(n)) for n in range(1, 5)]))  # 4 rows: under the cap
    assert not [r for r in caplog.records if "rotated" in r.getMessage()]
    ok(store.append([entry(n, timestamp=at(n)) for n in range(5, 8)]))  # 7 rows: 2 over

    kept = [f"aud-{n:016x}" for n in range(3, 8)]
    assert audit_ids(writer) == kept
    assert tool_call_ids(writer) == [f"tc-{n:016x}" for n in range(3, 8)]
    assert gate(writer) == 0
    rotated = [r for r in caplog.records if "rotated" in r.getMessage()]
    assert len(rotated) == 1 and rotated[0].levelno == logging.INFO
    assert "2 row(s)" in rotated[0].getMessage()


def test_rotation_orders_by_timestamp_then_audit_id_across_sessions(writer: SqliteWriter) -> None:
    store = store_on(writer, cap=2)
    # insertion order differs from (timestamp, audit_id) order: the newest-by-time is written first
    ok(store.append([
        entry(9, timestamp=at(5)), entry(1, sid=OTHER, timestamp=at(1)),
        entry(4, timestamp=at(1)), entry(2, sid=OTHER, timestamp=at(3)),
    ]))  # fmt: skip
    assert audit_ids(writer) == ["aud-0000000000000002", "aud-0000000000000009"]


def test_a_failure_mid_rotation_rolls_back_and_leaves_the_gate_closed(
    writer: SqliteWriter,
) -> None:
    store = store_on(writer, cap=2)
    ok(store.append([entry(1, timestamp=at(1)), entry(2, timestamp=at(2))]))
    with writer.read() as db:  # fails after the gate opened and the audit rows were deleted
        db.execute(
            "CREATE TEMP TRIGGER boom BEFORE DELETE ON tool_calls"
            " BEGIN SELECT RAISE(ABORT, 'disk full mid-rotation'); END"
        )
    result = store.append([entry(3, timestamp=at(3))])
    assert isinstance(result, Failure) and "disk full mid-rotation" in result.observed[0]
    assert audit_ids(writer) == ["aud-0000000000000001", "aud-0000000000000002"]
    assert tool_call_ids(writer) == ["tc-0000000000000001", "tc-0000000000000002"]
    assert gate(writer) == 0
    # and with the gate closed again, a direct delete is still refused
    with pytest.raises(sqlite3.IntegrityError, match=DELETE_DENIED), writer.transaction() as db:
        db.execute("DELETE FROM audit_records")


def test_a_cap_below_one_is_rejected(writer: SqliteWriter) -> None:
    with pytest.raises(ValueError):
        SqliteAuditStore(writer, 0)


# -- page --------------------------------------------------------------------------------------
def test_page_orders_by_timestamp_with_ties_broken_by_audit_id(writer: SqliteWriter) -> None:
    store = store_on(writer)
    # written in an order that is neither id order nor time order
    ok(store.append([
        entry(7, timestamp=at(2)), entry(5, timestamp=at(1)), entry(3, timestamp=at(2)),
        entry(4, sid=OTHER, timestamp=at(0)),
    ]))  # fmt: skip
    entries, total = ok(store.page(SID, 0, 20))
    assert [e.audit_id for e in entries] == [
        "aud-0000000000000005", "aud-0000000000000003", "aud-0000000000000007",
    ]  # fmt: skip
    assert total == 3  # the other session's row is not counted
    second, total = ok(store.page(SID, 1, 1))
    assert [e.audit_id for e in second] == ["aud-0000000000000003"] and total == 3
    assert ok(store.page(SID, 3, 20)) == ([], 3)
    assert ok(store.page("sess-00000000000000ff", 0, 20)) == ([], 0)


def test_page_on_a_closed_writer_is_a_typed_failure(writer: SqliteWriter) -> None:
    store = store_on(writer)
    writer.close()
    for result in (store.page(SID, 0, 20), store.append([entry(1)]), store.highest_counters()):
        assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


# -- id seeding --------------------------------------------------------------------------------
def test_highest_counters_read_both_id_kinds(writer: SqliteWriter) -> None:
    store = store_on(writer)
    assert ok(store.highest_counters()) == {"tool_call": 0, "audit": 0}
    ok(store.append([entry(3), entry(0x1A)]))
    assert ok(store.highest_counters()) == {"tool_call": 0x1A, "audit": 0x1A}
