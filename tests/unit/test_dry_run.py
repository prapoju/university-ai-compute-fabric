"""Story 2.2 - the pure dry-run rules: selector, items, summary and token expiry (AD-4, AD-6)."""

from __future__ import annotations

import pytest

from src.domain.dry_run import (
    EMPTY_SUMMARY,
    JOBS_PORT,
    NODES_PORT,
    build_selector,
    confirmation_enabled,
    enumerate_items,
    impact_summary,
    reexecution_query,
    token_expiry,
)
from src.dto import JobRecordDTO, NodeRecordDTO, SelectorDTO

pytestmark = pytest.mark.unit


def job(n: int, status: str = "running", node: str | None = None) -> JobRecordDTO:
    return JobRecordDTO(
        id=f"job#job-{n}", group_id="group#g", course="C", status=status,
        created_at="2026-10-16T10:00:00.000Z", node=node,
    )  # fmt: skip


def node(n: int, status: str = "available") -> NodeRecordDTO:
    return NodeRecordDTO(
        id=f"node#ws-gpu-{n:02d}", hostname=f"ws-gpu-{n:02d}", gpu_memory_gb=24, status=status,
        cordoned=False, error_code=None, health="ok",
    )  # fmt: skip


# -- the selector: the status comes from the action, never from the text ----------------------
@pytest.mark.parametrize(
    ("action", "kind", "keys", "method", "params"),
    [
        ("cancel_jobs", "group", ["group#CS-101"], JOBS_PORT,
         {"group_id": "group#CS-101", "status": "running"}),
        ("delete_jobs", "group", ["group#group-2"], JOBS_PORT,
         {"group_id": "group#group-2", "status": "pending"}),
        ("cancel_jobs", "group", ["group#a", "group#b"], JOBS_PORT,
         {"group_id": ["group#a", "group#b"], "status": "running"}),
        ("cancel_jobs", "job", ["job#job-1"], JOBS_PORT, {"id": "job#job-1"}),
        ("delete_jobs", "job", ["job#job-1", "job#job-2"], JOBS_PORT,
         {"id": ["job#job-1", "job#job-2"]}),
        ("delete_jobs", None, [], JOBS_PORT, {"status": "pending"}),
        ("cancel_jobs", None, [], JOBS_PORT, {"status": "running"}),
        ("cordon_node", "node", ["node#ws-gpu-02"], NODES_PORT, {"node_ids": ["node#ws-gpu-02"]}),
        ("drain_node", "node", ["node#a", "node#b"], NODES_PORT,
         {"node_ids": ["node#a", "node#b"]}),
        ("cordon_node", None, [], NODES_PORT, {}),
    ],
)  # fmt: skip
def test_the_selector_names_the_port_and_its_filter(action, kind, keys, method, params) -> None:
    selection = build_selector(action, kind, keys)
    assert (selection.method, selection.params) == (method, params)
    assert selection.persisted() == SelectorDTO(method=method, params=params)
    assert selection.query() == SelectorDTO(method="filter", params=params)
    assert reexecution_query(selection.persisted()) == selection.query()


@pytest.mark.parametrize(
    ("action", "kind"),
    [("cancel_jobs", "node"), ("delete_jobs", "node"), ("cordon_node", "group"),
     ("drain_node", "job")],
)  # fmt: skip
def test_a_verb_on_the_wrong_kind_of_target_has_no_selector(action, kind) -> None:
    with pytest.raises(ValueError, match="cannot act"):
        build_selector(action, kind, ["x#y"])


# -- the items ----------------------------------------------------------------------------------
def test_each_item_carries_its_own_status_and_the_list_is_ordered_by_key() -> None:
    items = enumerate_items([job(3), job(1, "pending"), job(2, "cancelled"), job(4, "succeeded")])
    assert [(i.key, i.actionable_value, i.actionable) for i in items] == [
        ("job#job-1", "pending", True),
        ("job#job-2", "cancelled", False),
        ("job#job-3", "running", True),
        ("job#job-4", "succeeded", False),
    ]
    assert {i.actionable_field for i in items} == {"status"}


def test_a_node_in_fault_is_listed_and_not_actionable() -> None:
    items = enumerate_items([node(11, "fault"), node(2), node(5, "reserved"), node(8, "active")])
    assert [(i.key, i.actionable) for i in items] == [
        ("node#ws-gpu-02", True), ("node#ws-gpu-05", True),
        ("node#ws-gpu-08", True), ("node#ws-gpu-11", False),
    ]  # fmt: skip


def test_confirmation_needs_one_actionable_item() -> None:
    assert confirmation_enabled(enumerate_items([job(1), job(2, "cancelled")])) is True
    assert confirmation_enabled(enumerate_items([job(2, "cancelled")])) is False
    assert confirmation_enabled([]) is False


# -- the summary: exact wording --------------------------------------------------------------------
def summary(action, kind, keys, records) -> str:
    return impact_summary(action, build_selector(action, kind, keys), records)


def test_the_annex_summary_lists_the_nodes_of_the_running_jobs() -> None:
    records = [
        job(8903, node="node#ws-gpu-08"), job(8901, node="node#ws-gpu-02"),
        job(8902, node="node#ws-gpu-05"),
    ]  # fmt: skip
    assert summary("cancel_jobs", "group", ["group#CS-101"], records) == (
        "3 active jobs will be terminated across nodes ws-gpu-02, ws-gpu-05, ws-gpu-08"
    )


@pytest.mark.parametrize(
    ("action", "kind", "records", "expected"),
    [
        ("delete_jobs", "group", [job(1, "pending")], "1 pending job will be deleted"),
        ("delete_jobs", None, [job(1, "pending"), job(2, "pending")],
         "2 pending jobs will be deleted"),
        ("cancel_jobs", "job", [job(1, "pending")], "1 job will be terminated"),
        ("cancel_jobs", "group", [job(1, node="node#ws-gpu-02")],
         "1 active job will be terminated across nodes ws-gpu-02"),
        ("cordon_node", "node", [node(2)], "1 node will be cordoned"),
        ("drain_node", None, [node(1), node(2)], "2 nodes will be drained"),
    ],
)  # fmt: skip
def test_the_summary_reads_by_action_target_and_count(action, kind, records, expected) -> None:
    keys = [r.id for r in records] if kind else []
    assert summary(action, kind, keys, records) == expected


def test_only_actionable_items_count_and_a_job_with_no_node_adds_no_node() -> None:
    records = [job(1, "pending"), job(2, "cancelled")]
    assert summary("cancel_jobs", "job", ["job#job-1", "job#job-2"], records) == (
        "1 job will be terminated"
    )


@pytest.mark.parametrize("records", [[], [job(1, "cancelled")], [node(11, "fault")]])
def test_an_empty_or_non_actionable_set_is_zero_affected_items(records) -> None:
    kind = "node" if records and isinstance(records[0], NodeRecordDTO) else "job"
    action = "cordon_node" if kind == "node" else "cancel_jobs"
    assert summary(action, kind, [r.id for r in records], records) == EMPTY_SUMMARY


# -- the token lifetime comes from the snapshot -------------------------------------------
@pytest.mark.parametrize(
    ("ttl", "expected"),
    [
        (60, "2026-10-16T15:01:00.000Z"),
        (5, "2026-10-16T15:00:05.000Z"),
        (3600, "2026-10-16T16:00:00.000Z"),
    ],
)
def test_the_token_lapses_one_lifetime_after_the_snapshot(ttl: int, expected: str) -> None:
    assert token_expiry("2026-10-16T15:00:00.000Z", ttl) == expected
