"""SqliteProposalStore on the real migrated schema (AD-3, AD-4, AD-6, E22, E39, E43)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.adapters.outbound.db.migrate import apply_migrations
from src.adapters.outbound.db.proposal_store import SqliteProposalStore
from src.adapters.outbound.db.session_store import SqliteSessionStore
from src.adapters.outbound.db.sqlite_writer import SqliteWriter
from src.config import PROJECT_ROOT
from src.domain.result import Failure, is_ok
from src.dto import (
    AffectedItemDTO,
    DryRunSnapshotDTO,
    ProposalDTO,
    SelectorDTO,
    SessionContextDTO,
    SessionDTO,
)

pytestmark = pytest.mark.integration

SID = "sess-0000000000000001"
T0 = "2026-10-16T15:00:00.000Z"
PARAMS = {"group_id": "group#CS-101", "status": "running"}


def proposal(n: int = 1, *, token: str | None = None, method: str = "jobs_port.select"):
    item = AffectedItemDTO(
        key="job#job-8901", actionable=True, actionable_field="status", actionable_value="running"
    )
    return ProposalDTO(
        proposal_id=f"prop-{n:016x}",
        session_id=SID,
        state="dry_run",
        action="cancel_jobs",
        dry_run_snapshot=DryRunSnapshotDTO(
            selector=SelectorDTO(method=method, params=PARAMS),
            affected_items=[item],
            snapshot_timestamp=T0,
        ),
        gate_token=token or f"gt-{n:032x}",
    )


@pytest.fixture(params=["memory", "file"])
def writer(request, tmp_path: Path) -> SqliteWriter:
    path = ":memory:" if request.param == "memory" else str(tmp_path / "m12.db")
    box = SqliteWriter.open(path)
    apply_migrations(box, PROJECT_ROOT / "migrations")
    context = SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[])
    session = SessionDTO(
        session_id=SID, created_at=T0, operator_role="role-operations", context=context,
        status="active",
    )  # fmt: skip
    assert is_ok(SqliteSessionStore(box).create(session, T0))
    yield box
    box.close()


def rows(writer: SqliteWriter) -> list[tuple]:
    with writer.read() as db:
        return db.execute(
            "SELECT proposal_id, session_id, state, action, selector, affected_items,"
            " snapshot_timestamp, gate_token, created_at, updated_at FROM proposals ORDER BY 1"
        ).fetchall()


def test_a_proposal_is_stored_whole_in_dry_run(writer: SqliteWriter) -> None:
    assert is_ok(SqliteProposalStore(writer).add(proposal(), T0))
    [row] = rows(writer)
    assert row[:4] == ("prop-0000000000000001", SID, "dry_run", "cancel_jobs")
    assert json.loads(row[4]) == {"method": "jobs_port.select", "params": PARAMS}
    assert json.loads(row[5]) == [
        {"key": "job#job-8901", "actionable": True, "actionable_field": "status",
         "actionable_value": "running"}
    ]  # fmt: skip
    assert row[6:] == (T0, f"gt-{1:032x}", T0, T0)


def test_an_empty_affected_set_is_still_a_row(writer: SqliteWriter) -> None:
    empty = proposal()
    empty.dry_run_snapshot.affected_items = []
    assert is_ok(SqliteProposalStore(writer).add(empty, T0))
    assert json.loads(rows(writer)[0][5]) == []


def test_a_token_confirms_at_most_one_proposal(writer: SqliteWriter) -> None:
    store = SqliteProposalStore(writer)
    assert is_ok(store.add(proposal(1, token=f"gt-{7:032x}"), T0))
    again = store.add(proposal(2, token=f"gt-{7:032x}"), T0)
    assert isinstance(again, Failure) and again.code == "PROVIDER_UNAVAILABLE"
    assert [r[0] for r in rows(writer)] == ["prop-0000000000000001"]  # the second left nothing


def test_a_selector_outside_the_two_vetted_queries_is_refused_by_the_schema(writer) -> None:
    result = SqliteProposalStore(writer).add(proposal(method="users_port.select"), T0)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert rows(writer) == []


def test_a_proposal_for_an_unknown_session_is_refused(writer: SqliteWriter) -> None:
    orphan = proposal()
    orphan.session_id = "sess-00000000000000ff"
    assert isinstance(SqliteProposalStore(writer).add(orphan, T0), Failure)
    assert rows(writer) == []


def test_highest_counters_read_the_proposal_kind(writer: SqliteWriter) -> None:
    store = SqliteProposalStore(writer)
    assert store.highest_counters().value == {"proposal": 0}
    for n in (3, 11):
        assert is_ok(store.add(proposal(n), T0))
    assert store.highest_counters().value == {"proposal": 11}


def test_a_closed_connection_is_a_typed_failure_never_an_exception(tmp_path: Path) -> None:
    box = SqliteWriter.open(str(tmp_path / "x.db"))
    apply_migrations(box, PROJECT_ROOT / "migrations")
    store = SqliteProposalStore(box)
    box.close()
    assert isinstance(store.add(proposal(), T0), Failure)
    assert isinstance(store.highest_counters(), Failure)
