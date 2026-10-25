"""Story 1.3 - the access-denial diagnoser end to end, below the HTTP layer.

Real fixtures, real read-only ports, the real pure diagnosis; only the LLM is the scripted
simulated writer. Covers resolution, the cited diagnosis, the prose guard, canonical outcomes,
follow-ups from the session context, failure safety, read-only behaviour and determinism.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import pytest

from src.adapters.outbound.sim.fixtures_adapter import SimCatalog, SimUsers
from src.adapters.outbound.sim.idgen_adapter import SimIdGen
from src.adapters.outbound.sim.prose_adapter import SimProse
from src.adapters.outbound.sim.record_store import RecordStore
from src.application.access_denial_handler import AccessDenialHandler
from src.application.entity_resolver import EntityResolver
from src.application.evidence_assembler import EvidenceAssembler
from src.application.pipeline import TurnInput, TurnOutput
from src.config import PROJECT_ROOT
from src.domain import canonical_strings as cs
from src.domain.intent import FOLLOW_UP_RULE_ID, Routed, classify
from src.domain.result import Failure, is_ok
from src.dto import ModelCatalogEntryDTO, SessionContextDTO, UserRecordDTO
from src.ports.inbound import CanonicalOutcome
from src.ports.outbound import EventStorePort, IdGenPort

pytestmark = pytest.mark.unit

REAL_FIXTURES = PROJECT_ROOT / "fixtures"
S1 = "why was alex denied deepseek-coder"
INTENT = "diagnose_access_denial"


@dataclass
class Rig:
    handler: AccessDenialHandler
    prose: SimProse
    providers: object


def make_rig(providers, *, users=None, catalog=None, events=None, idgen=None) -> Rig:
    prose = SimProse()
    handler = AccessDenialHandler(
        resolver=EntityResolver(
            users=users or providers.users, catalog=catalog or providers.catalog
        ),
        assembler=EvidenceAssembler(
            policy=providers.policy, events=events or providers.event_store
        ),
        prose=prose,
        idgen=idgen or SimIdGen(),
    )
    return Rig(handler, prose, providers)


@pytest.fixture
def rig(providers) -> Rig:
    return make_rig(providers)


def run(rig: Rig, query: str = S1, *, resolved=(), prior=()) -> object:
    now = rig.providers.clock.now()
    assert is_ok(now)
    decision = classify(query, list(prior))
    assert isinstance(decision, Routed), decision
    context = SessionContextDTO(
        resolved_entities=list(resolved), prior_intents=list(prior), active_answer_ids=[]
    )
    turn = TurnInput(
        session_id="sess-0000000000000001",
        answer_id="ans-0000000000000001",
        query=query,
        now=now.value,
        decision=decision,
        context=context,
    )
    return rig.handler(turn)


def out(result) -> TurnOutput:
    assert is_ok(result), result
    return result.value


# -- Scenario: Diagnose the S1 access denial with citations ------------------------------------
def test_s1_is_diagnosed_with_the_full_answer_chain_and_class(rig: Rig) -> None:
    answer = out(run(rig)).answer
    assert answer.intent == INTENT and answer.canonical is None
    assert answer.answer_chain == ["observation", "evidence", "diagnosis"]
    assert answer.diagnosis_class == "access_denial_not_in_allowlist"
    assert answer.recommendation is None and answer.proposal_ref is None
    assert (answer.answer_id, answer.session_id) == (
        "ans-0000000000000001",
        "sess-0000000000000001",
    )


def test_the_claims_state_role_clause_rule_text_and_reason_class(rig: Rig) -> None:
    claims = out(run(rig)).answer.claims
    texts = " | ".join(c.text for c in claims)
    assert [c.claim_id for c in claims] == [f"clm-{n:016x}" for n in (1, 2, 3)]
    assert "role student" in texts
    assert "policy#catalog.4.2" in texts and "RULE-CAT-04" in texts and "CS-480" in texts
    assert "not-in-allowlist" in texts and "event#evt-4711" in texts


def test_every_claim_cites_user_clause_and_event_and_every_citation_resolves(rig: Rig) -> None:
    answer = out(run(rig)).answer
    evidence_ids = {e.citation_id for e in answer.evidence}
    assert len(answer.claims) >= 1
    for claim in answer.claims:
        assert {"user#alex", "policy#catalog.4.2", "event#evt-4711"} <= set(claim.claim_citations)
        assert set(claim.claim_citations) <= evidence_ids


def test_the_evidence_lists_user_model_policy_event_then_the_clock_read(rig: Rig) -> None:
    evidence = out(run(rig)).answer.evidence
    assert [e.citation_id for e in evidence] == [
        "user#alex", "model#deepseek-coder", "policy#catalog.4.2", "event#evt-4711",
        "clock#clk-0000000000000001",
    ]  # fmt: skip
    assert [e.position for e in evidence] == [0, 1, 2, 3, 4]


def test_the_session_context_gains_the_resolved_entities(rig: Rig) -> None:
    assert out(run(rig)).resolved_entities == ("user#alex", "model#deepseek-coder")


@pytest.mark.parametrize(
    "query",
    [
        "why was alex denied deepseek-coder",
        "Why was student alex denied access to deepseek-coder?",
        "WHY WAS ALEX DENIED DEEPSEEK-CODER",
        "  why   was\talex   denied   deepseek-coder  ",
        "why was alex blocked from deepseek-coder",
        "why was alex refused deepseek-coder",
        "why can't alex access deepseek-coder",
        "why cannot alex access deepseek-coder?",
        "why is alex not allowed to access deepseek-coder",
        "why is alex unable to access deepseek-coder",
        "alex was denied access to deepseek-coder",
        "why was user#alex denied model#deepseek-coder",
    ],
)
def test_every_s1_variant_resolves_and_diagnoses_identically(rig: Rig, query: str) -> None:
    answer = out(run(rig, query)).answer
    assert answer.diagnosis_class == "access_denial_not_in_allowlist"
    assert [e.citation_id for e in answer.evidence][:4] == [
        "user#alex", "model#deepseek-coder", "policy#catalog.4.2", "event#evt-4711",
    ]  # fmt: skip


# -- Scenario: The LLM only connects, it never informs -----------------------------------------
def test_the_llm_is_called_exactly_once_with_the_evidence_as_data(rig: Rig) -> None:
    answer = out(run(rig)).answer
    assert rig.prose.call_count == 1
    assert rig.prose.last_prompt.evidence_sections == [e.snippet for e in answer.evidence]
    assert rig.prose.last_prompt.instruction
    assert answer.prose == SimProse.DEFAULT


def test_the_stored_prose_contains_none_of_the_facts(rig: Rig) -> None:
    prose = out(run(rig)).answer.prose.casefold()
    for fact in ("user#alex", "alex", "deepseek-coder", "policy#catalog.4.2", "student",
                 "not-in-allowlist", "evt-4711", "rule-cat-04", "2026-10-16"):  # fmt: skip
        assert fact not in prose


def test_prose_that_carries_a_fact_is_rejected_whole_and_retried_once(rig: Rig) -> None:
    rig.prose.script("Alex was denied because of the policy.")
    answer = out(run(rig)).answer
    assert rig.prose.call_count == 2
    assert answer.prose == SimProse.DEFAULT  # the clean second attempt, not a stripped first one


def test_two_rejected_attempts_fail_the_turn_with_llm_prose_rejected(rig: Rig) -> None:
    rig.prose.script("Alex was denied.", "The student role is the reason.")
    result = run(rig)
    assert isinstance(result, Failure) and result.code == "LLM_PROSE_REJECTED"
    assert rig.prose.call_count == 2


def test_an_unavailable_llm_fails_the_turn_without_retrying(rig: Rig) -> None:
    rig.prose.fail()
    result = run(rig)
    assert isinstance(result, Failure) and result.code == "LLM_UNAVAILABLE"
    assert rig.prose.call_count == 1


def test_the_llm_is_never_consulted_for_canonical_outcomes(rig: Rig) -> None:
    run(rig, "why was ghost denied deepseek-coder")
    run(rig, "why was sofia denied deepseek-coder")
    run(rig, "why was alex denied access?")
    assert rig.prose.call_count == 0


# -- Scenario: Unresolved references never produce a diagnosis ---------------------------------
def test_an_unknown_user_is_entity_not_found_with_no_diagnosis(rig: Rig) -> None:
    output = out(run(rig, "why was ghost_user_99 denied deepseek-coder"))
    message = "Entity Not Found in State: user#ghost_user_99."
    assert output.canonical == CanonicalOutcome("ENTITY_NOT_FOUND", message)
    answer = output.answer
    assert (answer.canonical, answer.diagnosis_class, answer.prose) == (
        "ENTITY_NOT_FOUND",
        None,
        message,
    )
    assert (answer.answer_chain, answer.claims, answer.evidence) == (["observation"], [], [])
    assert output.resolved_entities == ()


def test_every_unresolved_reference_is_named_in_input_order(rig: Rig) -> None:
    output = out(run(rig, "why was ghost denied imaginary-model"))
    assert (
        output.canonical.message == "Entity Not Found in State: user#ghost, model#imaginary-model."
    )
    only_model = out(run(rig, "why was alex denied imaginary-model"))
    assert only_model.canonical.message == "Entity Not Found in State: model#imaginary-model."


def test_resolution_is_exact_never_fuzzy(rig: Rig) -> None:
    output = out(run(rig, "why was ale denied deepseek-code"))
    assert output.canonical.message == "Entity Not Found in State: user#ale, model#deepseek-code."


def test_at_least_ten_nonexistent_references_all_return_entity_not_found(rig: Rig) -> None:
    ghosts = ["ghost", "nobody", "user42", "alexx", "ale", "mateo2", "x", "root", "admin", "zz-top"]
    for ghost in ghosts:
        output = out(run(rig, f"why was {ghost} denied deepseek-coder"))
        assert output.canonical.code == "ENTITY_NOT_FOUND", ghost
        assert output.answer.claims == [] and output.answer.evidence == [], (
            ghost
        )  # zero fabrication


# -- Scenario: Existing entities without a matching clause or event ----------------------------
def test_a_student_without_a_recorded_denial_is_cannot_confirm(rig: Rig) -> None:
    output = out(run(rig, "why was sofia denied deepseek-coder"))
    message = (
        "Cannot confirm (insufficient evidence): checked user#sofia, model#deepseek-coder, "
        "policy clauses for model#deepseek-coder, access_denied events for user#sofia."
    )
    assert output.canonical == CanonicalOutcome("CANNOT_CONFIRM", message)
    answer = output.answer
    assert (answer.canonical, answer.diagnosis_class) == ("CANNOT_CONFIRM", None)
    assert answer.answer_chain == ["observation", "evidence"] and answer.claims == []
    assert [e.citation_id for e in answer.evidence][:2] == ["user#sofia", "model#deepseek-coder"]
    assert output.resolved_entities == ("user#sofia", "model#deepseek-coder")  # both did resolve


def test_a_privileged_user_has_no_clause_that_explains_a_denial(rig: Rig) -> None:
    output = out(run(rig, "why was dr-vance denied deepseek-coder"))
    assert output.canonical.code == "CANNOT_CONFIRM"


# -- Scenario: Follow-up resolves from the session context -------------------------------------
CONTEXT = ("user#alex", "model#deepseek-coder")


def test_a_follow_up_resolves_the_new_user_and_takes_the_model_from_the_session(rig: Rig) -> None:
    decision = classify("and what about mateo?", [INTENT])
    assert isinstance(decision, Routed) and decision.matched_rule_id == FOLLOW_UP_RULE_ID
    output = out(run(rig, "and what about mateo?", resolved=CONTEXT, prior=[INTENT]))
    answer = output.answer
    assert answer.diagnosis_class == "access_denial_not_in_allowlist"
    assert [e.citation_id for e in answer.evidence][:4] == [
        "user#mateo", "model#deepseek-coder", "policy#catalog.4.2", "event#evt-4713",
    ]  # fmt: skip
    assert output.resolved_entities == ("user#mateo", "model#deepseek-coder")


def test_a_follow_up_with_nothing_to_resolve_against_is_a_clarification(rig: Rig) -> None:
    output = out(run(rig, "and what about mateo?", resolved=(), prior=[INTENT]))
    message = cs.clarification(cs.R_MISSING_REFERENCES)
    assert output.canonical == CanonicalOutcome("CLARIFICATION_REQUIRED", message)
    assert (output.answer.intent, output.answer.canonical) == ("clarification", "CLARIFICATION")


def test_a_follow_up_naming_nobody_is_entity_not_found_by_its_raw_text(rig: Rig) -> None:
    output = out(run(rig, "and what about ghost?", resolved=CONTEXT, prior=[INTENT]))
    assert output.canonical == CanonicalOutcome(
        "ENTITY_NOT_FOUND", "Entity Not Found in State: ghost."
    )


def test_a_context_entity_that_vanished_is_not_silently_reused(rig: Rig) -> None:
    output = out(
        run(rig, "and what about mateo?", resolved=("model#retired", "user#alex"), prior=[INTENT])
    )
    assert output.canonical.message == "Entity Not Found in State: model#retired."


def test_a_bare_reference_that_is_both_a_user_and_a_model_asks_which(providers) -> None:
    users = SimUsers(
        RecordStore(
            [UserRecordDTO(id="user#dual", display_name="D", role="student")], lambda r: r.id
        )
    )
    models = SimCatalog(
        RecordStore(
            [ModelCatalogEntryDTO(id="model#dual", name="dual", allowed_roles=["student"])],
            lambda r: r.id,
        )
    )
    rig = make_rig(providers, users=users, catalog=models)
    output = out(run(rig, "and what about dual?", resolved=CONTEXT, prior=[INTENT]))
    assert output.canonical.message == cs.clarification(cs.ambiguous_reference("dual"))


def test_a_routed_query_that_names_no_user_and_model_is_a_clarification(rig: Rig) -> None:
    output = out(run(rig, "why was alex denied access?"))
    assert output.canonical == CanonicalOutcome(
        "CLARIFICATION_REQUIRED", cs.clarification(cs.R_MISSING_REFERENCES)
    )


# -- Scenario: Failures and reads are safe -----------------------------------------------------
def test_a_failed_estate_aborts_the_turn_before_any_prose(fixtures_copy, providers_from) -> None:
    (fixtures_copy / "estate" / "policy.json").unlink()
    broken = make_rig(providers_from(fixtures_copy))
    result = run(broken)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert broken.prose.call_count == 0


class _FailingEvents(EventStorePort):
    def query(self, entity_ref, type, window):  # noqa: A002
        return Failure("PROVIDER_UNAVAILABLE", observed=("event store down",))


def test_an_event_store_failure_discards_everything_no_partial_evidence(providers) -> None:
    rig = make_rig(providers, events=_FailingEvents())
    result = run(rig)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"
    assert rig.prose.call_count == 0


class _BrokenIds(IdGenPort):
    def new_id(self, kind):
        return Failure("PROVIDER_UNAVAILABLE", observed=("ids down",))


def test_an_id_failure_aborts_the_turn_with_the_typed_failure(providers) -> None:
    rig = make_rig(providers, idgen=_BrokenIds())
    result = run(rig)
    assert isinstance(result, Failure) and result.code == "PROVIDER_UNAVAILABLE"


def test_a_burst_of_turns_never_changes_the_estate(rig: Rig, providers) -> None:
    before = providers.estate_snapshot()
    for query in (S1, "why was sofia denied deepseek-coder", "why was ghost denied deepseek-coder"):
        out(run(rig, query))
    assert providers.estate_snapshot() == before


# -- Scenario: Determinism and speed -----------------------------------------------------------
def test_three_fresh_runs_give_identical_evidence_claims_citations_and_class(
    providers_from,
) -> None:
    def snapshot():
        answer = out(run(make_rig(providers_from(REAL_FIXTURES)))).answer
        return (
            [e.model_dump() for e in answer.evidence],
            [c.model_dump() for c in answer.claims],
            answer.diagnosis_class,
            answer.answer_chain,
        )

    first = snapshot()
    assert snapshot() == first and snapshot() == first


def test_a_turn_is_far_below_the_latency_budget(rig: Rig) -> None:
    started = time.perf_counter()
    for _ in range(20):
        out(run(rig))
    assert (time.perf_counter() - started) / 20 < 0.1  # budget is 3000 ms p95 (NFR-5)


# -- review patches ----------------------------------------------------------------------------
@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
def test_empty_prose_is_rejected_and_retried(rig: Rig, blank: str) -> None:
    rig.prose.script(blank)
    answer = out(run(rig)).answer
    assert rig.prose.call_count == 2 and answer.prose == SimProse.DEFAULT


def test_two_empty_attempts_fail_the_turn(rig: Rig) -> None:
    rig.prose.script("", " ")
    result = run(rig)
    assert isinstance(result, Failure) and result.code == "LLM_PROSE_REJECTED"


def test_a_failed_turn_does_not_burn_claim_ids(rig: Rig) -> None:
    rig.prose.fail()
    assert isinstance(run(rig), Failure)
    rig.prose.recover()
    claims = out(run(rig)).answer.claims
    assert [c.claim_id for c in claims] == [f"clm-{n:016x}" for n in (1, 2, 3)]


def test_prose_naming_a_course_code_from_the_clause_text_is_rejected(rig: Rig) -> None:
    rig.prose.script("This usually needs CS-480.")
    out(run(rig))
    assert rig.prose.call_count == 2  # first attempt rejected, clean default accepted


def test_ordinary_connective_words_such_as_denied_are_allowed(rig: Rig) -> None:
    rig.prose.script("Access was denied, and the records below explain it.")
    out(run(rig))
    assert rig.prose.call_count == 1
