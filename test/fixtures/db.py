"""``db`` — ephemeral, migrated SQLite from ``001_module12_copilot_schema.sql``.

Re-exports the canonical implementation from ``tests/support/db.py``.
Anchors: the DDL under ``planning/detailed-design/schemas``; AD-10 (append-only
audit, rotation gate). Requires SQLite >= 3.35 (``RETURNING`` + JSON1).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

from support.db import TestDatabase, connect_ephemeral  # noqa: E402

__all__ = ["TestDatabase", "connect_ephemeral"]
