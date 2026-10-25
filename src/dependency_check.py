"""Startup dependency validation (Impl-1 §1 "dependency validation").

``python -m src.dependency_check`` prints every problem and exits non-zero, so a broken
environment fails loudly *before* the service starts instead of half-working.
"""

from __future__ import annotations

import importlib
import sqlite3
import sys

from src.config import ConfigError, Settings

MIN_PYTHON = (3, 11)
MIN_SQLITE = (3, 35, 0)  # AD-10: RETURNING + JSON1
REQUIRED_PACKAGES = ("fastapi", "pydantic", "uvicorn")


class DependencyError(RuntimeError):
    """The runtime environment cannot host the service."""


def _python_version() -> tuple[int, int, int]:
    info = sys.version_info
    return info.major, info.minor, info.micro


def _as_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split(".")[:3] if part.isdigit())


def check(settings: Settings) -> list[str]:
    """Return a human-readable list of problems (empty when the environment is fine)."""
    problems: list[str] = []

    if _python_version()[:2] < MIN_PYTHON:
        found = ".".join(str(n) for n in _python_version())
        problems.append(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required; found {found}.")

    if _as_tuple(sqlite3.sqlite_version) < MIN_SQLITE:
        problems.append(
            f"SQLite >= {'.'.join(str(n) for n in MIN_SQLITE[:2])} is required "
            f"(RETURNING/JSON1, AD-10); found {sqlite3.sqlite_version}."
        )

    for package in REQUIRED_PACKAGES:
        try:
            importlib.import_module(package)
        except ImportError:
            problems.append(f"Python package '{package}' is not installed (pip install -e .[dev]).")

    if not settings.fixtures_dir.is_dir():
        problems.append(f"Fixtures directory not found: {settings.fixtures_dir}")

    return problems


def require(settings: Settings) -> None:
    """Raise one :class:`DependencyError` listing every problem."""
    problems = check(settings)
    if problems:
        raise DependencyError("Environment check failed:\n- " + "\n- ".join(problems))


def main() -> int:
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        print(f"Invalid configuration: {exc}", file=sys.stderr)
        return 2
    problems = check(settings)
    for problem in problems:
        print(f"- {problem}", file=sys.stderr)
    if problems:
        return 1
    print("Environment OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
