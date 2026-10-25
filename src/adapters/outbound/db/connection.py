"""SQLite connection factory for the Module-12-owned stores (single writer, AD-10)."""

from __future__ import annotations

import sqlite3


def open_database(path: str) -> sqlite3.Connection:
    """Open the Module 12 database.

    ``check_same_thread=False`` because FastAPI serves sync handlers from a thread pool;
    writes stay serialized behind the single Audit Writer introduced in later stories.
    """
    return sqlite3.connect(path, check_same_thread=False)
