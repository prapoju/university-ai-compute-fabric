"""SQLite implementation of ``ProposalStorePort`` over the migrated ``proposals`` table.

The insert goes through the one ``SqliteWriter`` (review D-6), so a dry-run's proposal and its audit
rows commit together or not at all. The table's own CHECKs are the last guard: the selector method
is allowlisted to the two vetted provider queries (E39), the gate token is unique (E22) and the
state is one of the lifecycle values (AD-4).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from typing import TypeVar

from src.adapters.outbound.db.sqlite_writer import SqliteWriter
from src.domain.canonical_strings import S_CAP
from src.domain.result import Failure, Ok, Result
from src.dto import (
    AffectedItemDTO,
    ConfirmationDTO,
    DryRunSnapshotDTO,
    ExecutorResultDTO,
    ProposalDTO,
    SelectorDTO,
)
from src.ports.outbound import ProposalStorePort

T = TypeVar("T")

_INSERT = (
    "INSERT INTO proposals (proposal_id, session_id, state, action, supersedes_proposal_id,"
    " selector, affected_items, snapshot_timestamp, gate_token, created_at, updated_at)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


_COLUMNS = (
    "proposal_id", "session_id", "state", "action", "supersedes_proposal_id", "selector",
    "affected_items", "snapshot_timestamp", "gate_token", "confirmed_at", "executor_status",
    "applied_records", "applied_count", "executor_timestamp",
)  # fmt: skip
_SELECT = f"SELECT {', '.join(_COLUMNS)} FROM proposals WHERE proposal_id = ?"
# the one statement that decides a race: only a dry_run proposal with this token changes (AD-4)
_CLAIM = (
    "UPDATE proposals SET state = 'confirmed', confirmed_at = ?, updated_at = ?"
    " WHERE proposal_id = ? AND state = 'dry_run' AND gate_token = ?"
)


def _proposal(row: dict) -> ProposalDTO:
    """Rebuild the contract ``Proposal`` from a stored row (with its confirmation and result)."""
    selector = json.loads(row["selector"])
    snapshot = DryRunSnapshotDTO(
        selector=SelectorDTO(method=selector["method"], params=selector["params"]),
        affected_items=[AffectedItemDTO(**item) for item in json.loads(row["affected_items"])],
        snapshot_timestamp=row["snapshot_timestamp"],
    )
    confirmation = None
    if row["confirmed_at"] is not None:
        confirmation = ConfirmationDTO(confirmed_at=row["confirmed_at"], caption=S_CAP)
    result = None
    if row["executor_status"] is not None:
        result = ExecutorResultDTO(
            status=row["executor_status"],
            applied_records=json.loads(row["applied_records"]),
            applied_count=row["applied_count"],
            timestamp=row["executor_timestamp"],
            source="executor",
        )
    return ProposalDTO(
        proposal_id=row["proposal_id"],
        session_id=row["session_id"],
        state=row["state"],
        action=row["action"],
        supersedes_proposal_id=row["supersedes_proposal_id"],
        dry_run_snapshot=snapshot,
        gate_token=row["gate_token"],
        confirmation=confirmation,
        executor_result=result,
    )


class SqliteProposalStore(ProposalStorePort):
    def __init__(self, writer: SqliteWriter) -> None:
        self._writer = writer

    def _run(self, work: Callable[[sqlite3.Connection], T], *, write: bool = False) -> Result[T]:
        scope = self._writer.transaction if write else self._writer.read
        try:
            with scope() as connection:
                return Ok(work(connection))
        except (sqlite3.Error, ValueError) as exc:
            return Failure("PROVIDER_UNAVAILABLE", observed=(f"{type(exc).__name__}: {exc}",))

    def add(self, proposal: ProposalDTO, created_at: str) -> Result[None]:
        snapshot = proposal.dry_run_snapshot
        selector = json.dumps(snapshot.selector.model_dump(), sort_keys=True)
        items = json.dumps([i.model_dump() for i in snapshot.affected_items])

        def work(db: sqlite3.Connection) -> None:
            db.execute(
                _INSERT,
                (
                    proposal.proposal_id,
                    proposal.session_id,
                    proposal.state,
                    proposal.action,
                    proposal.supersedes_proposal_id,
                    selector,
                    items,
                    snapshot.snapshot_timestamp,
                    proposal.gate_token,
                    created_at,
                    created_at,
                ),
            )

        return self._run(work, write=True)

    def get(self, proposal_id: str) -> Result[ProposalDTO | None]:
        def work(db: sqlite3.Connection) -> ProposalDTO | None:
            cursor = db.execute(_SELECT, (proposal_id,))
            found = cursor.fetchone()
            return None if found is None else _proposal(dict(zip(_COLUMNS, found, strict=True)))

        return self._run(work)

    def claim(self, proposal_id: str, gate_token: str, confirmed_at: str) -> Result[bool]:
        def work(db: sqlite3.Connection) -> bool:
            changed = db.execute(_CLAIM, (confirmed_at, confirmed_at, proposal_id, gate_token))
            return changed.rowcount == 1

        return self._run(work, write=True)

    def highest_counters(self) -> Result[dict[str, int]]:
        def work(db: sqlite3.Connection) -> dict[str, int]:
            rows = db.execute("SELECT proposal_id FROM proposals").fetchall()
            return {"proposal": max((int(v[len("prop-") :], 16) for (v,) in rows), default=0)}

        return self._run(work)
