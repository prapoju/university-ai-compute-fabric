"""Story 2.4 - the dispatcher: one executor call, the 5 s rule, classification and recording.

A real container's ports and executor, with one collaborator swapped for a double at a time. A
proposal is walked to ``dispatched`` the way the confirmation leaves it, then handed to the
dispatcher.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from src.application.audit_writer import AuditWriter
from src.application.proposal_dispatcher import ProposalDispatcher
from src.bootstrap import build_container
from src.config import Settings
from src.domain.result import Failure, Ok
from src.domain.safety import DestructiveRequest, Target
from src.dto import ExecutorResultDTO
from src.ports.inbound import DestructiveUseCases, SessionUseCases
from src.ports.outbound import (
    AuditStorePort,
    ClockPort,
    ExecutorPort,
    IdGenPort,
    ProposalStorePort,
    SessionStorePort,
    UnitOfWorkError,
    UnitOfWorkPort,
)

pytestmark = pytest.mark.unit

DOWN = Failure("PROVIDER_UNAVAILABLE", observed=("simulated outage",))
KEYS = ["job#job-8901", "job#job-8902", "job#job-8903"]


class Executor:
    """The real simulated executor, with one answer replaced when told."""

    def __init__(self, inner, answer=None) -> None:
        self._inner, self._answer, self.calls = inner, answer, 0

    def dispatch(self, request):
        self.calls += 1
        real = self._inner.dispatch(request)
        return self._answer(real) if self._answer else real

    def get(self, proposal_id):
        return self._inner.get(proposal_id)


class FailingClock:
    def __init__(self, inner, *, fail_on: int) -> None:
        self._inner, self._fail_on, self._reads = inner, fail_on, 0

    def now(self):
        self._reads += 1
        return DOWN if self._reads == self._fail_on else self._inner.now()


class Proposals:
    def __init__(self, inner, *, record=None) -> None:
        self._inner, self._record = inner, record

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def record_result(self, *args):
        return self._record(*args) if self._record else self._inner.record_result(*args)


class FailingAudit:
    def __init__(self, inner: AuditWriter, *, entry: bool = False) -> None:
        self._inner, self._entry = inner, entry

    def executor_entry(self, *args):
        return DOWN if self._entry else self._inner.executor_entry(*args)

    def write(self, entries):
        return DOWN


class BrokenUnitOfWork:
    @contextmanager
    def atomic(self):
        raise UnitOfWorkError("the writer is closed")
        yield  # pragma: no cover


class Rig:
    def __init__(self) -> None:
        self.container = build_container(Settings.from_env({}))
        port = self.container.port
        created = port(SessionUseCases).create_session("role-operations")
        self.sid = created.value.session_id
        request = DestructiveRequest("cancel_jobs", Target("group", "CS-101"))
        stored = port(DestructiveUseCases).dry_run_request(self.sid, request).value.proposal
        at = "2026-10-16T15:00:00.000Z"
        assert port(ProposalStorePort).claim(stored.proposal_id, stored.gate_token, at).value
        assert port(ProposalStorePort).begin_dispatch(stored.proposal_id, at).value
        self.proposal = port(ProposalStorePort).get(stored.proposal_id).value
        self.session = port(SessionStorePort).get(self.sid).value.session

    def dispatcher(self, **swap) -> ProposalDispatcher:
        port = self.container.port
        parts = {
            "proposals": port(ProposalStorePort),
            "executor": port(ExecutorPort),
            "clock": port(ClockPort),
            "uow": port(UnitOfWorkPort),
            "audit": AuditWriter(port(AuditStorePort), port(IdGenPort)),
        }
        return ProposalDispatcher(**{**parts, **swap})

    def stored(self):
        return self.container.port(ProposalStorePort).get(self.proposal.proposal_id).value

    def rows(self, actor: str = "executor") -> int:
        with self.container.port(UnitOfWorkPort).read() as db:
            sql = "SELECT COUNT(*) FROM audit_records WHERE actor = ?"
            return db.execute(sql, (actor,)).fetchone()[0]


@pytest.fixture()
def rig():
    rig = Rig()
    yield rig
    rig.container.close()


def code(result) -> str:
    assert isinstance(result, Failure), result
    return result.code


def test_a_full_apply_is_executed_with_the_result_and_one_executor_row(rig: Rig) -> None:
    done = rig.dispatcher().dispatch(rig.proposal, rig.session).value
    assert done.state == "executed"
    assert (done.executor_result.status, done.executor_result.applied_records) == ("applied", KEYS)
    assert rig.stored() == done  # what was answered is what was stored
    assert rig.rows() == 1


def test_the_executor_is_called_exactly_once(rig: Rig) -> None:
    executor = Executor(rig.container.port(ExecutorPort))
    rig.dispatcher(executor=executor).dispatch(rig.proposal, rig.session)
    assert executor.calls == 1


def test_the_request_the_executor_gets_is_the_frozen_one_from_the_stored_row(rig: Rig) -> None:
    rig.dispatcher().dispatch(rig.proposal, rig.session)
    [sent] = rig.container.port(ExecutorPort).requests
    assert set(sent.model_dump()) == {
        "proposal_id", "action", "selector", "gate_token", "dry_run_ref",
    }  # fmt: skip
    assert sent.selector == rig.proposal.dry_run_snapshot.selector
    assert sent.gate_token == rig.proposal.gate_token


@pytest.mark.parametrize(
    ("setup", "status"),
    [("apply_only", "partial"), ("extra_applied", "failed")],
    ids=["fewer-than-the-scope", "more-than-the-scope"],
)
def test_anything_but_the_exact_scope_is_a_failed_proposal_with_the_real_records(
    rig: Rig, setup: str, status: str
) -> None:
    executor = rig.container.port(ExecutorPort)
    setattr(executor, setup, 2 if setup == "apply_only" else ["job#job-9999"])
    done = rig.dispatcher().dispatch(rig.proposal, rig.session).value
    assert done.state == "failed" and done.executor_result.status == status
    assert rig.stored().state == "failed" and rig.rows() == 1


def test_an_executor_that_says_applied_but_miscounts_is_not_a_success(rig: Rig) -> None:
    def liar(real):
        return Ok(real.value.model_copy(update={"applied_count": 99}))

    executor = Executor(rig.container.port(ExecutorPort), liar)
    done = rig.dispatcher(executor=executor).dispatch(rig.proposal, rig.session).value
    assert done.state == "failed" and done.executor_result.status == "partial"


@pytest.mark.parametrize(
    ("delay", "state"), [(4.999, "executed"), (5.0, "executed"), (5.001, "failed")]
)
def test_the_five_seconds_are_measured_on_the_clock(rig: Rig, delay: float, state: str) -> None:
    rig.container.port(ExecutorPort).delay_seconds = delay
    result = rig.dispatcher().dispatch(rig.proposal, rig.session)
    if state == "executed":
        assert result.value.state == "executed"
    else:
        assert code(result) == "EXECUTOR_UNAVAILABLE"
        assert rig.stored().state == "failed" and rig.stored().executor_result is None
        assert rig.rows() == 0  # it did not answer in time: no executor row
        assert rig.container.port(ExecutorPort).get(rig.proposal.proposal_id).value is not None


def test_a_down_executor_fails_the_proposal_and_is_called_once(rig: Rig) -> None:
    executor = rig.container.port(ExecutorPort)
    executor.down = True
    result = rig.dispatcher().dispatch(rig.proposal, rig.session)
    assert code(result) == "EXECUTOR_UNAVAILABLE" and executor.calls == 1
    assert rig.stored().state == "failed" and rig.rows() == 0


def test_another_typed_refusal_of_the_executor_also_fails_the_proposal(rig: Rig) -> None:
    refuse = Executor(
        rig.container.port(ExecutorPort), lambda real: Failure("GATE_TOKEN_INVALID", message="x")
    )
    result = rig.dispatcher(executor=refuse).dispatch(rig.proposal, rig.session)
    assert code(result) == "GATE_TOKEN_INVALID" and rig.stored().state == "failed"


def test_a_failing_audit_write_leaves_the_proposal_dispatched_never_executed(rig: Rig) -> None:
    audit = FailingAudit(
        AuditWriter(rig.container.port(AuditStorePort), rig.container.port(IdGenPort))
    )
    result = rig.dispatcher(audit=audit).dispatch(rig.proposal, rig.session)
    assert isinstance(result, Failure)
    assert rig.stored().state == "dispatched" and rig.stored().executor_result is None
    assert rig.rows() == 0


@pytest.mark.parametrize(
    "name", ["entry", "uow", "record", "lost", "clock-start", "clock-end", "mark-failed"]
)
def test_a_failing_collaborator_is_a_typed_failure(rig: Rig, name: str) -> None:
    port = rig.container.port
    proposals = port(ProposalStorePort)
    swaps = {
        "entry": {
            "audit": FailingAudit(AuditWriter(port(AuditStorePort), port(IdGenPort)), entry=True)
        },
        "uow": {"uow": BrokenUnitOfWork()},
        "record": {"proposals": Proposals(proposals, record=lambda *a: DOWN)},
        "lost": {"proposals": Proposals(proposals, record=lambda *a: Ok(False))},
        "clock-start": {"clock": FailingClock(port(ClockPort), fail_on=1)},
        "clock-end": {"clock": FailingClock(port(ClockPort), fail_on=2)},
    }
    if name == "mark-failed":
        port(ExecutorPort).down = True
        swaps["mark-failed"] = {"uow": BrokenUnitOfWork()}
    result = rig.dispatcher(**swaps[name]).dispatch(rig.proposal, rig.session)
    assert isinstance(result, Failure), name
    assert rig.stored().state in {"dispatched", "failed"} and rig.stored().state != "executed"


def test_the_result_the_executor_reports_late_is_never_recorded_on_the_proposal() -> None:
    rig = Rig()
    try:
        rig.container.port(ExecutorPort).delay_seconds = 6
        rig.dispatcher().dispatch(rig.proposal, rig.session)
        late = rig.container.port(ExecutorPort).get(rig.proposal.proposal_id).value
        assert isinstance(late, ExecutorResultDTO) and late.status == "applied"
        assert rig.stored().state == "failed" and rig.stored().executor_result is None
    finally:
        rig.container.close()
