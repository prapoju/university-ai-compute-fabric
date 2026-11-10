"""Only the SqliteWriter begins, commits or rolls back (review D-6.5b, log I2-06, TG-I2-1).

A second module that opens a connection or commits on the shared one brings back the IR-05
defect: its ``commit()`` would commit another store's half-written transaction. The checker is
fed a bad snippet once, so it cannot pass vacuously.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.config import PROJECT_ROOT

pytestmark = pytest.mark.unit

SRC = PROJECT_ROOT / "src"
WRITER = SRC / "adapters" / "outbound" / "db" / "sqlite_writer.py"
FORBIDDEN_CALLS = {"commit", "rollback"}


def offences(source: str, where: str) -> list[str]:
    """Every ``.commit(``, ``.rollback(`` or ``sqlite3.connect(`` call in ``source``."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        name = node.func.attr
        target = node.func.value
        if name in FORBIDDEN_CALLS:
            found.append(f"{where}:{node.lineno} .{name}(")
        elif name == "connect" and isinstance(target, ast.Name) and target.id == "sqlite3":
            found.append(f"{where}:{node.lineno} sqlite3.connect(")
    return found


def test_no_module_but_the_writer_commits_rolls_back_or_connects() -> None:
    found: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if path != WRITER:
            found += offences(path.read_text(encoding="utf-8"), str(path.relative_to(SRC)))
    assert found == []


def test_the_writer_itself_is_where_the_connection_is_opened() -> None:
    # guards the exemption: if the writer stopped connecting, the check above would be moot
    assert any("sqlite3.connect(" in o for o in offences(WRITER.read_text("utf-8"), "w"))


def test_the_checker_catches_each_forbidden_call() -> None:
    bad = (
        "import sqlite3\n"
        "c = sqlite3.connect(':memory:')\n"
        "c.commit()\n"
        "self._connection.rollback()\n"
        "c.execute('select 1')\n"
    )
    assert offences(bad, "bad.py") == [
        "bad.py:2 sqlite3.connect(",
        "bad.py:3 .commit(",
        "bad.py:4 .rollback(",
    ]


def test_the_scan_covers_the_stores() -> None:
    scanned = {p.name for p in SRC.rglob("*.py")}
    assert {"session_store.py", "migrate.py", "bootstrap.py"} <= scanned
    assert not (Path(SRC) / "adapters" / "outbound" / "db" / "connection.py").exists()
