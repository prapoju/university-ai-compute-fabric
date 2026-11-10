"""Story 2.4 - the pure execution rules and the simulated executor (OP-15, AD-1, AD-3, AD-15)."""

from __future__ import annotations

import pytest

from src.adapters.outbound.sim.executor_adapter import SimExecutor
from src.adapters.outbound.sim.record_store import RecordStore
from src.domain.execution import (
    classify,
    effect,
    expected_keys,
    still_promised,
    within_limit,
)
from src.domain.result import Failure, Ok
from src.dto import (
    AffectedItemDTO,
    DryRunSnapshotDTO,
    ExecutorRequestDTO,
    JobRecordDTO,
    NodeRecordDTO,
    ProposalDTO,
    SelectorDTO,
)

pytestmark = pytest.mark.unit

T0 = "2026-10-16T15:00:00.000Z"
TOKEN = "gt-" + "ab" * 16


def job(n: int, status: str = "running") -> JobRecordDTO:
    return JobRecordDTO(
        id=f"job#job-{n}", group_id="group#g", course="C", status=status, created_at=T0
    )


def node(n: int, status: str = "available") -> NodeRecordDTO:
    return NodeRecordDTO(
        id=f"node#ws-gpu-{n:02d}", hostname=f"h{n}", gpu_memory_gb=24, status=status,
        cordoned=False, error_code=None, health="ok",
    )  # fmt: skip


def item(key: str, value: str = "running", actionable: bool = True) -> AffectedItemDTO:
    return AffectedItemDTO(
        key=key, actionable=actionable, actionable_field="status", actionable_value=value
    )


# -- the pure rules -------------------------------------------------------------------------------
def test_each_verb_has_its_effect() -> None:
    assert effect("cancel_jobs", job(1)).status == "cancelled"
    assert effect("delete_jobs", job(1)) is None
    assert effect("cordon_node", node(2)).cordoned is True
    drained = effect("drain_node", node(2))
    assert (drained.cordoned, drained.health, drained.status) == (True, "draining", "available")


def test_an_effect_never_changes_the_record_it_was_given() -> None:
    original = job(1)
    effect("cancel_jobs", original)
    assert original.status == "running"


def test_the_expected_keys_are_the_actionable_ones_in_order() -> None:
    items = [item("job#b"), item("job#a", "cancelled", False), item("job#c")]
    assert expected_keys(items) == ["job#b", "job#c"]


def test_an_item_is_promised_only_while_the_record_is_in_that_state() -> None:
    assert still_promised(item("job#job-1"), job(1))
    assert not still_promised(item("job#job-1"), job(1, "succeeded"))
    assert not still_promised(item("job#job-1"), None)
    assert not still_promised(item("job#job-1", actionable=False), job(1))


@pytest.mark.parametrize(
    ("expected", "applied", "result"),
    [
        (["a", "b"], ["a", "b"], "applied"),
        (["a", "b"], ["b", "a"], "applied"),
        (["a", "b"], ["a"], "partial"),
        (["a", "b"], [], "partial"),
        (["a", "b"], ["a", "b", "c"], "failed"),  # more than the scope
        (["a", "b"], ["a", "x"], "failed"),  # a key outside it
        (["a", "b"], ["a", "a"], "failed"),  # a key twice
        ([], [], "applied"),
    ],
)
def test_a_result_is_classified_against_the_scope(expected, applied, result) -> None:
    assert classify(expected, applied) == result


@pytest.mark.parametrize(
    ("returned", "ok"),
    [
        ("2026-10-16T15:00:04.999Z", True),
        ("2026-10-16T15:00:05.000Z", True),  # the boundary is accepted
        ("2026-10-16T15:00:05.001Z", False),
        ("2026-10-16T15:01:00.000Z", False),
    ],
)
def test_the_executor_has_five_seconds(returned: str, ok: bool) -> None:
    assert within_limit(T0, returned) is ok


# -- the store's write path -----------------------------------------------------------------------
def test_the_record_store_replaces_and_removes_by_key_and_keeps_its_order() -> None:
    store = RecordStore([job(2), job(1), job(3)], lambda r: r.id)
    assert store.replace("job#job-2", job(2, "cancelled")) is True
    assert store.get("job#job-2").value.status == "cancelled"
    assert store.remove("JOB#JOB-1") is True  # case-folded, like the reads
    assert [r.id for r in store.all()] == ["job#job-2", "job#job-3"]
    assert store.replace("job#nope", job(9)) is False and store.remove("job#nope") is False


# -- the simulated executor -----------------------------------------------------------------------
class Clock:
    def __init__(self) -> None:
        self.seconds = 0.0

    def now(self):
        from src.domain.instants import add_seconds
        from src.dto import ClockReadDTO

        return Ok(
            ClockReadDTO(
                read_id="clk-0000000000000001",
                instant=add_seconds(T0, self.seconds),
                source="clock",
            )
        )

    def advance(self, *, seconds=0, **_):
        self.seconds += seconds


class Proposals:
    def __init__(self, *proposals: ProposalDTO) -> None:
        self.by_id = {p.proposal_id: p for p in proposals}

    def get(self, proposal_id):
        return Ok(self.by_id.get(proposal_id))


def proposal(items, *, state="dispatched", action="cancel_jobs", n=1) -> ProposalDTO:
    snapshot = DryRunSnapshotDTO(
        selector=SelectorDTO(method="jobs_port.select", params={}),
        affected_items=items, snapshot_timestamp=T0,
    )  # fmt: skip
    return ProposalDTO(
        proposal_id=f"prop-{n:016x}", session_id="sess-0000000000000001", state=state,
        action=action, dry_run_snapshot=snapshot, gate_token=TOKEN,
    )  # fmt: skip


def request(p: ProposalDTO, **override) -> ExecutorRequestDTO:
    body = {
        "proposal_id": p.proposal_id, "action": p.action,
        "selector": p.dry_run_snapshot.selector, "gate_token": p.gate_token,
        "dry_run_ref": {"proposal_id": p.proposal_id},
    }  # fmt: skip
    return ExecutorRequestDTO(**{**body, **override})


class Rig:
    def __init__(self, jobs=None, nodes=None, *, p=None) -> None:
        self.jobs = RecordStore(
            jobs if jobs is not None else [job(1), job(2), job(3)], lambda r: r.id
        )
        self.nodes = RecordStore(nodes if nodes is not None else [node(1), node(2)], lambda r: r.id)
        self.clock = Clock()
        keys = ["job#job-1", "job#job-2", "job#job-3"]
        self.p = p or proposal([item(k) for k in keys])
        self.executor = SimExecutor(
            clock=self.clock, stores={"jobs": self.jobs, "nodes": self.nodes},
            proposals=Proposals(self.p),
        )  # fmt: skip

    def statuses(self) -> list[str]:
        return [r.status for r in self.jobs.all()]


def test_it_applies_the_snapshots_items_once_and_reports_them() -> None:
    rig = Rig()
    result = rig.executor.dispatch(request(rig.p)).value
    assert (result.status, result.applied_count, result.source) == ("applied", 3, "executor")
    assert result.applied_records == ["job#job-1", "job#job-2", "job#job-3"]
    assert rig.statuses() == ["cancelled"] * 3
    assert rig.executor.get(rig.p.proposal_id).value == result


def test_it_never_touches_a_record_outside_the_snapshot() -> None:
    rig = Rig(jobs=[job(1), job(2), job(3), job(4)])  # job-4 matches nothing in the snapshot
    rig.executor.dispatch(request(rig.p))
    assert rig.statuses() == ["cancelled", "cancelled", "cancelled", "running"]


def test_an_identical_retry_returns_the_stored_result_and_a_differing_one_conflicts() -> None:
    rig = Rig()
    first = rig.executor.dispatch(request(rig.p)).value
    assert rig.executor.dispatch(request(rig.p)).value == first
    other = request(rig.p, selector=SelectorDTO(method="jobs_port.select", params={"id": "x"}))
    clash = rig.executor.dispatch(other)
    assert isinstance(clash, Failure) and clash.code == "EXECUTOR_DUPLICATE_APPLY"
    assert rig.statuses() == ["cancelled"] * 3 and rig.executor.calls == 3


def test_an_item_that_changed_is_skipped_and_the_result_is_partial() -> None:
    rig = Rig(jobs=[job(1), job(2, "succeeded"), job(3)])
    result = rig.executor.dispatch(request(rig.p)).value
    assert (result.status, result.applied_records) == ("partial", ["job#job-1", "job#job-3"])
    assert rig.statuses() == ["cancelled", "succeeded", "cancelled"]


def test_the_controls_make_it_partial_failed_slow_or_down() -> None:
    rig = Rig()
    rig.executor.apply_only = 1
    assert rig.executor.dispatch(request(rig.p)).value.status == "partial"
    extra = Rig()
    extra.executor.extra_applied = ["job#job-99"]
    assert extra.executor.dispatch(request(extra.p)).value.status == "failed"
    slow = Rig()
    slow.executor.delay_seconds = 3
    stamped = slow.executor.dispatch(request(slow.p)).value
    assert stamped.timestamp == "2026-10-16T15:00:03.000Z"  # its own read, after the work
    down = Rig()
    down.executor.down = True
    refused = down.executor.dispatch(request(down.p))
    assert isinstance(refused, Failure) and refused.code == "EXECUTOR_UNAVAILABLE"
    assert down.statuses() == ["running"] * 3 and down.executor.calls == 1


def test_it_accepts_only_a_dispatched_proposal_with_its_token() -> None:
    for state in ("dry_run", "confirmed", "executed", "failed"):
        rig = Rig(p=proposal([item("job#job-1")], state=state))
        result = rig.executor.dispatch(request(rig.p))
        assert isinstance(result, Failure) and result.code == "PROPOSAL_STATE_INVALID", state
        assert rig.statuses() == ["running"] * 3
    rig = Rig()
    wrong = rig.executor.dispatch(request(rig.p, gate_token="gt-" + "cd" * 16))
    assert isinstance(wrong, Failure) and wrong.code == "GATE_TOKEN_INVALID"
    ghost = rig.executor.dispatch(
        request(
            rig.p,
            proposal_id="prop-00000000000000ff",
            dry_run_ref={"proposal_id": "prop-00000000000000ff"},
        )
    )
    assert isinstance(ghost, Failure) and ghost.code == "PROPOSAL_NOT_FOUND"
    assert rig.executor.get("prop-00000000000000ff").value is None


@pytest.mark.parametrize(
    ("action", "check"),
    [
        ("delete_jobs", lambda rig: [r.id for r in rig.jobs.all()] == []),
        ("cancel_jobs", lambda rig: rig.statuses() == ["cancelled"] * 3),
    ],
)
def test_the_job_verbs_change_the_jobs_store(action, check) -> None:
    keys = ["job#job-1", "job#job-2", "job#job-3"]
    rig = Rig(p=proposal([item(k, "running") for k in keys], action=action))
    assert rig.executor.dispatch(request(rig.p)).value.status == "applied"
    assert check(rig)


def test_the_node_verbs_change_the_nodes_store() -> None:
    items = [item("node#ws-gpu-01", "available"), item("node#ws-gpu-02", "available")]
    rig = Rig(p=proposal(items, action="drain_node"))
    assert rig.executor.dispatch(request(rig.p)).value.applied_count == 2
    assert [(n.cordoned, n.health) for n in rig.nodes.all()] == [(True, "draining")] * 2


def test_a_key_that_belongs_to_no_store_is_a_typed_failure() -> None:
    rig = Rig(p=proposal([item("user#alex")]))
    result = rig.executor.dispatch(request(rig.p))
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


def test_a_store_that_failed_to_load_is_a_typed_failure() -> None:
    rig = Rig()
    rig.executor._stores = {
        "jobs": Failure("PROVIDER_UNAVAILABLE", observed=("estate",)),
        "nodes": rig.nodes,
    }
    result = rig.executor.dispatch(request(rig.p))
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


def test_a_proposal_store_that_fails_is_a_typed_failure() -> None:
    rig = Rig()
    rig.executor._proposals = type(
        "Down", (), {"get": lambda self, pid: Failure("PROVIDER_UNAVAILABLE")}
    )()
    result = rig.executor.dispatch(request(rig.p))
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert rig.statuses() == ["running"] * 3


def test_a_clock_that_fails_after_the_work_is_a_typed_failure_and_records_nothing() -> None:
    rig = Rig()
    rig.executor._clock = type("Down", (), {"now": lambda self: Failure("CLOCK_UNAVAILABLE")})()
    result = rig.executor.dispatch(request(rig.p))
    assert isinstance(result, Failure) and result.code == "CLOCK_UNAVAILABLE"
    assert rig.executor.get(rig.p.proposal_id).value is None


def test_a_key_the_store_cannot_look_up_is_a_typed_failure() -> None:
    rig = Rig(p=proposal([item("job#" + "x" * 300)]))
    result = rig.executor.dispatch(request(rig.p))
    assert isinstance(result, Failure)
