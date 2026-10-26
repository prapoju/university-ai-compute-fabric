"""Story 3.1 - the window diagnoser below the HTTP layer (Annex 12.2, FR-05)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.adapters.outbound.sim.idgen_adapter import SimIdGen
from src.adapters.outbound.sim.prose_adapter import SimProse
from src.application.entity_resolver import EntityResolver, Resolved, ResolvedGroup, Unresolved
from src.application.pipeline import TurnInput, TurnOutput
from src.application.window_diagnosis_handler import WindowDiagnosisHandler
from src.domain import canonical_strings as cs
from src.domain.intent import Routed, classify
from src.domain.result import Failure, is_ok
from src.dto import ClockReadDTO, SessionContextDTO
from src.ports.inbound import CanonicalOutcome

pytestmark = pytest.mark.unit

S2 = "why can't group 4 run their fine-tuning job right now"
NOW = "2026-10-16T15:00:00.000Z"


@dataclass
class Rig:
    handler: WindowDiagnosisHandler
    prose: SimProse
    providers: object


def make_rig(providers, *, resolver=None) -> Rig:
    prose = SimProse()
    handler = WindowDiagnosisHandler(
        resolver=resolver
        or EntityResolver(
            users=providers.users, catalog=providers.catalog, groups=providers.groups
        ),
        jobs=providers.jobs,
        windows=providers.windows,
        prose=prose,
        idgen=SimIdGen(),
    )
    return Rig(handler, prose, providers)


@pytest.fixture
def rig(providers) -> Rig:
    return make_rig(providers)


def run(rig: Rig, query: str = S2, instant: str = NOW):
    decision = classify(query, [])
    assert isinstance(decision, Routed), decision
    turn = TurnInput(
        session_id="sess-0000000000000001",
        answer_id="ans-0000000000000001",
        query=query,
        now=ClockReadDTO(read_id="clk-0000000000000001", instant=instant, source="clock"),
        decision=decision,
        context=SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[]),
    )
    return rig.handler(turn)


def out(result) -> TurnOutput:
    assert is_ok(result), result
    return result.value


# -- resolver: groups are exact, never fuzzy ------------------------------------------------
@pytest.mark.parametrize("token", ["group-4", "GROUP-4", "group#group-4", "group#GROUP-4"])
def test_a_group_resolves_exactly_and_case_folded(providers, token: str) -> None:
    resolved = EntityResolver(
        users=providers.users, catalog=providers.catalog, groups=providers.groups
    ).resolve_group(token)
    assert is_ok(resolved) and isinstance(resolved.value, ResolvedGroup)
    assert resolved.value.group.id == "group#group-4"


@pytest.mark.parametrize(
    ("token", "named"),
    [
        ("group-99", "group#group-99"),
        ("group-", "group#group-"),
        ("user#alex", "user#alex"),  # typed as something else: named as typed
        ("group#", "group#"),
    ],
)
def test_an_unknown_group_is_unresolved_and_named(providers, token: str, named: str) -> None:
    resolved = EntityResolver(
        users=providers.users, catalog=providers.catalog, groups=providers.groups
    ).resolve_group(token)
    assert is_ok(resolved) and resolved.value == Unresolved((named,))


def test_a_resolver_without_a_groups_port_fails_typed(providers) -> None:
    result = EntityResolver(users=providers.users, catalog=providers.catalog).resolve_group(
        "group-4"
    )
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert Resolved  # the user/model resolution API is unchanged


# -- S2 ---------------------------------------------------------------------------------------
def test_s2_returns_a_cited_restricted_diagnosis(rig: Rig) -> None:
    output = out(run(rig))
    answer = output.answer
    assert answer.intent == "diagnose_schedule_window" and answer.canonical is None
    # EXPERIENCE.md S2: the chain reaches the recommendation, which is the next open window
    assert answer.answer_chain == ["observation", "evidence", "diagnosis", "recommendation"]
    assert answer.recommendation == {
        "next_open_window": {
            "start": "2026-10-16T22:00:00.000Z", "end": "2026-10-17T06:00:00.000Z",
            "timezone": "UTC",
        }
    }  # fmt: skip
    assert answer.diagnosis_class == "schedule_window_restricted"
    assert [e.citation_id for e in answer.evidence] == [
        "group#group-4", "job#job-8823", "window#night", "clock#clk-0000000000000001",
    ]  # fmt: skip
    assert [c.claim_id for c in answer.claims] == [f"clm-{n:016x}" for n in (1, 2, 3)]
    ids = {e.citation_id for e in answer.evidence}
    assert all(set(claim.claim_citations) == ids for claim in answer.claims)
    text = " ".join(c.text for c in answer.claims)
    assert "2026-10-16T22:00:00.000Z" in text and "2026-10-17T06:00:00.000Z" in text
    assert "(UTC)" in text
    assert output.resolved_entities == ("group#group-4",)


def test_the_llm_is_called_once_with_the_evidence_and_never_carries_a_fact(rig: Rig) -> None:
    answer = out(run(rig)).answer
    assert rig.prose.call_count == 1
    assert rig.prose.last_prompt.evidence_sections == [e.snippet for e in answer.evidence]
    assert answer.prose == SimProse.DEFAULT


def test_prose_naming_the_window_is_rejected_then_retried_once(rig: Rig) -> None:
    rig.prose.script("It opens again at 22:00.")
    assert out(run(rig)).answer.prose == SimProse.DEFAULT
    assert rig.prose.call_count == 2


def test_two_rejected_attempts_fail_the_turn_and_unavailable_is_not_retried(rig: Rig) -> None:
    rig.prose.script("Group 4 waits.", "The night window.")
    result = run(rig)
    assert isinstance(result, Failure) and result.code == "LLM_PROSE_REJECTED"
    rig.prose.fail()
    result = run(rig)
    assert isinstance(result, Failure) and result.code == "LLM_UNAVAILABLE"


def test_when_the_window_is_open_no_restriction_is_stated(rig: Rig) -> None:
    answer = out(run(rig, instant="2026-10-16T22:00:00.000Z")).answer  # start is inclusive
    assert answer.diagnosis_class == "schedule_no_constraint"
    # nothing to recommend: the window is open, so the chain stops at the diagnosis
    assert answer.answer_chain == ["observation", "evidence", "diagnosis"]
    assert answer.recommendation == {"next_open_window": None}


def test_a_group_with_no_constrained_job_states_no_restriction_and_no_window(rig: Rig) -> None:
    answer = out(run(rig, "why can't group 7 run their job")).answer
    assert answer.diagnosis_class == "schedule_no_constraint"
    assert not [e for e in answer.evidence if e.source_type == "window"]


# -- canonical outcomes: no LLM, nothing fabricated ---------------------------------------
def test_an_unknown_group_is_entity_not_found(rig: Rig) -> None:
    output = out(run(rig, "why can't group 99 run their job"))
    message = "Entity Not Found in State: group#group-99."
    assert output.canonical == CanonicalOutcome("ENTITY_NOT_FOUND", message)
    assert (output.answer.canonical, output.answer.claims, output.answer.evidence) == (
        "ENTITY_NOT_FOUND", [], [],
    )  # fmt: skip
    assert rig.prose.call_count == 0 and output.resolved_entities == ()


def test_a_query_naming_no_group_is_a_clarification(rig: Rig) -> None:
    output = out(run(rig, "why can't they run the job"))
    assert output.canonical == CanonicalOutcome(
        "CLARIFICATION_REQUIRED", cs.clarification(cs.R_MISSING_GROUP)
    )
    assert rig.prose.call_count == 0


def test_past_the_only_window_it_cannot_confirm_and_never_invents_one(rig: Rig) -> None:
    output = out(run(rig, instant="2026-10-17T06:00:00.000Z"))
    assert output.canonical.code == "CANNOT_CONFIRM"
    assert output.canonical.message == cs.cannot_confirm(
        ("group#group-4", "job#job-8823", "window#night")
    )
    assert output.answer.claims == [] and output.answer.answer_chain == ["observation", "evidence"]
    assert rig.prose.call_count == 0


# -- failures are safe and reads are read-only -----------------------------------------------
def test_a_failed_estate_aborts_before_any_prose(fixtures_copy, providers_from) -> None:
    (fixtures_copy / "estate" / "windows.json").unlink()
    broken = make_rig(providers_from(fixtures_copy))
    result = run(broken)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert broken.prose.call_count == 0


def test_the_estate_is_never_changed(rig: Rig, providers) -> None:
    before = providers.estate_snapshot()
    for query in (S2, "why can't group 7 run their job", "why can't group 99 run their job"):
        out(run(rig, query))
    assert providers.estate_snapshot() == before


def test_a_turn_is_deterministic(providers_from) -> None:
    from src.config import PROJECT_ROOT

    def snapshot():
        answer = out(run(make_rig(providers_from(PROJECT_ROOT / "fixtures")))).answer
        return answer.model_dump()

    assert snapshot() == snapshot() == snapshot()
