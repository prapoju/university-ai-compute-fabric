"""The provider reads behind the access-denial diagnosis (AD-1 read-only, AD-12 all-or-nothing)."""

from __future__ import annotations

import pytest

from src.application.evidence_assembler import EvidenceAssembler
from src.application.parallel_reads import ParallelReads
from src.application.tool_audit import ToolCallRecorder, audited
from src.domain.result import Failure, is_ok
from src.dto import ClockReadDTO
from src.ports.outbound import EventStorePort, PolicyPort

pytestmark = pytest.mark.unit


def clock_at(instant: str) -> ClockReadDTO:
    return ClockReadDTO(read_id="clk-0000000000000001", instant=instant, source="clock")


def gather(providers, instant: str = "2026-10-16T15:00:00.000Z", user="user#alex"):
    assembler = EvidenceAssembler(policy=providers.policy, events=providers.event_store)
    users = providers.users.get(user)
    model = providers.catalog.get("model#deepseek-coder")
    assert is_ok(users) and is_ok(model)
    return assembler.gather(users.value, model.value, clock_at(instant))


def test_it_reads_the_models_clauses_and_the_users_denial_events(providers) -> None:
    result = gather(providers)
    assert is_ok(result)
    assert [c.clause_id for c in result.value.clauses] == ["policy#catalog.4.2"]
    assert [e.event_id for e in result.value.events] == ["event#evt-4711"]


def test_the_look_back_is_thirty_days_and_an_event_stamped_now_is_included(providers) -> None:
    # evt-4711 is stamped 2026-10-16T13:42:10Z: inside 30 days of the 16th, outside of Nov 20th
    assert gather(providers, "2026-10-16T15:00:00.000Z").value.events
    assert gather(providers, "2026-11-20T15:00:00.000Z").value.events == ()
    exactly = gather(providers, "2026-10-16T13:42:10.000Z")  # now == the event's own timestamp
    assert [e.event_id for e in exactly.value.events] == ["event#evt-4711"]


DOWN = Failure("PROVIDER_UNAVAILABLE", observed=("injected outage",))


class _PolicyDown(PolicyPort):
    def get(self, clause_id):
        return DOWN

    def for_model(self, model_id):
        return DOWN

    def browse(self, q, page, page_size):
        return DOWN


class _RecordingEvents(EventStorePort):
    def __init__(self, real: EventStorePort) -> None:
        self._real, self.calls = real, []

    def query(self, entity_ref, type, window):
        self.calls.append((entity_ref, type, window))
        return self._real.query(entity_ref, type, window)

    def get(self, event_id):
        return self._real.get(event_id)

    def browse(self, q, page, page_size):
        return self._real.browse(q, page, page_size)


def test_a_policy_outage_fails_the_turn_with_the_policy_failure_and_no_event_evidence(
    providers,
) -> None:
    """AD-12 under parallel reads (story 1.6): the events may be read alongside the policy, but a
    failed read fails the whole turn with the policy's own failure, and no event evidence reaches
    the returned result or the recorded tool calls."""
    events = _RecordingEvents(providers.event_store)
    recorder = ToolCallRecorder()
    assembler = EvidenceAssembler(
        policy=audited(PolicyPort, _PolicyDown(), name="policy_port", recorder=recorder),
        events=audited(EventStorePort, events, name="event_store_port", recorder=recorder),
        reads=ParallelReads(recorder=recorder),
    )
    user = providers.users.get("user#alex").value
    model = providers.catalog.get("model#deepseek-coder").value
    with recorder.turn() as calls:
        result = assembler.gather(user, model, clock_at("2026-10-16T15:00:00.000Z"))
    assert result == DOWN  # the policy's own failure, not the event-window one (same code)
    assert not is_ok(result)
    assert len(events.calls) <= 1, "events may be read at most once in the fan-out"
    assert "evt-4711" not in repr(calls), "event evidence reached the recorded tool calls"


@pytest.mark.parametrize("instant", ["0001-01-10T00:00:00.000Z", "9999-12-31T23:59:59.999Z"])
def test_an_extreme_clock_instant_is_a_typed_failure_not_an_exception(
    providers, instant: str
) -> None:
    result = gather(providers, instant)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
