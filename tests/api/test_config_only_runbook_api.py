"""Story 3.3 (NFR-10) - a runbook template added only as configuration is served, no code change.

The test copies the whole fixture estate to a temporary folder, drops one new template file into
``runbooks/``, and reads it back through the real route. No source file is edited for it.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.adapters.inbound.app import create_app
from src.config import Settings

pytestmark = pytest.mark.api

CONFIG_ONLY = {
    "template_id": "rb-config-only-01",
    "error_code": "ERR_CONFIG_ONLY_01",
    "steps": ["Check the cooling loop.", "Log the reading in the ticket."],
    "required_tools": ["infrared thermometer"],
    "safety_warnings": ["Power the node down before opening the chassis."],
    "physical_intervention": True,
    "approved_source": "Lab Safety SOP-CFG-01",
    "version": "2.0",
}


def estate_with(tmp_path: Path, extra: dict | None) -> Path:
    fixtures = tmp_path / "fixtures"
    shutil.copytree(Settings.from_env({}).fixtures_dir, fixtures)
    if extra is not None:
        (fixtures / "runbooks" / "config-only-01.json").write_text(
            json.dumps(extra), encoding="utf-8"
        )
    return fixtures


def test_a_template_added_only_as_configuration_is_served_without_a_code_change(
    tmp_path: Path,
) -> None:
    fixtures = estate_with(tmp_path, CONFIG_ONLY)
    with TestClient(create_app(Settings.from_env({"M12_FIXTURES_DIR": str(fixtures)}))) as client:
        response = client.get("/api/v1/runbooks/ERR_CONFIG_ONLY_01")
    assert response.status_code == 200
    body = response.json()
    assert body["steps"] == CONFIG_ONLY["steps"]
    assert body["provenance"] == {"source": "Lab Safety SOP-CFG-01", "version": "2.0"}


def test_without_the_file_the_same_code_is_a_404(tmp_path: Path) -> None:
    fixtures = estate_with(tmp_path, None)
    with TestClient(create_app(Settings.from_env({"M12_FIXTURES_DIR": str(fixtures)}))) as client:
        response = client.get("/api/v1/runbooks/ERR_CONFIG_ONLY_01")
    assert response.status_code == 404
