"""Story 2.3 - the confirmation use case: every branch of P1-P5 and every way it can fail.

A real container's ports, with one collaborator swapped for a double at a time. A rejected or failed
confirmation must leave the proposal in ``dry_run`` and write no audit row (AD-12); only the claim
that wins writes, and it writes the proposal and the audit rows together.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from src.application.audit_writer import AuditWriter
from src.application.confirmation_service import ConfirmationService
from src.application.tool_audit import ToolCallRecorder, audited
from src.bootstrap import build_container
from src.config import Settings
from src.domain.result import Failure, Ok
from src.domain.safety import DestructiveRequest, Target
from src.ports.inbound import DestructiveUseCases, SessionUseCases
from src.ports.outbound import (
    AuditStorePort,
    ClockPort,
    IdGenPort,
    JobsPort,
    NodesPort,
    ProposalStorePort,
    SessionStorePort,
    UnitOfWorkError,
    UnitOfWorkPort,
)

pytestmark = pytest.mark.unit

DOWN = Failure("PROVIDER_UNAVAILABLE", observed=("simulated outage",))
OTHER = "gt-" + "ab" * 16


class FailingSessions:
    def __init__(self, inner, *, missing: bool = False) -> None:
        self._inner, self._missing = inner, missing

    def get(self, session_id):
        return Ok(None) if self._missing else DOWN


class FailingClock:
    def now(self):
        return DOWN


class CountingClock:
    def __init__(self, inner) -> None:
        self._inner, self.reads = inner, 0

    def now(self):
        self.reads += 1
        return self._inner.now()


class FailingProposals:
    """Reads and claims through the real store, except for the one operation that is replaced."""

    def __init__(self, inner, *, get=None, claim=None) -> None:
        self._inner, self._get, self._claim = inner, get, claim

    def get(self, proposal_id):
        return self._get(self._inner, proposal_id) if self._get else self._inner.get(proposal_id)

    def claim(self, proposal_id, gate_token, confirmed_at):
        if self._claim:
            return self._claim(self._inner, proposal_id, gate_token, confirmed_at)
        return self._inner.claim(proposal_id, gate_token, confirmed_at)


class FailingIds:
    def __init__(self, inner: IdGenPort, kind: str) -> None:
        self._inner, self._kind = inner, kind

    def new_id(self, kind: str):
        return DOWN if kind == self._kind else self._inner.new_id(kind)


class FailingAudit:
    def __init__(self, inner: AuditWriter, *, entries: bool = False) -> None:
        self._inner, self._entries = inner, entries

    def entries_for(self, *args):
        return DOWN if self._entries else self._inner.entries_for(*args)

    def write(self, entries):
        return DOWN


class BrokenUnitOfWork:
    @contextmanager
    def atomic(self):
        raise UnitOfWorkError("the writer is closed")
        yield  # pragma: no cover


class Jobs:
    """``select`` counts its calls and answers what it is told; the rest is the real port."""

    def __init__(self, inner: JobsPort, answer=None) -> None:
        self._inner, self._answer, self.calls = inner, answer, 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def select(self, selector):
        self.calls += 1
        return self._answer(self._inner, selector) if self._answer else self._inner.select(selector)


class Rig:
    def __init__(self) -> None:
        self.container = build_container(Settings.from_env({}))
        created = self.container.port(SessionUseCases).create_session("role-operations")
        self.sid = created.value.session_id

    def dry_run(self, verb="cancel_jobs", kind="group", token="CS-101"):
        request = DestructiveRequest(verb, Target(kind, token))
        return (
            self.container.port(DestructiveUseCases)
            .dry_run_request(self.sid, request)
            .value.proposal
        )

    def service(self, **swap) -> ConfirmationService:
        port = self.container.port
        idgen = swap.get("idgen", port(IdGenPort))
        recorder = ToolCallRecorder()

        def audited_port(port_type, adapter, name):
            return audited(port_type, adapter, name=name, recorder=recorder)

        parts = {
            "proposals": port(ProposalStorePort),
            "sessions": port(SessionStorePort),
            "clock": port(ClockPort),
            "idgen": idgen,
            "jobs": port(JobsPort),
            "nodes": port(NodesPort),
            "uow": port(UnitOfWorkPort),
            "audit": AuditWriter(port(AuditStorePort), idgen),
            "recorder": recorder,
            "token_ttl_seconds": 60,
        }
        parts.update(swap)
        parts["jobs"] = audited_port(JobsPort, parts["jobs"], "jobs_port")
        parts["nodes"] = audited_port(NodesPort, parts["nodes"], "nodes_port")
        return ConfirmationService(**parts)

    def state(self, proposal_id: str) -> str:
        return self.container.port(ProposalStorePort).get(proposal_id).value.state

    def audit_rows(self) -> int:
        with self.container.port(UnitOfWorkPort).read() as db:
            return db.execute("SELECT COUNT(*) FROM audit_records").fetchone()[0]


@pytest.fixture()
def rig():
    rig = Rig()
    yield rig
    rig.container.close()


def code(result) -> str:
    assert isinstance(result, Failure), result
    return result.code


# -- the control and P1 ---------------------------------------------------------------------------
def test_a_fresh_proposal_is_confirmed_once_with_its_caption_and_its_audit(rig: Rig) -> None:
    proposal = rig.dry_run()
    rows_before = rig.audit_rows()
    result = rig.service().post_confirm(proposal.proposal_id, proposal.gate_token)
    confirmed = result.value
    assert confirmed.state == "confirmed" and confirmed.confirmation.confirmed_at.endswith("Z")
    assert confirmed.confirmation.caption.startswith("This confirms a proposal for delegation.")
    assert rig.state(proposal.proposal_id) == "confirmed"
    assert rig.audit_rows() == rows_before + 2  # the head and the re-validation read


def test_an_unknown_proposal_is_not_found_and_reads_no_clock(rig: Rig) -> None:
    clock = CountingClock(rig.container.port(ClockPort))
    result = rig.service(clock=clock).post_confirm("prop-00000000000000ff", OTHER)
    assert code(result) == "PROPOSAL_NOT_FOUND" and clock.reads == 0


# -- P5: a proposal that is not in dry_run --------------------------------------------------------
def test_an_identical_replay_is_the_persisted_proposal_and_a_different_token_conflicts(
    rig: Rig,
) -> None:
    proposal = rig.dry_run()
    service = rig.service()
    first = service.post_confirm(proposal.proposal_id, proposal.gate_token)
    rows = rig.audit_rows()
    assert service.post_confirm(proposal.proposal_id, proposal.gate_token) == first
    assert code(service.post_confirm(proposal.proposal_id, OTHER)) == "CONFIRMATION_CONFLICT"
    assert rig.audit_rows() == rows


def test_a_replay_after_the_lifetime_is_still_the_persisted_proposal(rig: Rig) -> None:
    proposal = rig.dry_run()
    service = rig.service()
    first = service.post_confirm(proposal.proposal_id, proposal.gate_token)
    rig.container.port(ClockPort).advance(seconds=3600)
    assert service.post_confirm(proposal.proposal_id, proposal.gate_token) == first


def test_a_refused_proposal_is_a_state_error(rig: Rig) -> None:
    proposal = rig.dry_run()
    with rig.container.port(UnitOfWorkPort).transaction() as db:
        db.execute("DROP TRIGGER trg_proposals_state_machine")  # to plant a state nothing creates
        db.execute(
            "UPDATE proposals SET state = 'refused' WHERE proposal_id = ?", (proposal.proposal_id,)
        )
    assert code(rig.service().post_confirm(proposal.proposal_id, proposal.gate_token)) == (
        "PROPOSAL_STATE_INVALID"
    )


# -- P2 and P4 ------------------------------------------------------------------------------------
def test_a_wrong_token_is_forbidden_and_an_expired_one_is_stale(rig: Rig) -> None:
    proposal = rig.dry_run()
    service = rig.service()
    assert code(service.post_confirm(proposal.proposal_id, OTHER)) == "GATE_TOKEN_INVALID"
    rig.container.port(ClockPort).advance(seconds=60.001)
    stale = service.post_confirm(proposal.proposal_id, proposal.gate_token)
    assert code(stale) == "CONFIRMATION_STALE"
    assert stale.observed == ("token expired: 60.001 s after the snapshot, lifetime 60 s",)
    assert rig.state(proposal.proposal_id) == "dry_run"


def test_nothing_actionable_is_refused_before_any_provider_read(rig: Rig) -> None:
    proposal = rig.dry_run(kind="job", token="job-8801")  # a cancelled job: listed, not actionable
    jobs = Jobs(rig.container.port(JobsPort))
    result = rig.service(jobs=jobs).post_confirm(proposal.proposal_id, proposal.gate_token)
    assert code(result) == "DRY_RUN_EMPTY_SET" and jobs.calls == 0


# -- P3 -------------------------------------------------------------------------------------------
def test_a_changed_set_is_stale_with_the_delta_in_the_message_and_the_lines(rig: Rig) -> None:
    proposal = rig.dry_run()
    jobs = Jobs(rig.container.port(JobsPort), lambda inner, sel: Ok(inner.select(sel).value[1:]))
    result = rig.service(jobs=jobs).post_confirm(proposal.proposal_id, proposal.gate_token)
    assert code(result) == "CONFIRMATION_STALE"
    assert result.message == "Snapshot stale: removed job#job-8901."
    assert result.observed == ("removed job#job-8901", "confirmation disabled: run a new dry-run")
    assert rig.state(proposal.proposal_id) == "dry_run"


def test_a_provider_outage_during_revalidation_is_a_failure_and_writes_nothing(rig: Rig) -> None:
    proposal = rig.dry_run()
    rows = rig.audit_rows()
    jobs = Jobs(rig.container.port(JobsPort), lambda inner, sel: DOWN)
    result = rig.service(jobs=jobs).post_confirm(proposal.proposal_id, proposal.gate_token)
    assert code(result) == "PROVIDER_UNAVAILABLE"
    assert rig.state(proposal.proposal_id) == "dry_run" and rig.audit_rows() == rows


def test_a_node_proposal_is_revalidated_through_the_nodes_port(rig: Rig) -> None:
    proposal = rig.dry_run("cordon_node", "node", "ws-gpu-02")
    result = rig.service().post_confirm(proposal.proposal_id, proposal.gate_token)
    assert result.value.state == "confirmed"


def test_a_stored_selector_that_names_no_port_is_a_failure(rig: Rig) -> None:
    proposal = rig.dry_run()
    corrupted = proposal.model_copy(
        update={
            "dry_run_snapshot": proposal.dry_run_snapshot.model_copy(
                update={
                    "selector": proposal.dry_run_snapshot.selector.model_copy(
                        update={"method": "x"}
                    )
                }
            )
        }
    )
    store = FailingProposals(
        rig.container.port(ProposalStorePort), get=lambda inner, pid: Ok(corrupted)
    )
    assert code(
        rig.service(proposals=store).post_confirm(proposal.proposal_id, proposal.gate_token)
    ) == ("PROVIDER_UNAVAILABLE")


# -- the claim and its failures -------------------------------------------------------------------
def swaps(r: Rig) -> dict[str, dict]:
    port = r.container.port
    writer = AuditWriter(port(AuditStorePort), port(IdGenPort))
    proposals = port(ProposalStorePort)
    return {
        "get": {"proposals": FailingProposals(proposals, get=lambda inner, pid: DOWN)},
        "clock": {"clock": FailingClock()},
        "sessions": {"sessions": FailingSessions(port(SessionStorePort))},
        "session-gone": {"sessions": FailingSessions(port(SessionStorePort), missing=True)},
        "tool-call-id": {"idgen": FailingIds(port(IdGenPort), "tool_call")},
        "audit-id": {"idgen": FailingIds(port(IdGenPort), "audit")},
        "entries": {"audit": FailingAudit(writer, entries=True)},
        "audit-write": {"audit": FailingAudit(writer)},
        "claim": {"proposals": FailingProposals(proposals, claim=lambda i, p, t, c: DOWN)},
        "uow": {"uow": BrokenUnitOfWork()},
    }


COLLABORATORS = [
    "get", "clock", "sessions", "session-gone", "tool-call-id", "audit-id", "entries",
    "audit-write", "claim", "uow",
]  # fmt: skip


@pytest.mark.parametrize("name", COLLABORATORS)
def test_a_failing_collaborator_is_a_typed_failure_and_the_proposal_stays_in_dry_run(
    rig: Rig, name: str
) -> None:
    proposal = rig.dry_run()
    rows = rig.audit_rows()
    result = rig.service(**swaps(rig)[name]).post_confirm(proposal.proposal_id, proposal.gate_token)
    assert isinstance(result, Failure), name
    assert rig.state(proposal.proposal_id) == "dry_run" and rig.audit_rows() == rows


def test_a_claim_that_keeps_losing_without_a_confirmation_is_a_failure_not_a_loop(rig: Rig) -> None:
    proposal = rig.dry_run()
    store = FailingProposals(
        rig.container.port(ProposalStorePort), claim=lambda inner, pid, token, at: Ok(False)
    )
    result = rig.service(proposals=store).post_confirm(proposal.proposal_id, proposal.gate_token)
    assert code(result) == "PROVIDER_UNAVAILABLE"
    assert rig.state(proposal.proposal_id) == "dry_run"


# -- review P-1: a rejected attempt leaves a trace in the log, never the token --------------------
LOGGER = "src.application.confirmation_service"


@pytest.mark.parametrize(
    ("make", "expected"),
    [
        (lambda p: (p.proposal_id, OTHER), "GATE_TOKEN_INVALID"),
        (lambda p: ("prop-00000000000000ff", OTHER), "PROPOSAL_NOT_FOUND"),
    ],
    ids=["wrong-token", "unknown-proposal"],
)
def test_a_rejected_confirmation_logs_its_id_and_code_and_never_a_token(
    rig: Rig, caplog: pytest.LogCaptureFixture, make, expected: str
) -> None:
    proposal = rig.dry_run()
    pid, token = make(proposal)
    with caplog.at_level("WARNING", logger=LOGGER):
        assert code(rig.service().post_confirm(pid, token)) == expected
    [record] = [r for r in caplog.records if r.name == LOGGER]
    assert record.levelname == "WARNING"
    assert pid in record.getMessage() and expected in record.getMessage()
    assert proposal.gate_token not in caplog.text and token not in caplog.text


def test_every_rejection_code_is_logged_and_a_success_or_a_replay_is_not(
    rig: Rig, caplog: pytest.LogCaptureFixture
) -> None:
    proposal = rig.dry_run()
    service = rig.service()
    with caplog.at_level("WARNING", logger=LOGGER):
        service.post_confirm(proposal.proposal_id, proposal.gate_token)  # success
        service.post_confirm(proposal.proposal_id, proposal.gate_token)  # replay
        assert [r for r in caplog.records if r.name == LOGGER] == []
        service.post_confirm(proposal.proposal_id, OTHER)  # conflict
    assert "CONFIRMATION_CONFLICT" in caplog.text


def test_a_rejected_id_with_control_characters_cannot_forge_a_log_line(
    rig: Rig, caplog: pytest.LogCaptureFixture
) -> None:
    forged = "prop-x\nWARNING forged line code=NOTHING"
    with caplog.at_level("WARNING", logger=LOGGER):
        rig.service().post_confirm(forged, OTHER)
    message = caplog.records[-1].getMessage()
    assert "\n" not in message and "\\n" in message  # the newline is escaped, not written


def test_a_provider_failure_is_not_logged_as_a_rejection(
    rig: Rig, caplog: pytest.LogCaptureFixture
) -> None:
    proposal = rig.dry_run()
    jobs = Jobs(rig.container.port(JobsPort), lambda inner, sel: DOWN)
    with caplog.at_level("WARNING", logger=LOGGER):
        rig.service(jobs=jobs).post_confirm(proposal.proposal_id, proposal.gate_token)
    assert [r for r in caplog.records if r.name == LOGGER] == []
