"""SqliteProposalStore on the real migrated schema (AD-3, AD-4, AD-6, E22, E39, E43)."""

from __future__ import annotations

import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.adapters.outbound.db.migrate import apply_migrations
from src.adapters.outbound.db.proposal_store import SqliteProposalStore
from src.adapters.outbound.db.session_store import SqliteSessionStore
from src.adapters.outbound.db.sqlite_writer import SqliteWriter
from src.config import PROJECT_ROOT
from src.domain.canonical_strings import S_CAP
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


# -- story 2.3: reading a proposal back and the one conditional claim ------------------------------
T1 = "2026-10-16T15:00:42.000Z"


def test_a_miss_is_none_and_a_dry_run_row_round_trips_whole(writer: SqliteWriter) -> None:
    store = SqliteProposalStore(writer)
    assert store.get("prop-00000000000000ff").value is None
    stored = proposal(3)
    assert is_ok(store.add(stored, T0))
    assert store.get(stored.proposal_id).value == stored  # selector, items, token, no confirmation


def test_the_claim_changes_a_dry_run_proposal_once_and_the_read_shows_the_confirmation(
    writer: SqliteWriter,
) -> None:
    store = SqliteProposalStore(writer)
    stored = proposal()
    assert is_ok(store.add(stored, T0))
    assert store.claim(stored.proposal_id, stored.gate_token, T1).value is True
    assert store.claim(stored.proposal_id, stored.gate_token, T1).value is False  # already claimed
    confirmed = store.get(stored.proposal_id).value
    assert confirmed.state == "confirmed" and confirmed.executor_result is None
    assert confirmed.confirmation.confirmed_at == T1 and confirmed.confirmation.caption == S_CAP
    assert confirmed.dry_run_snapshot == stored.dry_run_snapshot  # the snapshot is not rewritten
    [row] = rows(writer)
    assert (row[2], row[8], row[9]) == ("confirmed", T0, T1)  # created_at kept, updated_at moved


def test_a_claim_with_another_token_or_for_another_proposal_changes_nothing(
    writer: SqliteWriter,
) -> None:
    store = SqliteProposalStore(writer)
    first, second = proposal(1), proposal(2)
    assert is_ok(store.add(first, T0)) and is_ok(store.add(second, T0))
    assert store.claim(first.proposal_id, second.gate_token, T1).value is False
    assert store.claim("prop-00000000000000ff", first.gate_token, T1).value is False
    assert [r[2] for r in rows(writer)] == ["dry_run", "dry_run"]


def test_the_claim_joins_the_callers_transaction(writer: SqliteWriter) -> None:
    store = SqliteProposalStore(writer)
    stored = proposal()
    assert is_ok(store.add(stored, T0))
    with pytest.raises(RuntimeError), writer.transaction():
        assert store.claim(stored.proposal_id, stored.gate_token, T1).value is True
        raise RuntimeError("the caller fails after the claim")
    assert store.get(stored.proposal_id).value.state == "dry_run"  # rolled back with the caller


def test_fifty_simultaneous_claims_have_one_winner(writer: SqliteWriter) -> None:
    store = SqliteProposalStore(writer)
    stored = proposal()
    assert is_ok(store.add(stored, T0))
    barrier = threading.Barrier(50)

    def run(_: int) -> bool:
        barrier.wait(timeout=60)
        return store.claim(stored.proposal_id, stored.gate_token, T1).value

    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(run, range(50)))
    assert results.count(True) == 1 and results.count(False) == 49


def test_a_row_with_an_executor_result_is_rebuilt_with_it(writer: SqliteWriter) -> None:
    store = SqliteProposalStore(writer)
    stored = proposal()
    assert is_ok(store.add(stored, T0))
    assert store.claim(stored.proposal_id, stored.gate_token, T1).value is True
    with writer.transaction() as db:  # what story 2.4 will write, in the order the trigger allows
        db.execute(
            "UPDATE proposals SET state = 'dispatched' WHERE proposal_id = ?", (stored.proposal_id,)
        )
        db.execute(
            "UPDATE proposals SET state = 'executed', executor_status = 'applied',"
            " applied_records = ?, applied_count = 1, executor_timestamp = ?,"
            " executor_source = 'executor'"
            " WHERE proposal_id = ?",
            (json.dumps(["job#job-8901"]), T1, stored.proposal_id),
        )
    done = store.get(stored.proposal_id).value
    assert done.state == "executed"
    assert done.executor_result.model_dump() == {
        "status": "applied", "applied_records": ["job#job-8901"], "applied_count": 1,
        "timestamp": T1, "source": "executor",
    }  # fmt: skip
    assert store.claim(stored.proposal_id, stored.gate_token, T1).value is False


def test_the_state_machine_trigger_still_blocks_a_jump_from_dry_run(writer: SqliteWriter) -> None:
    store = SqliteProposalStore(writer)
    stored = proposal()
    assert is_ok(store.add(stored, T0))
    with (
        pytest.raises(sqlite3.IntegrityError, match="illegal state transition"),
        writer.transaction() as db,
    ):
        db.execute(
            "UPDATE proposals SET state = 'dispatched' WHERE proposal_id = ?", (stored.proposal_id,)
        )
    assert store.get(stored.proposal_id).value.state == "dry_run"


def test_a_closed_connection_makes_get_and_claim_typed_failures(tmp_path: Path) -> None:
    box = SqliteWriter.open(str(tmp_path / "y.db"))
    apply_migrations(box, PROJECT_ROOT / "migrations")
    store = SqliteProposalStore(box)
    box.close()
    assert isinstance(store.get("prop-0000000000000001"), Failure)
    assert isinstance(store.claim("prop-0000000000000001", "gt-" + "0" * 32, T1), Failure)
