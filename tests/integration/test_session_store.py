"""SQLite session store over the migrated schema, on :memory: AND on a real file (AD-12).

The in-memory database hid a real bug in story 1.1 (WAL cannot be enabled inside a transaction
on a file database), so every behaviour here runs on both.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from src.adapters.outbound.db.migrate import apply_migrations
from src.adapters.outbound.db.session_store import SqliteSessionStore
from src.config import PROJECT_ROOT
from src.domain.result import Failure, Ok, is_ok
from src.dto import AnswerDTO, SessionContextDTO, SessionDTO

pytestmark = pytest.mark.integration

NOW = "2026-10-16T15:00:00.000Z"
LATER = "2026-10-16T15:05:00.000Z"


def _connect(path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(path, check_same_thread=False)
    apply_migrations(connection, PROJECT_ROOT / "migrations")
    return connection


@pytest.fixture(params=["memory", "file"])
def database(request, tmp_path: Path) -> str:
    return ":memory:" if request.param == "memory" else str(tmp_path / "m12.db")


@pytest.fixture
def store(database: str) -> SqliteSessionStore:
    return SqliteSessionStore(_connect(database))


def session(n: int = 1, *, role: str = "role-operations", created_at: str = NOW) -> SessionDTO:
    return SessionDTO(
        session_id=f"sess-{n:016x}",
        created_at=created_at,
        operator_role=role,
        context=SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[]),
        status="active",
    )


def answer(
    sid: str, n: int = 1, *, query: str = "why was alex denied deepseek-coder", **kw
) -> AnswerDTO:
    fields = {
        "answer_id": f"ans-{n:016x}",
        "session_id": sid,
        "query": query,
        "intent": "diagnose_access_denial",
        "answer_chain": ["observation"],
        "claims": [],
        "evidence": [],
        "prose": "routed",
    }
    return AnswerDTO(**{**fields, **kw})


def context(*, intents: list[str], answers: list[str]) -> SessionContextDTO:
    return SessionContextDTO(resolved_entities=[], prior_intents=intents, active_answer_ids=answers)


def _ok(result):
    assert is_ok(result), result
    return result.value


# -- create / get ------------------------------------------------------------------------------
def test_create_then_get_round_trips_the_session_exactly(store: SqliteSessionStore) -> None:
    created = session(1)
    assert _ok(store.create(created, NOW)) is None
    stored = _ok(store.get(created.session_id))
    assert stored.session == created
    assert stored.last_turn_at is None


def test_a_missing_session_is_ok_none(store: SqliteSessionStore) -> None:
    assert store.get("sess-00000000000000ff") == Ok(None)


def test_creating_the_same_session_twice_is_a_typed_failure_not_an_exception(
    store: SqliteSessionStore,
) -> None:
    _ok(store.create(session(1), NOW))
    duplicate = store.create(session(1), NOW)
    assert isinstance(duplicate, Failure) and duplicate.code == "PROVIDER_UNAVAILABLE"


def test_schema_check_constraints_surface_as_failures(store: SqliteSessionStore) -> None:
    bad = session(1).model_copy(update={"created_at": "not-an-instant"})
    result = store.create(bad, NOW)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert store.get("sess-0000000000000001") == Ok(None)  # nothing was written


# -- append_turn / list_turns ------------------------------------------------------------------
def test_append_turn_stores_the_answer_and_replaces_the_context(store: SqliteSessionStore) -> None:
    created = session(1)
    _ok(store.create(created, NOW))
    first = answer(created.session_id, 1)
    new_context = context(intents=["diagnose_access_denial"], answers=[first.answer_id])
    _ok(store.append_turn(created.session_id, first, new_context, LATER))
    stored = _ok(store.get(created.session_id))
    assert stored.session.context.prior_intents == ["diagnose_access_denial"]
    assert stored.session.context.active_answer_ids == [first.answer_id]
    assert stored.last_turn_at == LATER
    assert _ok(store.list_turns(created.session_id)) == [first]


def test_turns_come_back_in_creation_order_with_ties_broken_by_id(
    store: SqliteSessionStore,
) -> None:
    created = session(1)
    _ok(store.create(created, NOW))
    sid = created.session_id
    # the same instant for both (frozen clock) - the id decides the order
    _ok(store.append_turn(sid, answer(sid, 2), context(intents=["a"], answers=["x"]), LATER))
    _ok(
        store.append_turn(
            sid, answer(sid, 1), context(intents=["a", "b"], answers=["x", "y"]), LATER
        )
    )
    assert [a.answer_id for a in _ok(store.list_turns(sid))] == [
        "ans-0000000000000001",
        "ans-0000000000000002",
    ]


def test_a_failed_append_is_atomic_no_orphan_answer_and_context_unchanged(
    store: SqliteSessionStore,
) -> None:
    created = session(1)
    _ok(store.create(created, NOW))
    sid = created.session_id
    too_long = answer(sid, 1).model_copy(update={"query": "x" * 1001})  # violates the table CHECK
    result = store.append_turn(sid, too_long, context(intents=["i"], answers=["a"]), LATER)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert _ok(store.list_turns(sid)) == []
    stored = _ok(store.get(sid))
    assert stored.session.context.prior_intents == [] and stored.last_turn_at is None


def test_appending_to_an_unknown_session_fails_and_writes_nothing(
    store: SqliteSessionStore,
) -> None:
    ghost = "sess-00000000000000ff"
    result = store.append_turn(ghost, answer(ghost, 1), context(intents=["i"], answers=["a"]), NOW)
    assert isinstance(result, Failure)
    assert _ok(store.list_turns(ghost)) == []


def test_claims_and_evidence_are_refused_until_their_stories_persist_them(
    store: SqliteSessionStore,
) -> None:
    # stories 1.3/1.4 own the claims/evidence tables; silently dropping them would lose data
    created = session(1)
    _ok(store.create(created, NOW))
    with_claim = answer(created.session_id, 1).model_copy(
        update={"claims": [{"claim_id": "clm-1", "text": "t", "claim_citations": ["user#alex"]}]}
    )
    result = store.append_turn(created.session_id, with_claim, context(intents=[], answers=[]), NOW)
    assert isinstance(result, Failure) and "claims" in result.observed[0]


# -- expiry / reset ----------------------------------------------------------------------------
def test_mark_expired_is_idempotent_and_keeps_the_first_timestamp(
    store: SqliteSessionStore,
) -> None:
    created = session(1)
    _ok(store.create(created, NOW))
    _ok(store.mark_expired(created.session_id, LATER))
    _ok(store.mark_expired(created.session_id, "2026-10-17T00:00:00.000Z"))
    assert _ok(store.get(created.session_id)).session.status == "expired"
    row = store._connection.execute(  # noqa: SLF001 - verifying persistence, not API
        "select expired_at from sessions where session_id = ?", (created.session_id,)
    ).fetchone()
    assert row == (LATER,)


def test_reset_clears_the_context_keeps_the_turns_and_is_idempotent(
    store: SqliteSessionStore,
) -> None:
    created = session(1)
    _ok(store.create(created, NOW))
    sid = created.session_id
    _ok(store.append_turn(sid, answer(sid, 1), context(intents=["i"], answers=["a"]), LATER))
    _ok(store.reset(sid, LATER))
    _ok(store.reset(sid, LATER))
    stored = _ok(store.get(sid))
    assert stored.session.status == "reset"
    assert stored.session.context == context(intents=[], answers=[])
    assert len(_ok(store.list_turns(sid))) == 1


# -- id seeding --------------------------------------------------------------------------------
def test_highest_counters_start_at_zero_and_track_the_largest_stored_suffix(
    store: SqliteSessionStore,
) -> None:
    assert _ok(store.highest_counters()) == {"session": 0, "answer": 0}
    for n in (3, 10):
        _ok(store.create(session(n), NOW))
    sid = session(10).session_id
    _ok(store.append_turn(sid, answer(sid, 255), context(intents=["i"], answers=["a"]), NOW))
    assert _ok(store.highest_counters()) == {"session": 10, "answer": 255}


# -- robustness --------------------------------------------------------------------------------
def test_a_closed_connection_is_a_typed_failure_never_an_exception(database: str) -> None:
    connection = _connect(database)
    store = SqliteSessionStore(connection)
    connection.close()
    for call in (
        lambda: store.create(session(1), NOW),
        lambda: store.get("sess-0000000000000001"),
        lambda: store.list_turns("sess-0000000000000001"),
        lambda: store.highest_counters(),
    ):
        result = call()
        assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


def test_concurrent_writers_on_one_connection_do_not_corrupt_each_other(
    store: SqliteSessionStore,
) -> None:
    sids = [session(n).session_id for n in range(1, 9)]
    for n in range(1, 9):
        _ok(store.create(session(n), NOW))
    errors: list[object] = []

    def worker(index: int) -> None:
        sid = sids[index]
        for turn in range(25):
            ans = answer(sid, index * 100 + turn + 1)
            result = store.append_turn(
                sid, ans, context(intents=["i"] * (turn + 1), answers=[ans.answer_id]), NOW
            )
            if not is_ok(result):
                errors.append(result)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert all(len(_ok(store.list_turns(sid))) == 25 for sid in sids)


# -- persistence -------------------------------------------------------------------------------
def test_a_file_database_survives_reopening(tmp_path: Path) -> None:
    path = str(tmp_path / "m12.db")
    first = SqliteSessionStore(_connect(path))
    created = session(1)
    _ok(first.create(created, NOW))
    sid = created.session_id
    _ok(first.append_turn(sid, answer(sid, 1), context(intents=["i"], answers=["a"]), LATER))
    first._connection.close()  # noqa: SLF001

    second = SqliteSessionStore(_connect(path))
    assert _ok(second.get(sid)).session.context.prior_intents == ["i"]
    assert len(_ok(second.list_turns(sid))) == 1
    assert _ok(second.highest_counters()) == {"session": 1, "answer": 1}


def test_applied_migrations_are_read_through_the_store_lock(store: SqliteSessionStore) -> None:
    assert "001_module12_copilot_schema.sql" in _ok(store.applied_migrations())


def test_applied_migrations_on_a_closed_connection_is_a_typed_failure(database: str) -> None:
    connection = _connect(database)
    store = SqliteSessionStore(connection)
    connection.close()
    result = store.applied_migrations()
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
