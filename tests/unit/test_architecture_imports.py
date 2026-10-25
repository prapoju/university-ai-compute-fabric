"""Hexagonal boundary audit (R1-R4, ports-and-adapters.md section 2).

``src/domain`` and ``src/ports`` (and ``src/application`` once it exists) must stay pure:
no web framework, DB driver, network client, randomness or wall-clock reads, and no import
path to ``src.adapters``. The audit is itself tested against deliberately bad code so it can
never pass vacuously.
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
    "fastapi", "starlette", "sqlite3", "sqlalchemy", "httpx", "requests", "urllib3",
    "random", "secrets", "uuid", "time",
}  # fmt: skip
CLOCK_READS = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("datetime", "today"),
    ("date", "today"),
}


def violations(src_root: Path, layers: tuple[str, ...] = PURE_LAYERS) -> list[str]:
    """Every rule break in the pure layers under ``src_root`` as ``"file:line message"``."""
    found: list[str] = []
    for layer in layers:
        for path in sorted((src_root / layer).rglob("*.py")) if (src_root / layer).is_dir() else []:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                where = f"{path.relative_to(src_root)}:{getattr(node, 'lineno', 0)}"
                for module in _imported_modules(node):
                    if module.split(".")[0] in FORBIDDEN_MODULES:
                        found.append(f"{where} imports forbidden module {module}")
                    if module == "src.adapters" or module.startswith("src.adapters."):
                        found.append(f"{where} imports an adapter ({module}) - R3")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    owner = node.func.value
                    if isinstance(owner, ast.Name) and (owner.id, node.func.attr) in CLOCK_READS:
                        found.append(
                            f"{where} reads the wall clock via {owner.id}.{node.func.attr}()"
                        )
    return found


def _imported_modules(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
        return [node.module]
    return []


# -- the real code ------------------------------------------------------------------------------
def test_pure_layers_have_no_forbidden_imports_clock_reads_or_adapter_dependencies() -> None:
    assert violations(PROJECT_ROOT / "src") == []


def test_the_pure_layers_exist_so_the_audit_is_not_vacuous() -> None:
    assert (PROJECT_ROOT / "src" / "domain").is_dir() and (PROJECT_ROOT / "src" / "ports").is_dir()
    checked = [
        p for layer in ("domain", "ports") for p in (PROJECT_ROOT / "src" / layer).rglob("*.py")
    ]
    assert len(checked) >= 10


# -- the audit itself ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import fastapi\n", "forbidden module fastapi"),
        ("from fastapi import Request\n", "forbidden module fastapi"),
        ("import sqlite3\n", "forbidden module sqlite3"),
        ("import random\n", "forbidden module random"),
        ("import uuid\n", "forbidden module uuid"),
        ("import time\n", "forbidden module time"),
        ("import httpx\n", "forbidden module httpx"),
        ("from src.adapters.outbound.sim import clock_adapter\n", "imports an adapter"),
        ("from datetime import datetime\nx = datetime.now()\n", "reads the wall clock"),
        ("from datetime import date\nx = date.today()\n", "reads the wall clock"),
    ],
)
def test_the_audit_detects_each_kind_of_violation(
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
        "from datetime import datetime, timedelta\nfrom src.dto import UserRecordDTO\n"
        "def shift(x: datetime) -> datetime:\n    return x + timedelta(seconds=1)\n",
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
