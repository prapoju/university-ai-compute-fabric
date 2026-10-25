"""Settings and environment validation (Impl-1 §4 ``config.py``).

All configuration enters through ``M12_*`` environment variables and is validated once
at startup. Relative paths resolve against the project root, never the working
directory, so the service and the tests behave identically from any cwd.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from src.domain.instants import is_instant

PROJECT_ROOT = Path(__file__).resolve().parents[1]

_ENV_PREFIX = "M12_"


class ConfigError(ValueError):
    """Raised when the environment does not describe a valid configuration."""


class Settings(BaseModel):
    """Validated, immutable runtime settings."""

    model_config = ConfigDict(frozen=True)

    fixtures_dir: Path = PROJECT_ROOT / "fixtures"
    migrations_dir: Path = PROJECT_ROOT / "migrations"
    db_path: str = ":memory:"
    clock_start: str = "2026-10-16T15:00:00.000Z"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("fixtures_dir", "migrations_dir", "db_path", mode="before")
    @classmethod
    def _paths_must_not_be_empty(cls, value: object) -> object:
        # Path("") means "." - an empty variable would silently point at the working directory
        if isinstance(value, str) and not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("fixtures_dir", "migrations_dir", mode="after")
    @classmethod
    def _anchor_relative_paths(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_ROOT / value

    @field_validator("db_path", mode="after")
    @classmethod
    def _anchor_relative_db_path(cls, value: str) -> str:
        if value == ":memory:" or Path(value).is_absolute():
            return value
        return str(PROJECT_ROOT / value)

    @field_validator("clock_start")
    @classmethod
    def _must_be_an_instant(cls, value: str) -> str:
        if not is_instant(value):
            raise ValueError("must be a real ISO-8601 UTC instant such as 2026-10-16T15:00:00.000Z")
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_case_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build settings from ``env`` (defaults to ``os.environ``)."""
        source = os.environ if env is None else env
        raw = {
            name.removeprefix(_ENV_PREFIX).lower(): value
            for name, value in source.items()
            if name.startswith(_ENV_PREFIX)
        }
        unknown = sorted(set(raw) - set(cls.model_fields))
        if unknown:
            names = ", ".join(_ENV_PREFIX + key.upper() for key in unknown)
            raise ConfigError(f"unknown configuration variable(s): {names}")
        try:
            return cls(**raw)
        except ValidationError as exc:
            problems = "; ".join(
                f"{_ENV_PREFIX}{'.'.join(str(p) for p in err['loc']).upper()}: {err['msg']}"
                for err in exc.errors()
            )
            raise ConfigError(problems) from exc
