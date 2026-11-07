"""SqliteWriter: one connection, one lock, explicit transactions (review D-6, log I2-06, IR-05).

Runs on the real migrated schema. The cross-store case runs on a file database, with threads
coordinated by ``threading.Event`` only (no sleeps).
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from src.adapters.outbound.db.migrate import apply_migrations
from src.adapters.outbound.db.session_store import SqliteSessionStore
from src.adapters.outbound.db.sqlite_writer import RollbackOnly, SqliteWriter
from src.config import PROJECT_ROOT
from src.domain.result import Failure, Ok
from src.dto import SessionContextDTO, SessionDTO
from src.ports.outbound import UnitOfWorkError

pytestmark = pytest.mark.integration

NOW = "2026-10-16T15:00:00.000Z"
INSERT = (
    "INSERT INTO sessions (session_id, created_at, updated_at, operator_role, status)"
    " VALUES (?, ?, ?, 'role-operations', 'active')"
)


def sid(n: int) -> str:
    return f"sess-{n:016x}"


def session(n: int) -> SessionDTO:
    return SessionDTO(
        session_id=sid(n),
        created_at=NOW,
        operator_role="role-operations",
        context=SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[]),
        status="active",
    )


def migrated(path: str = ":memory:") -> SqliteWriter:
    writer = SqliteWriter.open(path)
    apply_migrations(writer, PROJECT_ROOT / "migrations")
    return writer


def insert(connection: sqlite3.Connection, n: int) -> None:
    connection.execute(INSERT, (sid(n), NOW, NOW))


def stored_ids(writer: SqliteWriter) -> list[str]:
    with writer.read() as connection:
        rows = connection.execute("SELECT session_id FROM sessions ORDER BY session_id")
        return [value for (value,) in rows]


@pytest.fixture
def writer() -> SqliteWriter:
    box = migrated()
    yield box
    box.close()


# -- pragmas -----------------------------------------------------------------------------------
def test_open_pins_the_pragmas_and_autocommit_mode(tmp_path: Path) -> None:
    writer = migrated(str(tmp_path / "m12.db"))
    with writer.read() as connection:
        assert connection.isolation_level is None
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        assert connection.execute("PRAGMA busy_timeout").fetchone() == (5000,)
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert not connection.in_transaction
    writer.close()


# -- commit / rollback / nesting ---------------------------------------------------------------
def test_a_transaction_commits_on_exit(writer: SqliteWriter) -> None:
    with writer.transaction() as connection:
        insert(connection, 1)
        assert connection.in_transaction
    with writer.read() as connection:
        assert not connection.in_transaction
    assert stored_ids(writer) == [sid(1)]


def test_a_nested_block_joins_the_outer_transaction_and_commits_with_it(
    writer: SqliteWriter,
) -> None:
    with writer.transaction() as outer:
        insert(outer, 1)
        with writer.transaction() as inner:
            insert(inner, 2)
        with writer.read() as connection:
            assert connection.in_transaction  # the inner exit did not commit
    assert stored_ids(writer) == [sid(1), sid(2)]


def test_an_inner_failure_rolls_back_the_whole_transaction(writer: SqliteWriter) -> None:
    with writer.transaction() as outer:
        insert(outer, 1)
        with pytest.raises(ValueError), writer.transaction() as inner:
            insert(inner, 2)
            raise ValueError("inner failed")
        insert(outer, 3)  # still inside the open (now rollback-only) transaction
    assert stored_ids(writer) == []


def test_reentry_after_a_failure_raises_rollback_only(writer: SqliteWriter) -> None:
    with writer.transaction() as outer:
        insert(outer, 1)
        with pytest.raises(ValueError), writer.transaction():
            raise ValueError("first block failed")
        with pytest.raises(RollbackOnly), writer.transaction() as never:
            insert(never, 2)  # pragma: no cover - the block is never entered
    assert issubclass(RollbackOnly, sqlite3.Error)  # the stores map it to a typed Failure
    assert stored_ids(writer) == []


def test_a_store_write_inside_a_failed_transaction_is_a_typed_failure(
    writer: SqliteWriter,
) -> None:
    store = SqliteSessionStore(writer)
    with writer.atomic() as tx:
        tx.abort()
        result = store.create(session(1), NOW)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert "RollbackOnly" in result.observed[0]
    assert stored_ids(writer) == []


def test_abort_rolls_back_without_an_exception(writer: SqliteWriter) -> None:
    store = SqliteSessionStore(writer)
    with writer.atomic() as tx:
        assert store.create(session(1), NOW) == Ok(None)
        tx.abort()
    assert stored_ids(writer) == []
    # the next transaction starts clean
    with writer.atomic():
        assert store.create(session(2), NOW) == Ok(None)
    assert stored_ids(writer) == [sid(2)]


def test_atomic_joins_store_writes_into_one_commit(writer: SqliteWriter) -> None:
    store = SqliteSessionStore(writer)
    with writer.atomic():
        assert store.create(session(1), NOW) == Ok(None)
        assert store.create(session(1), NOW).code == "PROVIDER_UNAVAILABLE"  # duplicate key
        assert store.create(session(2), NOW).code == "PROVIDER_UNAVAILABLE"  # rollback-only
    assert stored_ids(writer) == []


def test_atomic_reports_a_begin_failure_as_a_unit_of_work_error(writer: SqliteWriter) -> None:
    writer.close()
    with pytest.raises(UnitOfWorkError, match="ProgrammingError"), writer.atomic():
        pass  # pragma: no cover - BEGIN fails before the block runs


def test_a_commit_failure_rolls_back_and_raises(writer: SqliteWriter) -> None:
    # a deferred foreign key is only checked at COMMIT time
    with pytest.raises(UnitOfWorkError, match="FOREIGN KEY"), writer.atomic():
        with writer.transaction() as connection:
            connection.execute("PRAGMA defer_foreign_keys = ON")
            connection.execute(
                "INSERT INTO tool_calls (tool_call_id, session_id, tool_name, timestamp,"
                " status, created_at) VALUES ('tc-0000000000000001', ?, 't', ?, 'ok', ?)",
                (sid(9), NOW, NOW),
            )
    with writer.read() as connection:
        assert not connection.in_transaction
        assert connection.execute("SELECT count(*) FROM tool_calls").fetchone() == (0,)


def test_an_unexpected_exception_propagates_after_the_rollback(writer: SqliteWriter) -> None:
    with pytest.raises(KeyError), writer.transaction() as connection:
        insert(connection, 1)
        raise KeyError("boom")
    assert stored_ids(writer) == []


# -- scripts -----------------------------------------------------------------------------------
def test_a_failing_script_rolls_back_and_re_raises(writer: SqliteWriter) -> None:
    with pytest.raises(sqlite3.OperationalError):
        writer.run_script(
            "BEGIN; CREATE TABLE half (x integer); CREATE TABLE half (x integer); COMMIT;"
        )
    with writer.read() as connection:
        assert not connection.in_transaction
        names = {n for (n,) in connection.execute("SELECT name FROM sqlite_master")}
    assert "half" not in names


# -- cross-store (§6.3.5 IR-05 row) ------------------------------------------------------------
def test_a_failing_transaction_is_never_committed_by_another_stores_write(tmp_path: Path) -> None:
    """Thread A fails partway through its own transaction while thread B commits through the
    session store. With one writer lock, A's row is absent and B's row is present.

    Red against the old design (a lock per store on one shared connection): B's ``commit()``
    committed A's half-written row (see the story Debug Log)."""
    writer = migrated(str(tmp_path / "m12.db"))
    store = SqliteSessionStore(writer)
    a_inserted = threading.Event()
    b_started = threading.Event()
    outcome: dict[str, object] = {}

    def thread_a() -> None:
        try:
            with writer.transaction() as connection:
                insert(connection, 1)
                a_inserted.set()
                b_started.wait(timeout=10)
                raise RuntimeError("store A failed partway")
        except RuntimeError as exc:
            outcome["a"] = exc

    def thread_b() -> None:
        a_inserted.wait(timeout=10)
        b_started.set()
        outcome["b"] = store.create(session(2), NOW)

    threads = [threading.Thread(target=thread_a), threading.Thread(target=thread_b)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert a_inserted.is_set() and b_started.is_set()
    assert isinstance(outcome["a"], RuntimeError)
    assert outcome["b"] == Ok(None)
    assert stored_ids(writer) == [sid(2)]
    writer.close()
