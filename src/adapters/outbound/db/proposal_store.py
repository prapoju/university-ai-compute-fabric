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
from src.domain.result import Failure, Ok, Result
from src.dto import ProposalDTO
from src.ports.outbound import ProposalStorePort

T = TypeVar("T")

_INSERT = (
    "INSERT INTO proposals (proposal_id, session_id, state, action, supersedes_proposal_id,"
    " selector, affected_items, snapshot_timestamp, gate_token, created_at, updated_at)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
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

    def highest_counters(self) -> Result[dict[str, int]]:
        def work(db: sqlite3.Connection) -> dict[str, int]:
            rows = db.execute("SELECT proposal_id FROM proposals").fetchall()
            return {"proposal": max((int(v[len("prop-") :], 16) for (v,) in rows), default=0)}

        return self._run(work)
