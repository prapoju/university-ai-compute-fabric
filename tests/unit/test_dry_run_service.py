"""Story 2.2 - every way the dry-run can fail leaves nothing behind (AD-12, IR-03).

Each collaborator is replaced, one at a time, by a double that fails; the use case must answer the
typed failure and must not insert a proposal or an audit row.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from src.application.audit_writer import AuditWriter
from src.application.dry_run_service import DryRunService
from src.application.entity_resolver import EntityResolver
from src.application.tool_audit import ToolCallRecorder
from src.bootstrap import build_container
from src.config import Settings
from src.domain.result import Failure, Ok
from src.domain.safety import DestructiveRequest, Target
from src.ports.inbound import SessionUseCases
from src.ports.outbound import (
    AuditStorePort,
    CatalogPort,
    ClockPort,
    GroupsPort,
    IdGenPort,
    JobsPort,
    NodesPort,
    ProposalStorePort,
    SessionStorePort,
    UnitOfWorkError,
    UnitOfWorkPort,
    UsersPort,
)

pytestmark = pytest.mark.unit

DOWN = Failure("PROVIDER_UNAVAILABLE", observed=("simulated outage",))
REQUEST = DestructiveRequest("cancel_jobs", Target("group", "CS-101"))


class FailingSessions:
    def __init__(self, inner: SessionStorePort) -> None:
        self._inner = inner

    def get(self, session_id: str):
        return DOWN


class FailingClock:
    def now(self):
        return DOWN


class FailingIds:
    def __init__(self, inner: IdGenPort, kind: str) -> None:
        self._inner, self._kind = inner, kind

    def new_id(self, kind: str):
        return DOWN if kind == self._kind else self._inner.new_id(kind)


class FailingProposals:
    def add(self, proposal, created_at):
        return DOWN


class FailingAudit:
    def __init__(self, inner: AuditWriter, *, entries: bool = False) -> None:
        self._inner, self._entries = inner, entries

    def entries_for(self, *args):
        return DOWN if self._entries else self._inner.entries_for(*args)

    def write(self, entries):
        return DOWN


class FailingResolver:
    def resolve_target(self, kind, token):
        return DOWN


class BrokenUnitOfWork:
    @contextmanager
    def atomic(self):
        raise UnitOfWorkError("the writer is closed")
        yield  # pragma: no cover


class Rig:
    """A real container's ports, with one collaborator swapped for a failing double."""

    def __init__(self) -> None:
        self.container = build_container(Settings.from_env({}))
        self.sid = (
            self.container.port(SessionUseCases).create_session("role-operations").value.session_id
        )

    def service(self, **swap) -> DryRunService:
        port = self.container.port
        idgen = port(IdGenPort)
        parts = {
            "sessions": port(SessionStorePort),
            "proposals": port(ProposalStorePort),
            "clock": port(ClockPort),
            "idgen": idgen,
            "resolver": EntityResolver(
                users=port(UsersPort), catalog=port(CatalogPort), groups=port(GroupsPort),
                nodes=port(NodesPort), jobs=port(JobsPort),
            ),
            "jobs": port(JobsPort),
            "nodes": port(NodesPort),
            "uow": port(UnitOfWorkPort),
            "audit": AuditWriter(port(AuditStorePort), idgen),
            "recorder": ToolCallRecorder(),
            "token_ttl_seconds": 60,
        }  # fmt: skip
        return DryRunService(**{**parts, **swap})

    def rows(self) -> int:
        with self.container.port(UnitOfWorkPort).read() as db:
            return db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]

    def audit_rows(self) -> int:
        with self.container.port(UnitOfWorkPort).read() as db:
            return db.execute("SELECT COUNT(*) FROM audit_records").fetchone()[0]


@pytest.fixture()
def rig():
    rig = Rig()
    yield rig
    rig.container.close()


def test_the_healthy_service_is_the_control(rig: Rig) -> None:
    outcome = rig.service().dry_run_request(rig.sid, REQUEST)
    assert isinstance(outcome, Ok) and rig.rows() == 1


@pytest.mark.parametrize(
    "swap",
    [
        lambda r: {"sessions": FailingSessions(r.container.port(SessionStorePort))},
        lambda r: {"clock": FailingClock()},
        lambda r: {"resolver": FailingResolver()},
        lambda r: {"idgen": FailingIds(r.container.port(IdGenPort), "proposal")},
        lambda r: {"idgen": FailingIds(r.container.port(IdGenPort), "gate_token")},
        lambda r: {"proposals": FailingProposals()},
        lambda r: {"uow": BrokenUnitOfWork()},
    ],
    ids=["session-store", "clock", "resolver", "proposal-id", "token", "proposal-insert", "uow"],
)
def test_a_failing_collaborator_is_a_typed_failure_and_writes_nothing(rig: Rig, swap) -> None:
    result = rig.service(**swap(rig)).dry_run_request(rig.sid, REQUEST)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert rig.rows() == 0 and rig.audit_rows() == 0


def test_a_failure_minting_the_audit_ids_writes_nothing(rig: Rig) -> None:
    audit = FailingAudit(
        AuditWriter(rig.container.port(AuditStorePort), rig.container.port(IdGenPort)), entries=True
    )
    result = rig.service(audit=audit).dry_run_request(rig.sid, REQUEST)
    assert isinstance(result, Failure) and rig.rows() == 0


def test_a_failing_audit_write_rolls_the_proposal_back(rig: Rig) -> None:
    audit = FailingAudit(
        AuditWriter(rig.container.port(AuditStorePort), rig.container.port(IdGenPort))
    )
    result = rig.service(audit=audit).dry_run_request(rig.sid, REQUEST)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert rig.rows() == 0 and rig.audit_rows() == 0  # the insert joined the unit of work


def test_a_resolver_failure_on_a_bare_ref_is_a_typed_failure(rig: Rig) -> None:
    result = rig.service(resolver=FailingResolver()).post_dry_run(
        "cancel", "cancel_jobs", ["CS-101"], rig.sid
    )
    assert isinstance(result, Failure) and rig.rows() == 0


def test_an_unknown_action_is_malformed_before_anything_is_read(rig: Rig) -> None:
    result = rig.service(
        sessions=FailingSessions(rig.container.port(SessionStorePort))
    ).post_dry_run("cancel", "nuke_jobs", ["CS-101"], rig.sid)
    assert isinstance(result, Failure) and result.code == "VALIDATION_MALFORMED_BODY"
