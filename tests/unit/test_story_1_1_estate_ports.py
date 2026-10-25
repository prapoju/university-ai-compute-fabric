"""Story 1.1 - the seeded estate behind read-only ports (Gherkin scenarios 1 and 2, plus reads).

Scenario: Estate loads offline and exposes S1 through read-only ports
Scenario: Fleet fixture has exactly 32 nodes with the specified hardware
"""

from __future__ import annotations

from collections import Counter

import pytest

from src.adapters.outbound.sim.fixtures_adapter import SimProviders
from src.domain.result import Ok, is_failure, is_ok
from src.dto import SelectorDTO
from src.ports.outbound import EventWindow

pytestmark = pytest.mark.unit

DAY = EventWindow("2026-10-16T00:00:00.000Z", "2026-10-17T00:00:00.000Z")


def _value(result):
    assert is_ok(result), result
    return result.value


# -- Scenario: Estate loads offline and exposes S1 through read-only ports ---------------------
def test_s1_alex_is_a_student_resolved_through_users_port(providers: SimProviders) -> None:
    alex = _value(providers.users.get("user#alex"))
    assert (alex.id, alex.display_name, alex.role) == ("user#alex", "Alex Rivera", "student")


def test_s1_deepseek_coder_is_restricted_by_clause_catalog_4_2(providers: SimProviders) -> None:
    clauses = _value(providers.policy.for_model("model#deepseek-coder"))
    clause = next(c for c in clauses if c.clause_id == "policy#catalog.4.2")
    assert clause.reason_class == "not-in-allowlist"
    assert "student" in clause.text
    model = _value(providers.catalog.get("model#deepseek-coder"))
    assert "student" not in model.allowed_roles


def test_s1_denial_event_is_found_by_entity_type_and_window(providers: SimProviders) -> None:
    events = _value(providers.event_store.query("user#alex", "access_denied", DAY))
    assert [e.event_id for e in events] == ["event#evt-4711"]
    assert events[0].recorded_reason.startswith("not-in-allowlist")


def test_estate_needs_no_network_and_the_clock_is_frozen(providers: SimProviders) -> None:
    first, second = _value(providers.clock.now()), _value(providers.clock.now())
    assert first.instant == second.instant == "2026-10-16T15:00:00.000Z"
    assert first.read_id != second.read_id and first.source == "clock"


# -- Scenario: Fleet fixture has exactly 32 nodes with the specified hardware ------------------
def _all_nodes(providers: SimProviders):
    nodes, page = [], 1
    while chunk := _value(providers.nodes.browse("", page, 10)):
        nodes += chunk
        page += 1
    return nodes


def test_fleet_browse_in_pages_yields_32_unique_nodes_in_id_order(providers: SimProviders) -> None:
    nodes = _all_nodes(providers)
    assert len(nodes) == 32 == len({n.id for n in nodes})
    assert [n.id for n in nodes] == sorted(n.id for n in nodes)


def test_fleet_hardware_is_31_workstations_and_one_dual_48gb_server(
    providers: SimProviders,
) -> None:
    memory = Counter(n.gpu_memory_gb for n in _all_nodes(providers))
    assert memory == {24: 31, 96: 1}


def test_ws_gpu_11_is_cordoned_with_the_thermal_error_code(providers: SimProviders) -> None:
    node = _value(providers.nodes.get("node#ws-gpu-11"))
    assert (node.status, node.cordoned, node.error_code) == ("fault", True, "ERR_THERMAL_88")


# -- reads: identity, browse, select, ordering -------------------------------------------------
def test_get_is_exact_and_case_folded_never_fuzzy(providers: SimProviders) -> None:
    assert _value(providers.users.get("USER#Alex")).id == "user#alex"
    assert _value(providers.users.get("user#ale")) is None  # a miss is Ok(None), never a guess
    assert _value(providers.users.get("user#ghost")) is None


def test_browse_matches_full_key_or_bare_id_case_folded(providers: SimProviders) -> None:
    by_bare = _value(providers.nodes.browse("WS-GPU-11", 1, 25))
    by_key = _value(providers.nodes.browse("node#ws-gpu-11", 1, 25))
    assert [n.id for n in by_bare] == [n.id for n in by_key] == ["node#ws-gpu-11"]
    assert _value(providers.nodes.browse("ws-gpu", 1, 25)) == []  # exact, not substring


def test_browse_page_beyond_the_total_is_empty_not_an_error(providers: SimProviders) -> None:
    assert _value(providers.nodes.browse("", 9999, 25)) == []


def test_jobs_select_returns_matching_records_ordered_by_id(providers: SimProviders) -> None:
    selector = SelectorDTO(method="filter", params={"course": "CS201", "status": "pending"})
    jobs = _value(providers.jobs.select(selector))
    assert [j.id for j in jobs] == ["job#job-8823", "job#job-8824", "job#job-8825"]


def test_nodes_select_by_cordoned_flag(providers: SimProviders) -> None:
    selector = SelectorDTO(method="filter", params={"cordoned": True})
    assert [n.id for n in _value(providers.nodes.select(selector))] == ["node#ws-gpu-11"]


def test_users_by_ids_keeps_input_order_and_skips_unknown(providers: SimProviders) -> None:
    users = _value(providers.users.by_ids(["user#mateo", "user#ghost", "user#alex"]))
    assert [u.id for u in users] == ["user#mateo", "user#alex"]


def test_groups_and_reservations_and_windows_are_readable(providers: SimProviders) -> None:
    assert _value(providers.groups.get("group#group-4")).members[0] == "user#mateo"
    reservation = _value(providers.reservations.get("reservation#res-001"))
    assert reservation.node_id == "node#ws-gpu-05"
    assert [w.window_id for w in _value(providers.windows.list())] == ["window#night"]
    assert _value(providers.windows.get("window#night")).timezone == "UTC"


def test_policy_clauses_for_a_model_come_back_in_clause_id_order(providers: SimProviders) -> None:
    for model in _value(providers.catalog.browse("", 1, 100)):
        ids = [c.clause_id for c in _value(providers.policy.for_model(model.id))]
        assert ids == sorted(ids)


def test_policy_content_and_runbooks_are_served_as_data(providers: SimProviders) -> None:
    night = _value(providers.policy_content.get("policy#night.2"))
    assert "22:00-06:00" in night.text and night.version
    template = _value(providers.runbook_registry.get("ERR_THERMAL_88"))
    assert template.physical_intervention and template.approved_source
    assert _value(providers.runbook_registry.get("ERR_UNKNOWN_1")) is None


# -- half-open event windows -------------------------------------------------------------------
@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (
            "2026-10-16T13:42:10.000Z",
            "2026-10-16T14:00:00.000Z",
            ["event#evt-4711"],
        ),  # start inclusive
        ("2026-10-16T13:00:00.000Z", "2026-10-16T13:42:10.000Z", []),  # end exclusive
        ("2026-10-16T13:42:10Z", "2026-10-16T13:42:11Z", ["event#evt-4711"]),  # no-millis instants
    ],
)
def test_event_windows_are_half_open(providers: SimProviders, start, end, expected) -> None:
    events = _value(
        providers.event_store.query("user#alex", "access_denied", EventWindow(start, end))
    )
    assert [e.event_id for e in events] == expected


def test_results_are_typed_ok_instances_not_bare_values(providers: SimProviders) -> None:
    result = providers.users.get("user#alex")
    assert isinstance(result, Ok) and not is_failure(result)
