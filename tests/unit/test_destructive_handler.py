"""Story 2.1 - the refusal handler below the HTTP layer (FR-09, NFR-8, AD-1, AD-4, AD-7)."""

from __future__ import annotations

import pytest

from src.application.destructive_handler import INTENT, DestructiveRefusalHandler
from src.application.entity_resolver import EntityResolver, ResolvedTarget, Unresolved
from src.application.pipeline import TurnInput, TurnOutput
from src.domain import canonical_strings as cs
from src.domain.intent import Routed, classify
from src.domain.result import Failure, Ok, is_ok
from src.dto import ClockReadDTO, SessionContextDTO
from src.ports.inbound import CanonicalOutcome
from src.ports.outbound import JobsPort

pytestmark = pytest.mark.unit

NOW = "2026-10-16T15:00:00.000Z"


def resolver_for(providers, **ports) -> EntityResolver:
    return EntityResolver(
        users=providers.users,
        catalog=providers.catalog,
        groups=ports.get("groups", providers.groups),
        nodes=ports.get("nodes", providers.nodes),
        jobs=ports.get("jobs", providers.jobs),
    )


def run(handler: DestructiveRefusalHandler, query: str):
    decision = classify(query, [])
    assert isinstance(decision, Routed), decision
    turn = TurnInput(
        session_id="sess-0000000000000001",
        answer_id="ans-0000000000000001",
        query=query,
        now=ClockReadDTO(read_id="clk-0000000000000001", instant=NOW, source="clock"),
        decision=decision,
        context=SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[]),
    )
    return handler(turn)


def out(result) -> TurnOutput:
    assert is_ok(result), result
    return result.value


@pytest.fixture
def handler(providers) -> DestructiveRefusalHandler:
    return DestructiveRefusalHandler(resolver=resolver_for(providers))


# -- the refusal ----------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("query", "entity"),
    [
        ("delete all pending jobs for group 2", "group#group-2"),
        ("cancel job 8823", "job#job-8823"),
        ("drain ws-gpu-11", "node#ws-gpu-11"),
        ("cordon node#ws-gpu-11", "node#ws-gpu-11"),
    ],
)
def test_a_resolved_target_is_refused_and_added_to_the_context(
    handler, query: str, entity: str
) -> None:
    turn = out(run(handler, query))
    assert turn.canonical == CanonicalOutcome("ACTION_REFUSED", cs.S_ARF)
    assert turn.resolved_entities == (entity,)
    answer = turn.answer
    assert (answer.intent, answer.canonical, answer.prose) == (INTENT, "ACTION_REFUSED", cs.S_ARF)
    assert answer.claims == [] and answer.evidence == []  # a refusal states no fact (AD-2, AD-8)


def test_a_fleet_wide_scope_is_refused_with_no_entity_in_the_context(handler) -> None:
    turn = out(run(handler, "cordon entire lab"))
    assert turn.canonical == CanonicalOutcome("ACTION_REFUSED", cs.S_ARF)
    assert turn.resolved_entities == ()


def test_a_refusal_changes_nothing_in_the_estate(providers, handler) -> None:
    before = providers.estate_snapshot()
    for query in ("delete all pending jobs for group 2", "drain ws-gpu-11", "cordon entire lab"):
        out(run(handler, query))
    assert providers.estate_snapshot() == before  # AD-1: the handler only holds read-only ports


# -- the target is resolved before the refusal completes ---------------------------------------
@pytest.mark.parametrize(
    ("query", "named"),
    [
        ("delete all pending jobs for cs201", "group#cs201"),
        ("cancel job 9999", "job#job-9999"),
        ("drain ws-gpu-99", "node#ws-gpu-99"),
    ],
)
def test_an_unresolved_target_is_named_never_refused(handler, query: str, named: str) -> None:
    turn = out(run(handler, query))
    assert turn.canonical == CanonicalOutcome("ENTITY_NOT_FOUND", cs.entity_not_found([named]))
    assert turn.answer.canonical == "ENTITY_NOT_FOUND"
    assert turn.resolved_entities == ()


def test_a_provider_outage_is_never_reported_as_not_found(providers) -> None:
    class DownJobs(JobsPort):
        def get(self, job_id):
            return Failure("PROVIDER_UNAVAILABLE", observed=("down",))

        def select(self, selector):
            return Failure("PROVIDER_UNAVAILABLE", observed=("down",))

        def browse(self, q, page, page_size):
            return Failure("PROVIDER_UNAVAILABLE", observed=("down",))

    handler = DestructiveRefusalHandler(resolver=resolver_for(providers, jobs=DownJobs()))
    result = run(handler, "cancel job 8823")
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


# -- the verb has to fit the target (contracts P3) ----------------------------------------------
@pytest.mark.parametrize(
    "query", ["cancel ws-gpu-11", "terminate ws-gpu-11", "drain group 2", "cordon job 8823"]
)
def test_a_verb_on_the_wrong_kind_of_target_is_a_bad_action(handler, query: str) -> None:
    result = run(handler, query)
    assert isinstance(result, Failure) and result.code == "VALIDATION_BAD_ACTION"
    assert result.message is not None and "on " in result.message


@pytest.mark.parametrize("query", ["drain all jobs", "cancel every node"])
def test_a_fleet_scope_of_the_wrong_kind_is_a_bad_action(handler, query: str) -> None:
    result = run(handler, query)
    assert isinstance(result, Failure) and result.code == "VALIDATION_BAD_ACTION"


def test_an_unresolved_target_outranks_a_wrong_kind_of_verb(handler) -> None:
    turn = out(run(handler, "cancel ws-gpu-99"))  # the node does not exist: say that first
    assert turn.canonical is not None and turn.canonical.code == "ENTITY_NOT_FOUND"


# -- the resolver additions --------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kind", "token", "key"),
    [
        ("group", "group-2", "group#group-2"),
        ("group", "GROUP-2", "group#group-2"),
        ("job", "job#job-8823", "job#job-8823"),
        ("node", "WS-GPU-11", "node#ws-gpu-11"),
    ],
)
def test_resolve_target_is_exact_and_case_folded(
    providers, kind: str, token: str, key: str
) -> None:
    assert resolver_for(providers).resolve_target(kind, token) == Ok(ResolvedTarget(key))


@pytest.mark.parametrize(
    ("kind", "token", "named"),
    [
        ("group", "cs201", "group#cs201"),
        ("job", "job#nope", "job#nope"),
        ("node", "group#group-2", "group#group-2"),  # typed as another kind: a miss, as typed
    ],
)
def test_resolve_target_names_a_miss_as_typed(providers, kind: str, token: str, named: str) -> None:
    assert resolver_for(providers).resolve_target(kind, token) == Ok(Unresolved((named,)))


def test_resolve_target_without_its_port_is_a_typed_failure(providers) -> None:
    bare = EntityResolver(users=providers.users, catalog=providers.catalog)
    for kind in ("group", "job", "node"):
        result = bare.resolve_target(kind, "x")
        assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert isinstance(bare.resolve_target("course", "cs201"), Failure)


# -- not a destructive request after all -------------------------------------------------------
def test_a_compound_query_that_reaches_the_handler_is_clarified(handler) -> None:
    turn = out(run(handler, "cancel job 8823"))
    assert turn.canonical is not None and turn.canonical.code == "ACTION_REFUSED"

    compound = TurnInput(
        session_id="sess-0000000000000001",
        answer_id="ans-0000000000000002",
        query="show group 2 jobs and cancel them",
        now=ClockReadDTO(read_id="clk-0000000000000002", instant=NOW, source="clock"),
        decision=Routed(INTENT, "RULE-INTENT-DESTRUCTIVE"),
        context=SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[]),
    )
    clarified = out(handler(compound))
    assert clarified.canonical is not None
    assert clarified.canonical.code == "CLARIFICATION_REQUIRED"
    assert clarified.canonical.message == cs.clarification(cs.R_COMPOUND_DESTRUCTIVE)


def test_a_query_with_no_verb_that_reaches_the_handler_is_clarified(handler) -> None:
    stray = TurnInput(
        session_id="sess-0000000000000001",
        answer_id="ans-0000000000000003",
        query="hello there",
        now=ClockReadDTO(read_id="clk-0000000000000003", instant=NOW, source="clock"),
        decision=Routed(INTENT, "RULE-INTENT-DESTRUCTIVE"),
        context=SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[]),
    )
    clarified = out(handler(stray))
    assert clarified.canonical is not None
    assert clarified.canonical.message == cs.clarification(cs.R_NO_INTENT)
