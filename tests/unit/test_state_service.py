"""StateService: one route-name table, checks before reads, paged totals (FR-12, I22, E13, E49)."""

from __future__ import annotations

import pytest

from src.adapters.outbound.sim.fixtures_adapter import SimProviders
from src.application.state_service import STATE_ROW_CAP, StateService
from src.config import PROJECT_ROOT
from src.domain import canonical_strings as cs
from src.domain.result import Failure, Ok, is_ok
from src.dto import NodeRecordDTO
from src.ports.outbound import NodesPort

pytestmark = pytest.mark.unit

START = "2026-10-16T15:00:00.000Z"
ROUTES = {
    "users": ("user", "alex"),
    "catalog": ("model", "deepseek-coder"),
    "policy": ("policy", "catalog.4.2"),
    "groups": ("group", "group-4"),
    "jobs": ("job", "job-8801"),
    "nodes": ("node", "ws-gpu-11"),
    "reservations": ("reservation", "res-001"),
    "windows": ("window", "night"),
    "events": ("event", "evt-4711"),
}
RECORD_TYPES = {
    "users": "UserRecordDTO", "catalog": "ModelCatalogEntryDTO", "policy": "AccessPolicyClauseDTO",
    "groups": "GroupRecordDTO", "jobs": "JobRecordDTO", "nodes": "NodeRecordDTO",
    "reservations": "ReservationRecordDTO", "windows": "PolicyWindowDTO",
    "events": "OperationalEventDTO",
}  # fmt: skip


@pytest.fixture(scope="module")
def providers() -> SimProviders:
    return SimProviders.from_fixtures(PROJECT_ROOT / "fixtures", START)


def service_on(providers: SimProviders, **override) -> StateService:
    ports = dict(
        users=providers.users, catalog=providers.catalog, policy=providers.policy,
        groups=providers.groups, jobs=providers.jobs, nodes=providers.nodes,
        reservations=providers.reservations, windows=providers.windows,
        event_store=providers.event_store,
    )  # fmt: skip
    return StateService(**{**ports, **override})


def node(n: int) -> NodeRecordDTO:
    return NodeRecordDTO(
        id=f"node#n-{n:05d}", hostname=f"n-{n:05d}", gpu_memory_gb=24, status="available",
        cordoned=False, error_code=None, health="healthy",
    )  # fmt: skip


class _SpyNodes(NodesPort):
    """A node port over ``count`` synthetic nodes that counts every read."""

    def __init__(self, count: int = 0, fail: bool = False) -> None:
        self._nodes = [node(n) for n in range(count)]
        self._fail = fail
        self.reads = 0

    def get(self, node_id):
        self.reads += 1
        if self._fail:
            return Failure("PROVIDER_UNAVAILABLE", observed=("nodes down",))
        return Ok(next((n for n in self._nodes if n.id == node_id), None))

    def select(self, selector):
        self.reads += 1
        return Ok([])

    def browse(self, q, page, page_size):
        self.reads += 1
        if self._fail:
            return Failure("PROVIDER_UNAVAILABLE", observed=("nodes down",))
        return Ok(self._nodes[(page - 1) * page_size : page * page_size])


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_every_route_name_reads_its_own_port(providers, route: str) -> None:
    kind, bare = ROUTES[route]
    result = service_on(providers).get_state_record(route, bare)
    assert is_ok(result), result
    key = f"{kind}#{bare}"
    record = result.value
    assert type(record).__name__ == RECORD_TYPES[route]
    assert key in record.model_dump().values()  # the record's own id field holds the key


def test_the_nine_route_names_are_exactly_the_contract_enum(providers) -> None:
    result = service_on(providers).get_state_record("gpus", "x")
    assert isinstance(result, Failure) and result.code == "VALIDATION_BAD_ENTITY_TYPE"
    assert result.message == (
        "Unknown entity type gpus; expected one of ['users', 'catalog', 'policy', 'groups',"
        " 'jobs', 'nodes', 'reservations', 'windows', 'events']."
    )


def test_an_absent_record_is_entity_not_found_with_its_key(providers) -> None:
    result = service_on(providers).get_state_record("nodes", "ghost")
    assert isinstance(result, Failure) and result.code == "ENTITY_NOT_FOUND"
    assert result.message == cs.S_ENF.format(ref_list="node#ghost")


@pytest.mark.parametrize("bad", ["ws gpu 11", "", "a/b", "x" * 201, "user#alex", "é"])
def test_a_malformed_id_is_a_400_before_any_read(providers, bad: str) -> None:
    spy = _SpyNodes()
    result = service_on(providers, nodes=spy).get_state_record("nodes", bad)
    assert isinstance(result, Failure) and result.code == "VALIDATION_MALFORMED_BODY"
    assert spy.reads == 0


def test_a_bad_type_wins_over_a_bad_id(providers) -> None:
    result = service_on(providers).get_state_record("gpus", "not an id")
    assert result.code == "VALIDATION_BAD_ENTITY_TYPE"


def test_a_provider_failure_passes_through(providers) -> None:
    down = _SpyNodes(fail=True)
    service = service_on(providers, nodes=down)
    for result in (service.get_state_record("nodes", "x"), service.browse_state("nodes", "", 1, 5)):
        assert isinstance(result, Failure) and result.observed == ("nodes down",)


@pytest.mark.parametrize(
    ("page", "page_size"), [(0, 20), (-1, 20), (1, 0), (1, 101), (10_001, 1), (101, 100), (501, 20)]
)
def test_invalid_pagination_is_rejected_before_any_read(providers, page, page_size) -> None:
    spy = _SpyNodes(5)
    result = service_on(providers, nodes=spy).browse_state("nodes", "", page, page_size)
    assert isinstance(result, Failure) and result.code == "PAGINATION_INVALID"
    assert spy.reads == 0


@pytest.mark.parametrize(("page", "page_size"), [(10_000, 1), (100, 100), (500, 20)])
def test_the_deepest_valid_page_is_accepted(providers, page, page_size) -> None:
    service = service_on(providers, nodes=_SpyNodes(3))
    assert is_ok(service.browse_state("nodes", "", page, page_size))


def test_a_bad_type_wins_over_bad_pagination(providers) -> None:
    assert service_on(providers).browse_state("gpus", "", 0, 0).code == "VALIDATION_BAD_ENTITY_TYPE"


def test_total_counts_every_match_by_paging_the_port(providers) -> None:
    spy = _SpyNodes(250)
    page = service_on(providers, nodes=spy).browse_state("nodes", "", 2, 20).value
    assert page.total == 250 and len(page.items) == 20
    assert [n.id for n in page.items] == [node(n).id for n in range(20, 40)]
    assert spy.reads == 1 + 3  # one page read, then 100 + 100 + 50 to count


def test_total_is_clamped_to_ten_thousand(providers) -> None:
    spy = _SpyNodes(STATE_ROW_CAP + 150)
    page = service_on(providers, nodes=spy).browse_state("nodes", "", 1, 100).value
    assert page.total == STATE_ROW_CAP
    assert spy.reads == 1 + STATE_ROW_CAP // 100  # stops at the cap


def test_an_exact_multiple_of_the_count_page_needs_one_empty_read(providers) -> None:
    spy = _SpyNodes(200)
    assert service_on(providers, nodes=spy).browse_state("nodes", "", 1, 5).value.total == 200
    assert spy.reads == 1 + 3


def test_a_page_beyond_total_is_empty_with_the_same_total(providers) -> None:
    page = service_on(providers).browse_state("users", "", 50, 10).value
    assert page.items == [] and page.total == 8 and (page.page, page.page_size) == (50, 10)


def test_q_matches_the_key_or_bare_id_case_folded(providers) -> None:
    service = service_on(providers)
    for q in ("WS-GPU-11", "node#ws-gpu-11", "  ws-gpu-11 "):
        page = service.browse_state("nodes", q, 1, 20).value
        assert [n.id for n in page.items] == ["node#ws-gpu-11"] and page.total == 1
    assert service.browse_state("nodes", "ws-gpu", 1, 20).value.total == 0  # exact, not prefix
