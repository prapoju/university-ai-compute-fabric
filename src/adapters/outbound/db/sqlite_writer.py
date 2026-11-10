"""The single SQLite writer for every Module-12-owned store (review D-6, log I2-06, IR-05).

One connection and one lock serve the session store, the audit store and the migration runner.
With a lock per store, store B's ``commit()`` on the shared connection would commit store A's
half-written transaction; here only this module begins, commits or rolls back.

The connection runs with ``isolation_level=None``, so the driver opens no implicit transaction:
every write runs inside an explicit ``BEGIN IMMEDIATE ... COMMIT | ROLLBACK``. ``transaction()``
is re-entrant on the holding thread, and an inner block joins the outer transaction. Once any
block raises (or ``abort()`` is called) the transaction is rollback-only: a later inner block
raises :class:`RollbackOnly` and the outermost exit rolls back.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from src.ports.outbound.unit_of_work import UnitOfWorkError, UnitOfWorkPort


class RollbackOnly(sqlite3.Error):
    """The enclosing transaction already failed; this block would be rolled back anyway."""


class _Handle:
    def __init__(self, writer: SqliteWriter) -> None:
        self._writer = writer

    def abort(self) -> None:
        self._writer._rollback_only = True  # noqa: SLF001 - the handle is part of the writer


class SqliteWriter(UnitOfWorkPort):
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._lock = threading.RLock()
        self._depth = 0
        self._rollback_only = False

    @classmethod
    def open(cls, path: str) -> SqliteWriter:
        connection = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
        except sqlite3.Error:
            connection.close()
            raise
        return cls(connection)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            if self._depth == 0:
                self._connection.execute("BEGIN IMMEDIATE")
                self._rollback_only = False
            elif self._rollback_only:
                raise RollbackOnly("the enclosing transaction is rollback-only")
            self._depth += 1
            try:
                yield self._connection
            except BaseException:
                self._rollback_only = True
                raise
            finally:
                self._depth -= 1
                if self._depth == 0:
                    self._finish()

    def _finish(self) -> None:
        if self._rollback_only:
            self._rollback()
            return
        try:
            self._connection.execute("COMMIT")
        except sqlite3.Error:
            self._rollback()
            raise

    def _rollback(self) -> None:
        try:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass  # a dead connection has nothing left to roll back

    @contextmanager
    def atomic(self) -> Iterator[_Handle]:
        try:
            with self.transaction():
                yield _Handle(self)
        except sqlite3.Error as exc:
            raise UnitOfWorkError(f"{type(exc).__name__}: {exc}") from exc

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        # one connection cannot serve two threads at once (D-6.2), so reads take the lock too
        with self._lock:
            yield self._connection

    def run_script(self, script: str) -> None:
        """Run a migration script (``executescript`` commits any pending transaction first)."""
        with self._lock:
            try:
                self._connection.executescript(script)
            except sqlite3.Error:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()
