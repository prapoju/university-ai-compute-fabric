"""SQLite implementation of ``AuditStorePort`` over the migrated ``tool_calls`` / ``audit_records``.

Writes go through the one ``SqliteWriter`` (review D-6), so an append made inside the turn's unit
of work commits with the ``Answer`` or not at all (story 1.5 D1). The schema's triggers keep
``audit_records`` append-only (AD-10); the only delete is the retention rotation (I20, D42, D50),
which opens the gate, removes the oldest excess rows and their ``tool_calls``, and closes the gate
inside the same transaction (C9), so a rollback also leaves the gate closed.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable, Sequence
from typing import TypeVar

from src.adapters.outbound.db.sqlite_writer import SqliteWriter
from src.domain.result import Failure, Ok, Result
from src.dto import AuditRecordDTO
from src.ports.outbound import AuditEntry, AuditStorePort

logger = logging.getLogger(__name__)

T = TypeVar("T")

_INSERT_TOOL_CALL = (
    "INSERT INTO tool_calls (tool_call_id, session_id, tool_name, params_summary, timestamp,"
    " status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
)
# C8: ux_audit_tool_call makes a second row for the same tool call a constraint failure
_INSERT_AUDIT = (
    "INSERT INTO audit_records (audit_id, tool_call_id, session_id, operator_role, timestamp,"
    " result_summary, actor, proposal_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)
_AUDIT_COLUMNS = (
    "audit_id, tool_call_id, session_id, operator_role, timestamp, result_summary, actor,"
    " proposal_id"
)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True)  # deterministic stored bytes


class SqliteAuditStore(AuditStorePort):
    def __init__(self, writer: SqliteWriter, retention_cap: int) -> None:
        if retention_cap < 1:
            raise ValueError("retention_cap must be at least 1")
        self._writer = writer
        self._cap = retention_cap

    def _run(self, work: Callable[[sqlite3.Connection], T], *, write: bool = False) -> Result[T]:
        scope = self._writer.transaction if write else self._writer.read
        try:
            with scope() as connection:
                return Ok(work(connection))
        except (sqlite3.Error, ValueError) as exc:  # ValueError: invalid stored JSON/DTO
            return Failure("PROVIDER_UNAVAILABLE", observed=(f"{type(exc).__name__}: {exc}",))

    # -- AuditStorePort ------------------------------------------------------------------------
    def append(self, entries: Sequence[AuditEntry]) -> Result[None]:
        removed: list[int] = []

        def work(db: sqlite3.Connection) -> None:
            for entry in entries:
                call, record = entry.tool_call, entry.record
                if call is not None:
                    db.execute(
                        _INSERT_TOOL_CALL,
                        (
                            call.tool_call_id,
                            call.session_id,
                            call.tool_name,
                            _json(call.params_summary),
                            call.timestamp,
                            call.status,
                            call.timestamp,
                        ),
                    )
                db.execute(
                    _INSERT_AUDIT,
                    (
                        record.audit_id,
                        record.tool_call_id,
                        record.session_id,
                        record.operator_role,
                        record.timestamp,
                        _json(record.result_summary),
                        record.actor,
                        record.proposal_id,
                    ),
                )
            removed.append(self._rotate(db))

        written = self._run(work, write=True)
        if isinstance(written, Ok) and removed[0]:
            logger.info("audit retention rotated %d row(s) (cap %d)", removed[0], self._cap)
        return written

    def _rotate(self, db: sqlite3.Connection) -> int:
        """C9: delete the oldest rows above the cap, with their tool calls. Returns the count."""
        (count,) = db.execute("SELECT count(*) FROM audit_records").fetchone()
        excess = count - self._cap
        if excess <= 0:
            return 0
        db.execute("UPDATE audit_rotation_gate SET gate_open = 1 WHERE gate_id = 1")
        gone = db.execute(
            "DELETE FROM audit_records WHERE audit_id IN (SELECT audit_id FROM audit_records"
            " ORDER BY timestamp ASC, audit_id ASC LIMIT ?) RETURNING tool_call_id",
            (excess,),
        ).fetchall()
        calls = [(tool_call_id,) for (tool_call_id,) in gone if tool_call_id is not None]
        db.executemany("DELETE FROM tool_calls WHERE tool_call_id = ?", calls)
        db.execute("UPDATE audit_rotation_gate SET gate_open = 0 WHERE gate_id = 1")
        return len(gone)

    def page(
        self, session_id: str, offset: int, limit: int
    ) -> Result[tuple[list[AuditRecordDTO], int]]:
        def work(db: sqlite3.Connection) -> tuple[list[AuditRecordDTO], int]:
            rows = db.execute(
                f"SELECT {_AUDIT_COLUMNS} FROM audit_records WHERE session_id = ?"
                " ORDER BY timestamp, audit_id LIMIT ? OFFSET ?",
                (session_id, limit, offset),
            ).fetchall()
            (total,) = db.execute(
                "SELECT count(*) FROM audit_records WHERE session_id = ?", (session_id,)
            ).fetchone()
            entries = [
                AuditRecordDTO(
                    audit_id=aid,
                    tool_call_id=tool_call_id,
                    session_id=sid,
                    operator_role=role,
                    timestamp=timestamp,
                    result_summary=json.loads(summary),
                    actor=actor,
                    proposal_id=proposal_id,
                )
                for aid, tool_call_id, sid, role, timestamp, summary, actor, proposal_id in rows
            ]
            return entries, total

        return self._run(work)

    def highest_counters(self) -> Result[dict[str, int]]:
        def highest(db: sqlite3.Connection, table: str, column: str, prefix: str) -> int:
            rows = db.execute(f"SELECT {column} FROM {table}").fetchall()
            return max((int(value[len(prefix) :], 16) for (value,) in rows), default=0)

        def work(db: sqlite3.Connection) -> dict[str, int]:
            return {
                "tool_call": highest(db, "tool_calls", "tool_call_id", "tc-"),
                "audit": highest(db, "audit_records", "audit_id", "aud-"),
            }

        return self._run(work)
