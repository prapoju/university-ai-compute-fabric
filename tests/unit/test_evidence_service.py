"""Story 1.4 - ``get_answer_evidence`` and ``get_citation`` below the HTTP layer.

A real in-memory SQLite store, the real fixtures behind the real read-only ports, and the real
service. Answers are stored through the store's own ``append_turn``, as a turn would store them.
"""

from __future__ import annotations

import sqlite3

import pytest

from src.adapters.outbound.db.migrate import apply_migrations
from src.adapters.outbound.db.session_store import SqliteSessionStore
from src.application.evidence_service import CITATION_TYPES, EvidenceService
from src.config import PROJECT_ROOT
from src.domain import canonical_strings as cs
from src.domain.result import Failure, Ok, is_ok
from src.dto import (
    AnswerDTO,
    ClockReadDTO,
    EvidenceDTO,
    GetCitationResponse,
    SessionContextDTO,
    SessionDTO,
)

pytestmark = pytest.mark.unit

SID = "sess-0000000000000001"
T0 = "2026-10-16T15:00:00.000Z"
T1 = "2026-10-16T15:05:00.000Z"
EMPTY = SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[])
ALEX = "user#alex: Alex Rivera, role student"
CLOCK = "clock read clk-0000000000000002 at 2026-10-16T15:00:00.000Z"


def store_on(connection: sqlite3.Connection | None = None) -> SqliteSessionStore:
    connection = connection or sqlite3.connect(":memory:", check_same_thread=False)
    apply_migrations(connection, PROJECT_ROOT / "migrations")
    store = SqliteSessionStore(connection)
    session = SessionDTO(
        session_id=SID, created_at=T0, operator_role="role-operations", context=EMPTY,
        status="active",
    )  # fmt: skip
    assert is_ok(store.create(session, T0))
    return store


def service_on(store: SqliteSessionStore, providers) -> EvidenceService:
    return EvidenceService(
        store=store,
        users=providers.users,
        catalog=providers.catalog,
        policy=providers.policy,
        groups=providers.groups,
        jobs=providers.jobs,
        nodes=providers.nodes,
        reservations=providers.reservations,
        windows=providers.windows,
        event_store=providers.event_store,
    )


def entries(*cited: tuple[str, str]) -> list[EvidenceDTO]:
    return [
        EvidenceDTO(citation_id=cid, source_type=cid.partition("#")[0], snippet=snip, position=n)
        for n, (cid, snip) in enumerate(cited)
    ]


def stored(store: SqliteSessionStore, number: int, evidence: list[EvidenceDTO], now: str = T0):
    answer = AnswerDTO(
        answer_id=f"ans-{number:016x}",
        session_id=SID,
        query="why was alex denied deepseek-coder",
        intent="diagnose_access_denial",
        answer_chain=["observation", "evidence"],
        canonical="CANNOT_CONFIRM",
        claims=[],
        evidence=evidence,
        prose="p",
    )
    assert is_ok(store.append_turn(SID, answer, EMPTY, now))
    return answer


@pytest.fixture
def store() -> SqliteSessionStore:
    return store_on()


@pytest.fixture
def service(store, providers) -> EvidenceService:
    return service_on(store, providers)


def not_found(ref: str) -> Failure:
    return Failure("ENTITY_NOT_FOUND", message=cs.S_ENF.format(ref_list=ref))


# -- get_answer_evidence ------------------------------------------------------------------------
def test_the_stored_evidence_set_comes_back_unchanged_in_position_order(store, service) -> None:
    evidence = entries(
        ("user#alex", ALEX),
        ("model#deepseek-coder", "model#deepseek-coder: deepseek-coder"),
        ("clock#clk-0000000000000002", CLOCK),
    )
    stored(store, 1, evidence)
    result = service.get_answer_evidence("ans-0000000000000001")
    assert is_ok(result) and result.value.evidence == evidence
    assert [e.position for e in result.value.evidence] == [0, 1, 2]


def test_an_answer_without_evidence_has_an_empty_set_not_a_404(store, service) -> None:
    stored(store, 1, [])
    assert service.get_answer_evidence("ans-0000000000000001").value.evidence == []


@pytest.mark.parametrize("aid", ["ans-00000000000000ff", "ans-0000000000000001 ", "", "x" * 500])
def test_an_unknown_answer_is_entity_not_found(service, aid: str) -> None:
    assert service.get_answer_evidence(aid) == not_found(aid)


# -- get_citation: the happy paths --------------------------------------------------------------
def test_a_cited_record_resolves_to_its_current_record_and_the_stored_snippet(
    store, service, providers
) -> None:
    stored(store, 1, entries(("user#alex", ALEX)))
    assert service.get_citation("user#alex") == Ok(
        GetCitationResponse(source_record=providers.users.get("user#alex").value, snippet=ALEX)
    )


def test_an_event_citation_resolves_through_the_event_store(store, service, providers) -> None:
    snippet = "event#evt-4711: access_denied ..."
    stored(store, 1, entries(("event#evt-4711", snippet)))
    result = service.get_citation("event#evt-4711")
    assert is_ok(result)
    assert result.value.source_record == providers.event_store.get("event#evt-4711").value
    assert result.value.source_record.event_id == "event#evt-4711"
    assert result.value.snippet == snippet


def test_a_clock_citation_resolves_to_the_clock_read_it_cites(store, service) -> None:
    stored(store, 1, entries(("clock#clk-0000000000000002", CLOCK)))
    result = service.get_citation("clock#clk-0000000000000002")
    assert is_ok(result)
    assert result.value.source_record == ClockReadDTO(
        read_id="clk-0000000000000002", instant=T0, source="clock"
    )
    assert result.value.snippet == CLOCK


def test_the_snippet_is_the_one_of_the_most_recent_answer_that_cites_it(store, service) -> None:
    # D5: recency is created_at, not the answer id - the newer answer has the lower id here
    stored(store, 2, entries(("user#alex", "user#alex: an older snippet")), now=T0)
    stored(store, 1, entries(("user#alex", ALEX)), now=T1)
    stored(store, 3, entries(("model#deepseek-coder", "model#deepseek-coder: m")), now=T1)
    assert service.get_citation("user#alex").value.snippet == ALEX


def test_a_tie_on_time_is_broken_by_the_highest_answer_id(store, service) -> None:
    # the lower id is stored first, so scan order alone would pick it
    stored(store, 1, entries(("user#alex", "user#alex: from ans 1")), now=T0)
    stored(store, 2, entries(("user#alex", "user#alex: from ans 2")), now=T0)
    assert service.get_citation("user#alex").value.snippet == "user#alex: from ans 2"


def test_every_citation_type_but_clock_has_exactly_one_source_port(service) -> None:
    assert service.source_types == CITATION_TYPES - {"clock"}  # NFR-10: one row per type


# one real fixture record per citation type, and the provider port that owns it
OWNED_BY = {
    "user#alex": "users",
    "model#deepseek-coder": "catalog",
    "policy#catalog.4.1": "policy",
    "group#group-2": "groups",
    "job#job-8801": "jobs",
    "node#ws-gpu-01": "nodes",
    "reservation#res-001": "reservations",
    "window#night": "windows",
    "event#evt-4711": "event_store",
}


def test_the_record_cases_cover_every_type_with_a_source_port(service) -> None:
    assert {cid.partition("#")[0] for cid in OWNED_BY} == service.source_types


@pytest.mark.parametrize("cid", OWNED_BY)
def test_each_type_resolves_through_its_own_port(store, service, providers, cid: str) -> None:
    stored(store, 1, entries((cid, f"{cid}: snippet")))
    own = getattr(providers, OWNED_BY[cid]).get(cid)
    assert is_ok(own) and own.value is not None  # the fixture really holds this record
    assert service.get_citation(cid) == Ok(
        GetCitationResponse(source_record=own.value, snippet=f"{cid}: snippet")
    )


# -- get_citation: ENTITY_NOT_FOUND ---------------------------------------------------------------
@pytest.mark.parametrize(
    "cid", ["alex", "user#", "#alex", "course#CS-101", "User#alex", "", "clock"]
)
def test_a_malformed_citation_id_is_entity_not_found_never_a_400(service, cid: str) -> None:
    assert service.get_citation(cid) == not_found(cid)


def test_a_record_no_answer_cites_is_entity_not_found_even_if_it_exists(service) -> None:
    assert service.get_citation("user#alex") == not_found("user#alex")  # AD-8: never rendered


def test_the_match_on_stored_ids_is_exact(store, service) -> None:
    stored(store, 1, entries(("user#alex", ALEX)))
    assert service.get_citation("user#ALEX") == not_found("user#ALEX")


def test_a_cited_source_that_is_no_longer_in_state_is_entity_not_found(store, service) -> None:
    stored(store, 1, entries(("user#gone", "user#gone: someone who left")))
    assert service.get_citation("user#gone") == not_found("user#gone")


def test_a_clock_snippet_that_does_not_parse_is_entity_not_found(store, service) -> None:
    stored(store, 1, entries(("clock#clk-0000000000000009", "clock read clk-1 at nowhere")))
    assert service.get_citation("clock#clk-0000000000000009") == not_found(
        "clock#clk-0000000000000009"
    )


def test_a_citation_survives_a_session_reset(store, service) -> None:
    stored(store, 1, entries(("user#alex", ALEX)))
    assert is_ok(store.reset(SID, T1))  # D5: reset clears the context, never the turns
    assert service.get_citation("user#alex").value.snippet == ALEX
    assert service.get_answer_evidence("ans-0000000000000001").value.evidence


# -- failures pass through as the typed 503 ------------------------------------------------------
def test_a_provider_failure_passes_through(store, fixtures_copy, providers_from) -> None:
    (fixtures_copy / "estate" / "users.json").unlink()
    service = service_on(store, providers_from(fixtures_copy))
    stored(store, 1, entries(("user#alex", ALEX)))
    result = service.get_citation("user#alex")
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


def test_a_store_failure_passes_through_for_both_reads(providers) -> None:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    service = service_on(store_on(connection), providers)
    connection.close()
    for result in (service.get_answer_evidence("ans-1"), service.get_citation("user#alex")):
        assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


def test_the_reads_change_nothing(store, service, providers) -> None:
    stored(store, 1, entries(("user#alex", ALEX), ("clock#clk-0000000000000002", CLOCK)))
    estate = providers.estate_snapshot()
    turns = store.list_turns(SID).value
    for _ in range(2):
        assert is_ok(service.get_answer_evidence("ans-0000000000000001"))
        assert is_ok(service.get_citation("user#alex"))
        assert is_ok(service.get_citation("clock#clk-0000000000000002"))
    assert providers.estate_snapshot() == estate
    assert store.list_turns(SID).value == turns
