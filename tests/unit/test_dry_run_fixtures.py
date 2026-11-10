"""Story 2.2 - the CS-101 fixtures, the job ``node`` field and the select vocabulary (D4)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from src.adapters.outbound.sim.estate_loader import load_estate
from src.config import PROJECT_ROOT
from src.domain.result import Failure
from src.dto import SelectorDTO

pytestmark = pytest.mark.unit


def keys(result) -> list[str]:
    assert not isinstance(result, Failure), result
    return [r.id for r in result.value]


def select(**params) -> SelectorDTO:
    return SelectorDTO(method="filter", params=params)


# -- the fixtures the Annex scenario needs -----------------------------------------------------
def test_the_cs_101_group_and_its_three_running_jobs_sit_on_the_annex_nodes(providers) -> None:
    group = providers.groups.get("group#CS-101").value
    assert (group.id, group.name, group.members) == ("group#CS-101", "CS-101", [])
    running = providers.jobs.select(select(group_id="group#CS-101", status="running"))
    assert keys(running) == ["job#job-8901", "job#job-8902", "job#job-8903"]
    assert [j.node for j in running.value] == ["node#ws-gpu-02", "node#ws-gpu-05", "node#ws-gpu-08"]


def test_the_records_that_existed_before_are_untouched(providers) -> None:
    """IR-12: the new group and jobs add records; group-2/-4/-7 and the six old jobs keep theirs."""
    fixtures = PROJECT_ROOT / "fixtures" / "estate"
    jobs = json.loads((fixtures / "jobs.json").read_text(encoding="utf-8"))
    old = [j for j in jobs if j["group_id"] != "group#CS-101"]
    assert [j["id"] for j in old] == [
        "job#job-8801", "job#job-8812", "job#job-8823",
        "job#job-8824", "job#job-8825", "job#job-8830",
    ]  # fmt: skip
    assert all("node" not in j for j in old)  # nothing was added to a record that existed
    for record in old:
        stored = providers.jobs.get(record["id"]).value
        assert stored.node is None
        assert stored.model_dump(exclude={"node"}) == record


def test_the_two_groups_of_the_s1_and_s2_scenarios_are_unchanged(providers) -> None:
    assert providers.groups.get("group#group-4").value.members == [
        "user#mateo", "user#lucas", "user#alex",
    ]  # fmt: skip
    assert [g.id for g in providers.groups.browse("", 1, 100).value] == [
        "group#CS-101", "group#group-2", "group#group-4", "group#group-7",
    ]  # fmt: skip


# -- the vocabulary (D4) ---------------------------------------------------------------------------
def test_an_empty_selector_selects_every_record(providers) -> None:
    assert len(keys(providers.nodes.select(select()))) == 32
    assert len(keys(providers.jobs.select(select()))) == 9


def test_a_scalar_parameter_is_still_an_exact_match(providers) -> None:
    assert keys(providers.jobs.select(select(status="pending"))) == [
        "job#job-8823", "job#job-8824", "job#job-8825",
    ]  # fmt: skip
    assert keys(providers.jobs.select(select(id="job#job-8823"))) == ["job#job-8823"]
    assert keys(providers.jobs.select(select(id="job#nope"))) == []


def test_a_list_value_means_one_of(providers) -> None:
    both = providers.jobs.select(select(id=["job#job-8823", "job#job-8830", "job#nope"]))
    assert keys(both) == ["job#job-8823", "job#job-8830"]
    two_groups = providers.jobs.select(
        select(group_id=["group#group-2", "group#CS-101"], status="running")
    )
    assert keys(two_groups) == ["job#job-8901", "job#job-8902", "job#job-8903"]
    assert keys(providers.jobs.select(select(id=[]))) == []  # one of nothing is nothing


def test_a_list_matches_the_exact_type_of_each_element(providers) -> None:
    """``24.0 == 24`` in Python, but a float is not the integer a node reports (D4)."""
    assert keys(providers.nodes.select(select(gpu_memory_gb=[24]))) != []  # the control
    assert keys(providers.nodes.select(select(gpu_memory_gb=[24.0]))) == []
    assert keys(providers.nodes.select(select(gpu_memory_gb=[True]))) == []


def test_node_ids_selects_the_named_nodes(providers) -> None:
    found = providers.nodes.select(select(node_ids=["node#ws-gpu-11", "node#ws-gpu-02", "node#x"]))
    assert keys(found) == ["node#ws-gpu-02", "node#ws-gpu-11"]  # ordered by id
    assert keys(providers.nodes.select(select(node_ids=[]))) == []


def test_node_ids_combines_with_another_filter(providers) -> None:
    ids = ["node#ws-gpu-02", "node#ws-gpu-11"]
    assert keys(providers.nodes.select(select(node_ids=ids, status="fault"))) == ["node#ws-gpu-11"]


def test_an_unknown_field_is_still_a_malformed_selector(providers) -> None:
    result = providers.jobs.select(select(course_name="CS101"))
    assert isinstance(result, Failure) and result.code == "VALIDATION_MALFORMED_BODY"
    assert isinstance(providers.jobs.select(select(node_ids=["node#ws-gpu-02"])), Failure)


# -- the loader checks the new reference -------------------------------------------------------
def test_a_job_on_a_node_that_does_not_exist_fails_the_whole_load(tmp_path: Path) -> None:
    shutil.copytree(PROJECT_ROOT / "fixtures", tmp_path / "fixtures")
    path = tmp_path / "fixtures" / "estate" / "jobs.json"
    jobs = json.loads(path.read_text(encoding="utf-8"))
    jobs[-1]["node"] = "node#ws-gpu-99"
    path.write_text(json.dumps(jobs), encoding="utf-8")
    result = load_estate(tmp_path / "fixtures")
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert any("jobs.node" in line for line in result.observed)
