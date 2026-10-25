"""Settings come from M12_* environment variables and are validated at startup (Impl-1 §4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import PROJECT_ROOT, ConfigError, Settings

pytestmark = pytest.mark.unit


def test_defaults_resolve_against_project_root_not_cwd(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)  # a different cwd must not change where fixtures are found
    settings = Settings.from_env({})
    assert settings.fixtures_dir == PROJECT_ROOT / "fixtures"
    assert settings.migrations_dir == PROJECT_ROOT / "migrations"
    assert settings.db_path == ":memory:"
    assert settings.clock_start == "2026-10-16T15:00:00.000Z"
    assert settings.log_level == "INFO"


def test_environment_overrides_every_setting(tmp_path: Path) -> None:
    settings = Settings.from_env(
        {
            "M12_FIXTURES_DIR": str(tmp_path / "fx"),
            "M12_MIGRATIONS_DIR": str(tmp_path / "mg"),
            "M12_DB_PATH": str(tmp_path / "m12.db"),
            "M12_CLOCK_START": "2027-01-02T03:04:05Z",
            "M12_LOG_LEVEL": "debug",
        }
    )
    assert settings.fixtures_dir == tmp_path / "fx"
    assert settings.migrations_dir == tmp_path / "mg"
    assert settings.db_path == str(tmp_path / "m12.db")
    assert settings.clock_start == "2027-01-02T03:04:05Z"
    assert settings.log_level == "DEBUG"


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("M12_CLOCK_START", "yesterday at noon"),
        ("M12_CLOCK_START", "2026-10-16 15:00:00"),
        ("M12_LOG_LEVEL", "LOUD"),
    ],
)
def test_invalid_values_fail_fast_with_the_variable_name(variable: str, value: str) -> None:
    with pytest.raises(ConfigError) as excinfo:
        Settings.from_env({variable: value})
    assert variable in str(excinfo.value)


def test_settings_are_immutable() -> None:
    settings = Settings.from_env({})
    with pytest.raises(Exception):  # noqa: B017 - pydantic raises ValidationError on frozen models
        settings.log_level = "DEBUG"  # type: ignore[misc]


@pytest.mark.parametrize(
    "value",
    [
        "2026-13-45T00:00:00Z",  # month 13: matches the shape, is not a date
        "2026-02-30T00:00:00Z",
        "2026-10-16T25:61:61Z",
        "2026-10-16T15:00:00Z\n",  # a trailing newline (env file) must not slip through
    ],
)
def test_clock_start_must_be_a_real_instant_not_just_the_right_shape(value: str) -> None:
    with pytest.raises(ConfigError) as excinfo:
        Settings.from_env({"M12_CLOCK_START": value})
    assert "M12_CLOCK_START" in str(excinfo.value)


@pytest.mark.parametrize("variable", ["M12_FIXTURES_DIR", "M12_MIGRATIONS_DIR", "M12_DB_PATH"])
@pytest.mark.parametrize("empty", ["", "   "])
def test_empty_paths_are_rejected_instead_of_silently_meaning_the_project_root(
    variable: str, empty: str
) -> None:
    with pytest.raises(ConfigError) as excinfo:
        Settings.from_env({variable: empty})
    assert variable in str(excinfo.value)


def test_relative_db_path_is_anchored_to_the_project_root_but_memory_is_kept(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    assert Settings.from_env({"M12_DB_PATH": "data/m12.db"}).db_path == str(
        PROJECT_ROOT / "data" / "m12.db"
    )
    assert Settings.from_env({"M12_DB_PATH": ":memory:"}).db_path == ":memory:"
    absolute = str(tmp_path / "x.db")
    assert Settings.from_env({"M12_DB_PATH": absolute}).db_path == absolute
