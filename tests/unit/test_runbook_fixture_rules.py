"""Story 3.3 - registration rules of runbook templates (D44, AD-9), enforced when the estate loads.

The registry port is read-only (AD-1), so a template is checked when the fixtures load: it needs at
least one step, a physical-intervention template needs an approved source, and an error code is
registered once. A bad template makes the estate unloadable (PROVIDER_UNAVAILABLE), never partly
loaded.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from src.adapters.outbound.sim.estate_loader import load_estate
from src.config import Settings
from src.domain.result import is_failure, is_ok

pytestmark = pytest.mark.unit

BASE = json.loads(
    (Settings.from_env({}).fixtures_dir / "runbooks" / "err-thermal-88.json").read_text(
        encoding="utf-8"
    )
)


def estate_with_runbooks(tmp_path: Path, *templates: dict) -> Path:
    fixtures = tmp_path / "fixtures"
    shutil.copytree(Settings.from_env({}).fixtures_dir, fixtures)
    folder = fixtures / "runbooks"
    for path in folder.glob("*.json"):
        path.unlink()
    for index, template in enumerate(templates):
        (folder / f"t{index}.json").write_text(json.dumps(template), encoding="utf-8")
    return fixtures


def reason(result) -> str:
    assert is_failure(result), result
    assert result.code == "PROVIDER_UNAVAILABLE"
    return " ".join(result.observed)


def test_the_registered_fixtures_load() -> None:
    assert is_ok(load_estate(Settings.from_env({}).fixtures_dir))


def test_an_empty_steps_template_is_rejected_when_the_estate_loads(tmp_path: Path) -> None:
    fixtures = estate_with_runbooks(tmp_path, {**BASE, "steps": []})
    assert "steps" in reason(load_estate(fixtures))


def test_a_physical_template_without_an_approved_source_is_rejected(tmp_path: Path) -> None:
    fixtures = estate_with_runbooks(tmp_path, {**BASE, "approved_source": None})
    assert "RUNBOOK_TEMPLATE_UNSOURCED" in reason(load_estate(fixtures))


def test_a_non_physical_template_needs_no_source(tmp_path: Path) -> None:
    fixtures = estate_with_runbooks(
        tmp_path, {**BASE, "physical_intervention": False, "approved_source": None}
    )
    assert is_ok(load_estate(fixtures))


def test_an_error_code_is_registered_once(tmp_path: Path) -> None:
    fixtures = estate_with_runbooks(tmp_path, BASE, {**BASE, "template_id": "rb-copy"})
    assert "duplicate error_code" in reason(load_estate(fixtures))


def test_an_estate_with_no_runbook_templates_is_rejected(tmp_path: Path) -> None:
    fixtures = estate_with_runbooks(tmp_path)
    assert "no runbook templates" in reason(load_estate(fixtures))
