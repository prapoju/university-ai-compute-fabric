"""The generic port wrapper and the turn-scoped recorder (FR-11, Q-port-3, story 1.5 D3, D4)."""

from __future__ import annotations

import threading

import pytest

from src.adapters.outbound.sim.fixtures_adapter import SimProviders
from src.application.tool_audit import (
    TOOL_PORT_NAMES,
    RecordedCall,
    ToolCallRecorder,
    audited,
)
from src.config import PROJECT_ROOT
from src.domain.result import Failure, Ok
from src.dto import SelectorDTO
from src.ports.outbound import (
    ClockPort,
    EventStorePort,
    EventWindow,
    IdGenPort,
    JobsPort,
    LlmProsePort,
    PolicyContentPort,
    SessionStorePort,
    UsersPort,
    WindowsPort,
)

pytestmark = pytest.mark.unit

START = "2026-10-16T15:00:00.000Z"


@pytest.fixture(scope="module")
def providers() -> SimProviders:
    return SimProviders.from_fixtures(PROJECT_ROOT / "fixtures", START)


def wrap(port_type, adapter, recorder: ToolCallRecorder):
    return audited(port_type, adapter, name=TOOL_PORT_NAMES[port_type], recorder=recorder)


class _FailingUsers(UsersPort):
    def get(self, id):
        return Failure("PROVIDER_UNAVAILABLE", observed=("users down",))

    def browse(self, q, page, page_size):
        return Ok([])

    def by_ids(self, ids):
        return Ok([])


def test_the_wrapper_is_an_instance_of_the_port_and_returns_the_adapter_result(providers) -> None:
    recorder = ToolCallRecorder()
    users = wrap(UsersPort, providers.users, recorder)
    assert isinstance(users, UsersPort)
    assert type(users).__name__ == "AuditedUsersPort"
    assert users.get("user#alex") == providers.users.get("user#alex")
    assert users.browse("", 1, 3) == providers.users.browse("", 1, 3)


def test_every_tool_port_wraps_without_new_code(providers) -> None:
    recorder = ToolCallRecorder()
    raw = providers.as_ports()
    for port_type in TOOL_PORT_NAMES:
        wrapped = wrap(port_type, raw[port_type], recorder)
        assert isinstance(wrapped, port_type)
        assert set(port_type.__abstractmethods__) <= set(vars(type(wrapped)))


def test_inside_a_turn_each_call_is_recorded_with_name_params_status_and_count(
    providers,
) -> None:
    recorder = ToolCallRecorder()
    users = wrap(UsersPort, providers.users, recorder)
    jobs = wrap(JobsPort, providers.jobs, recorder)
    events = wrap(EventStorePort, providers.event_store, recorder)
    windows = wrap(WindowsPort, providers.windows, recorder)
    window = EventWindow(start="2026-09-16T15:00:00.000Z", end=START)
    selector = SelectorDTO(method="filter", params={"group_id": "group#group-4"})
    with recorder.turn() as calls:
        users.get("user#alex")
        users.get(id="user#ghost")
        jobs.select(selector)
        events.query("user#alex", "access_denied", window=window)
        windows.list()
    assert calls == [
        RecordedCall("toolcall.users_port.get", {"id": "user#alex"}, "ok", result_count=1),
        RecordedCall("toolcall.users_port.get", {"id": "user#ghost"}, "ok", result_count=0),
        RecordedCall(
            "toolcall.jobs_port.select",
            {"selector": {"method": "filter", "params": {"group_id": "group#group-4"}}},
            "ok",
            result_count=len(providers.jobs.select(selector).value),
        ),
        RecordedCall(
            "toolcall.event_store_port.query",
            {"entity_ref": "user#alex", "type": "access_denied",
             "window": {"start": "2026-09-16T15:00:00.000Z", "end": START}},
            "ok",
            result_count=1,
        ),  # fmt: skip
        RecordedCall(
            "toolcall.windows_port.list", {}, "ok",
            result_count=len(providers.windows.list().value),
        ),  # fmt: skip
    ]


def test_a_failure_is_recorded_with_its_code_and_no_count() -> None:
    recorder = ToolCallRecorder()
    users = wrap(UsersPort, _FailingUsers(), recorder)
    with recorder.turn() as calls:
        result = users.get("user#alex")
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert calls == [
        RecordedCall(
            "toolcall.users_port.get", {"id": "user#alex"}, "failure",
            error_code="PROVIDER_UNAVAILABLE",
        )
    ]  # fmt: skip


def test_a_non_optional_non_list_result_has_no_count(providers) -> None:
    recorder = ToolCallRecorder()
    content = wrap(PolicyContentPort, providers.policy_content, recorder)
    with recorder.turn() as calls:
        result = content.get("policy#catalog.4.2")
    assert calls[0].tool_name == "toolcall.policy_content_port.get"
    assert calls[0].status == ("ok" if isinstance(result, Ok) else "failure")
    assert calls[0].result_count is None


def test_nothing_is_recorded_outside_a_turn(providers) -> None:
    recorder = ToolCallRecorder()
    users = wrap(UsersPort, providers.users, recorder)
    users.get("user#alex")  # e.g. the evidence or state routes (D2)
    with recorder.turn() as calls:
        pass
    assert calls == []
    with recorder.turn() as calls:
        users.get("user#alex")
    users.get("user#alex")  # after the turn ended
    assert len(calls) == 1


def test_a_nested_turn_does_not_leak_into_the_outer_one(providers) -> None:
    recorder = ToolCallRecorder()
    users = wrap(UsersPort, providers.users, recorder)
    with recorder.turn() as outer:
        users.get("user#alex")
        with recorder.turn() as inner:
            users.get("user#ghost")
        users.get("user#bea")
    assert [c.params["id"] for c in outer] == ["user#alex", "user#bea"]
    assert [c.params["id"] for c in inner] == ["user#ghost"]


def test_parallel_turns_on_two_threads_see_only_their_own_calls(providers) -> None:
    recorder = ToolCallRecorder()
    users = wrap(UsersPort, providers.users, recorder)
    barrier = threading.Barrier(2)
    seen: dict[str, list[str]] = {}

    def operator(name: str) -> None:
        with recorder.turn() as calls:
            barrier.wait(timeout=10)  # both turns are open at the same time
            for _ in range(20):
                users.get(f"user#{name}")
            barrier.wait(timeout=10)
        seen[name] = [c.params["id"] for c in calls]

    threads = [threading.Thread(target=operator, args=(n,)) for n in ("alex", "bea")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert seen == {"alex": ["user#alex"] * 20, "bea": ["user#bea"] * 20}


def test_two_recorders_are_independent(providers) -> None:
    first, second = ToolCallRecorder(), ToolCallRecorder()
    users = wrap(UsersPort, providers.users, first)
    with first.turn() as mine, second.turn() as theirs:
        users.get("user#alex")
    assert len(mine) == 1 and theirs == []


def test_clock_idgen_prose_and_stores_are_not_tool_ports() -> None:
    assert not {ClockPort, IdGenPort, LlmProsePort, SessionStorePort} & set(TOOL_PORT_NAMES)
    assert len(TOOL_PORT_NAMES) == 11
    assert len(set(TOOL_PORT_NAMES.values())) == 11
