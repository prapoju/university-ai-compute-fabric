"""The seeded estate: 32-node fleet, S1-S4 anchors and referential integrity (story 1.1, AC 1).

Reads the JSON fixtures directly (not through an adapter) so a broken seed fails here first.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

import pytest

from src.config import PROJECT_ROOT
from src.dto import (
    AccessPolicyClauseDTO,
    GroupRecordDTO,
    JobRecordDTO,
    ModelCatalogEntryDTO,
    NodeRecordDTO,
    OperationalEventDTO,
    PolicyWindowDTO,
    ReservationRecordDTO,
    RunbookTemplateDTO,
    UserRecordDTO,
)

pytestmark = pytest.mark.unit

ESTATE = PROJECT_ROOT / "fixtures" / "estate"

# store file -> (DTO, id field, entity type used in the {type}#{id} key)
STORES: dict[str, tuple[Any, str, str]] = {
    "users": (UserRecordDTO, "id", "user"),
    "catalog": (ModelCatalogEntryDTO, "id", "model"),
    "policy": (AccessPolicyClauseDTO, "clause_id", "policy"),
    "groups": (GroupRecordDTO, "id", "group"),
    "jobs": (JobRecordDTO, "id", "job"),
    "nodes": (NodeRecordDTO, "id", "node"),
    "reservations": (ReservationRecordDTO, "id", "reservation"),
    "windows": (PolicyWindowDTO, "window_id", "window"),
    "events": (OperationalEventDTO, "event_id", "event"),
}


def _load(store: str) -> list[dict[str, Any]]:
    return json.loads((ESTATE / f"{store}.json").read_text(encoding="utf-8"))


def _by_id(store: str) -> dict[str, dict[str, Any]]:
    id_field = STORES[store][1]
    return {record[id_field]: record for record in _load(store)}


@pytest.mark.parametrize("store", sorted(STORES))
def test_every_store_is_present_non_empty_and_dto_exact(store: str) -> None:
    dto, id_field, entity_type = STORES[store]
    records = _load(store)
    assert records, f"{store}.json is empty"
    for record in records:
        dto.model_validate(record)  # extra="forbid": a stray field is a contract violation
        assert record[id_field].startswith(f"{entity_type}#"), record[id_field]


@pytest.mark.parametrize("store", sorted(STORES))
def test_ids_are_unique_within_each_store(store: str) -> None:
    id_field = STORES[store][1]
    ids = [record[id_field] for record in _load(store)]
    assert [i for i, n in Counter(ids).items() if n > 1] == []


def test_fleet_is_32_nodes_31_workstations_of_24gb_and_one_2x48gb_server() -> None:
    nodes = _load("nodes")
    assert len(nodes) == 32
    memory = Counter(node["gpu_memory_gb"] for node in nodes)
    assert memory == {24: 31, 96: 1}  # the server's 2 x 48 GB is stored as an aggregate
    hostnames = {node["hostname"] for node in nodes}
    assert hostnames == {f"ws-gpu-{n:02d}" for n in range(1, 33)}
    assert [n["hostname"] for n in nodes if n["gpu_memory_gb"] == 96] == ["ws-gpu-32"]


def test_s3_node_ws_gpu_11_is_the_only_cordoned_faulted_node() -> None:
    nodes = _by_id("nodes")
    node = nodes["node#ws-gpu-11"]
    assert (node["status"], node["cordoned"], node["error_code"], node["health"]) == (
        "fault", True, "ERR_THERMAL_88", "fault",
    )  # fmt: skip
    assert [n["id"] for n in nodes.values() if n["cordoned"]] == ["node#ws-gpu-11"]
    assert [n["id"] for n in nodes.values() if n["status"] == "fault"] == ["node#ws-gpu-11"]


def test_s1_anchors_alex_deepseek_coder_clause_and_denial_event() -> None:
    assert _by_id("users")["user#alex"]["role"] == "student"
    deepseek = _by_id("catalog")["model#deepseek-coder"]
    assert "student" not in deepseek["allowed_roles"]
    clause = _by_id("policy")["policy#catalog.4.2"]
    assert clause["model_id"] == "model#deepseek-coder"
    assert clause["reason_class"] == "not-in-allowlist"
    event = _by_id("events")["event#evt-4711"]
    assert (event["type"], event["entity_ref"]) == ("access_denied", "user#alex")


def test_s2_anchors_group_4_job_8823_and_the_night_window() -> None:
    job = _by_id("jobs")["job#job-8823"]
    assert (job["group_id"], job["status"], job["scheduling_constraint"]) == (
        "group#group-4", "pending", "night",
    )  # fmt: skip
    night = _by_id("windows")["window#night"]
    assert night["start"].endswith("T22:00:00.000Z") and night["end"].endswith("T06:00:00.000Z")
    assert night["start"] < night["end"]  # D66; the window spans midnight into the next day
    sources = {p["source_id"] for p in _policy_content()}
    assert "policy#night.2" in sources


def test_s4_has_several_pending_cs201_jobs_including_job_8823() -> None:
    cs201 = [j for j in _load("jobs") if j["course"] == "CS201"]
    pending = [j["id"] for j in cs201 if j["status"] == "pending"]
    assert len(pending) >= 3 and "job#job-8823" in pending


def test_referential_integrity_across_stores() -> None:
    users, models, nodes = _by_id("users"), _by_id("catalog"), _by_id("nodes")
    groups, jobs = _by_id("groups"), _by_id("jobs")
    assert all(c["model_id"] in models for c in _load("policy"))
    assert all(m in users for g in groups.values() for m in g["members"])
    assert all(j["group_id"] in groups for j in jobs.values())
    assert all(r["node_id"] in nodes for r in _load("reservations"))
    refs = {**users, **jobs, **nodes}
    assert all(e["entity_ref"] in refs for e in _load("events"))


def test_reservations_and_windows_are_half_open_with_start_before_end() -> None:
    for record in [*_load("reservations"), *_load("windows")]:
        assert record["start"] < record["end"]  # D66 provider invariant


def _policy_content() -> list[dict[str, Any]]:
    folder = PROJECT_ROOT / "fixtures" / "policy_content"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]


def test_policy_content_is_bounded_curated_text() -> None:
    content = _policy_content()
    assert content
    for item in content:
        assert set(item) == {"source_id", "text", "version"}
        assert 1 <= len(item["text"]) <= 2000


def test_runbook_templates_are_valid_at_load_time() -> None:
    folder = PROJECT_ROOT / "fixtures" / "runbooks"
    templates = [
        RunbookTemplateDTO.model_validate(json.loads(p.read_text(encoding="utf-8")))
        for p in sorted(folder.glob("*.json"))
    ]
    assert "ERR_THERMAL_88" in {t.error_code for t in templates}
    for template in templates:
        assert len(template.steps) >= 1  # D44 - checked here, at fixture-load time
        if template.physical_intervention:
            assert template.approved_source  # RUNBOOK_TEMPLATE_UNSOURCED otherwise


def test_course_copy_of_the_fleet_matches_the_single_source_of_truth() -> None:
    course_copy = PROJECT_ROOT / "tests" / "fixtures" / "nodes.json"
    assert json.loads(course_copy.read_text(encoding="utf-8")) == _load("nodes")
