"""Hexagonal boundary audit (R1-R4, ports-and-adapters.md section 2).

``src/domain`` and ``src/ports`` (and ``src/application`` once it exists) must stay pure:
no web framework, DB driver, network client, randomness, OS access or wall-clock reads, and
no import path to ``src.adapters`` - however the import is spelled (absolute, ``from src
import adapters``, relative) and however the clock is reached (aliases, ``datetime.datetime``).
The audit is itself tested against deliberately bad code so it can never pass vacuously.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from src.config import PROJECT_ROOT

pytestmark = pytest.mark.unit

PURE_LAYERS = ("domain", "ports", "application")
FORBIDDEN_MODULES = {
    "fastapi", "starlette", "sqlite3", "sqlalchemy", "httpx", "requests", "urllib", "urllib3",
    "random", "secrets", "uuid", "time", "os", "importlib", "socket", "subprocess",
}  # fmt: skip
CLOCK_METHODS = {"now", "utcnow", "today"}


def violations(src_root: Path, layers: tuple[str, ...] = PURE_LAYERS) -> list[str]:
    """Every rule break in the pure layers under ``src_root`` as ``"file:line message"``."""
    found: list[str] = []
    for layer in layers:
        folder = src_root / layer
        for path in sorted(folder.rglob("*.py")) if folder.is_dir() else []:
            found += _audit_file(src_root, path)
    return found


def _audit_file(src_root: Path, path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    relative = path.relative_to(src_root)
    package = ["src", *relative.parent.parts]  # the package this file lives in
    module_aliases: set[str] = set()  # names bound to the datetime module
    class_aliases: set[str] = set()  # names bound to datetime.datetime / datetime.date
    found: list[str] = []

    for node in ast.walk(tree):
        where = f"{relative}:{getattr(node, 'lineno', 0)}"

        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_module(alias.name, where, found)
                if alias.name == "datetime":
                    module_aliases.add(alias.asname or "datetime")

        elif isinstance(node, ast.ImportFrom):
            base = _resolve(node, package)
            _check_module(base, where, found)
            for alias in node.names:
                _check_module(f"{base}.{alias.name}" if base else alias.name, where, found)
                if base == "datetime" and alias.name in {"datetime", "date"}:
                    class_aliases.add(alias.asname or alias.name)

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                found.append(f"{where} uses __import__ (dynamic import)")

    # wall-clock reads need the alias tables, so a second pass over the calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in CLOCK_METHODS and _is_datetime_owner(
                node.func.value, module_aliases, class_aliases
            ):
                where = f"{relative}:{node.lineno}"
                found.append(f"{where} reads the wall clock via .{node.func.attr}()")
    return found


def _resolve(node: ast.ImportFrom, package: list[str]) -> str:
    """Absolute dotted name of the module a ``from ... import`` refers to."""
    parts = node.module.split(".") if node.module else []
    if node.level:  # relative: level 1 = this package, 2 = its parent, ...
        anchor = package[: len(package) - (node.level - 1)]
        return ".".join([*anchor, *parts])
    return ".".join(parts)


def _check_module(dotted: str, where: str, found: list[str]) -> None:
    if dotted.split(".")[0] in FORBIDDEN_MODULES:
        found.append(f"{where} imports forbidden module {dotted}")
    if dotted == "src.adapters" or dotted.startswith("src.adapters."):
        found.append(f"{where} imports an adapter ({dotted}) - R3")


def _is_datetime_owner(owner: ast.expr, module_aliases: set[str], class_aliases: set[str]) -> bool:
    if isinstance(owner, ast.Name):
        return owner.id in class_aliases  # dt.now() after `from datetime import datetime as dt`
    if isinstance(owner, ast.Attribute) and isinstance(owner.value, ast.Name):
        # datetime.datetime.now() / datetime.date.today() after `import datetime`
        return owner.value.id in module_aliases and owner.attr in {"datetime", "date"}
    return False


# -- the real code ------------------------------------------------------------------------------
def test_pure_layers_have_no_forbidden_imports_clock_reads_or_adapter_dependencies() -> None:
    assert violations(PROJECT_ROOT / "src") == []


def test_the_pure_layers_exist_so_the_audit_is_not_vacuous() -> None:
    src = PROJECT_ROOT / "src"
    assert (src / "domain").is_dir() and (src / "ports").is_dir()
    checked = [p for layer in ("domain", "ports") for p in (src / layer).rglob("*.py")]
    assert len(checked) >= 10


# -- the audit itself: every way of breaking a rule must be caught ------------------------------
BAD_SOURCES = [
    ("import fastapi\n", "forbidden module fastapi"),
    ("from fastapi import Request\n", "forbidden module fastapi"),
    ("import sqlite3\n", "forbidden module sqlite3"),
    ("import random\n", "forbidden module random"),
    ("import uuid\n", "forbidden module uuid"),
    ("import time\n", "forbidden module time"),
    ("import httpx\n", "forbidden module httpx"),
    ("import os\nos.urandom(4)\n", "forbidden module os"),
    ("from os import getenv\n", "forbidden module os"),
    ("import importlib\n", "forbidden module importlib"),
    ('__import__("os")\n', "dynamic import"),
    ("from src.adapters.outbound.sim import clock_adapter\n", "imports an adapter"),
    ("from src import adapters\n", "imports an adapter"),
    ("from src.adapters import outbound\n", "imports an adapter"),
    ("from ..adapters.outbound import sim\n", "imports an adapter"),
    ("from .. import adapters\n", "imports an adapter"),
    ("from datetime import datetime\nx = datetime.now()\n", "reads the wall clock"),
    ("from datetime import date\nx = date.today()\n", "reads the wall clock"),
    ("import datetime\nx = datetime.datetime.now()\n", "reads the wall clock"),
    ("import datetime as d\nx = d.datetime.utcnow()\n", "reads the wall clock"),
    ("from datetime import datetime as dt\nx = dt.now()\n", "reads the wall clock"),
    ("import datetime\nx = datetime.date.today()\n", "reads the wall clock"),
]


@pytest.mark.parametrize(("source", "expected"), BAD_SOURCES)
def test_the_audit_detects_each_way_of_breaking_a_rule(
    tmp_path: Path, source: str, expected: str
) -> None:
    layer = tmp_path / "domain"
    layer.mkdir()
    (layer / "bad.py").write_text(source, encoding="utf-8")
    assert any(expected in v for v in violations(tmp_path)), violations(tmp_path)


def test_the_audit_accepts_pure_code(tmp_path: Path) -> None:
    layer = tmp_path / "ports"
    layer.mkdir()
    (layer / "ok.py").write_text(
        "import datetime\n"
        "from datetime import UTC, datetime as dt\n"
        "from src.dto import UserRecordDTO\n"
        "def shift(x: dt) -> dt:\n"
        "    return x + datetime.timedelta(seconds=1)\n"
        "def parse(s: str) -> dt:\n"
        '    return dt.strptime(s, "%Y").replace(tzinfo=UTC)\n',
        encoding="utf-8",
    )
    assert violations(tmp_path) == []


# -- the ruff rule mirrors the audit (belt and braces, R1/R3) -----------------------------------
def _ruff(filename: str, source: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--stdin-filename", filename, "-"],
        input=source, capture_output=True, text=True, cwd=PROJECT_ROOT, check=False,
    )  # fmt: skip
    return result.stdout + result.stderr


def test_ruff_bans_framework_imports_in_the_pure_layers_only() -> None:
    assert "TID251" in _ruff("src/domain/probe.py", "import fastapi\n")
    assert "TID251" in _ruff("src/ports/outbound/probe.py", "import sqlite3\n")
    assert "TID251" not in _ruff("src/adapters/inbound/probe.py", "import fastapi\n")
    assert "TID251" not in _ruff("src/bootstrap.py", "import sqlite3\n")
