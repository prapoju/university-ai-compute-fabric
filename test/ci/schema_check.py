#!/usr/bin/env python3
"""CI gate: validate the generated contract artifacts.

Checks that the Phase 1-2 schemas are syntactically valid and internally usable:

* ``001_module12_copilot_schema.sql`` — the DDL executes against a fresh SQLite.
* ``dto.py`` — imports cleanly (enums, DTOs, IdKind).
* ``events.schema.json`` — valid JSON.
* ``openapi.yaml`` — valid YAML (skipped with a notice if PyYAML is absent).

Usage:  python test/ci/schema_check.py     (also: make schema)
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

SCHEMAS = (
    Path(__file__).resolve().parents[1].parent
    / "planning"
    / "detailed-design"
    / "schemas"
)


def check_sql() -> None:
    con = sqlite3.connect(":memory:")
    try:
        con.executescript((SCHEMAS / "001_module12_copilot_schema.sql").read_text())
    finally:
        con.close()


def check_dto() -> None:
    spec = importlib.util.spec_from_file_location("_module12_dto", SCHEMAS / "dto.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)


def check_json() -> None:
    json.loads((SCHEMAS / "events.schema.json").read_text())


def check_openapi() -> None:
    try:
        import yaml  # type: ignore
    except ImportError:
        print("note: PyYAML not installed; openapi.yaml YAML parse skipped")
        return
    yaml.safe_load((SCHEMAS / "openapi.yaml").read_text())


CHECKS = {
    "001_module12_copilot_schema.sql": check_sql,
    "dto.py": check_dto,
    "events.schema.json": check_json,
    "openapi.yaml": check_openapi,
}


def main() -> int:
    failures = 0
    for name, fn in CHECKS.items():
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - report every failure class
            failures += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok   {name}")

    if failures:
        print(f"GATE FAIL: {failures} schema artifact(s) invalid")
        return 1
    print("GATE PASS: all schema artifacts valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
