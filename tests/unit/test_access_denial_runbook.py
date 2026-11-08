"""Story 3.3 - when the access-denial handler attaches the runbook (D-2), below the HTTP layer."""

from __future__ import annotations

import pytest

from src.adapters.outbound.sim.fixtures_adapter import SimRunbookRegistry
from src.adapters.outbound.sim.idgen_adapter import SimIdGen
from src.adapters.outbound.sim.prose_adapter import SimProse
from src.application.access_denial_handler import AccessDenialHandler
from src.application.entity_resolver import EntityResolver
from src.application.evidence_assembler import EvidenceAssembler
from src.application.pipeline import TurnInput, TurnOutput
from src.domain.intent import Routed, classify
from src.domain.result import Failure, is_ok
from src.dto import ClockReadDTO, RunbookTemplateDTO, SessionContextDTO

pytestmark = pytest.mark.unit

S1 = "Why was student Alex denied access to model deepseek-coder?"
ANNEX = "Student Alex was denied model deepseek-coder. Diagnose and provide runbook."
NOW = "2026-10-16T15:00:00.000Z"
CLASS_KEY = "access_denial_not_in_allowlist"


def template(**changes: object) -> RunbookTemplateDTO:
    base = {
        "template_id": "rb-access-denial-not-in-allowlist",
        "error_code": CLASS_KEY,
        "steps": ["step one"],
        "required_tools": ["ticket system"],
        "safety_warnings": ["do not change the allowlist"],
        "physical_intervention": False,
        "approved_source": None,
        "version": "1.0",
    }
    return RunbookTemplateDTO(**{**base, **changes})


def handler_for(providers, runbooks) -> AccessDenialHandler:
    return AccessDenialHandler(
        resolver=EntityResolver(users=providers.users, catalog=providers.catalog),
        assembler=EvidenceAssembler(policy=providers.policy, events=providers.event_store),
        prose=SimProse(),
        idgen=SimIdGen(),
        runbooks=runbooks,
    )


def run(handler: AccessDenialHandler, query: str):
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


def answer(handler: AccessDenialHandler, query: str):
    result = run(handler, query)
    assert is_ok(result), result
    output: TurnOutput = result.value
    return output.answer


def test_a_runbook_is_attached_only_when_the_query_asks_for_one(providers) -> None:
    handler = handler_for(providers, SimRunbookRegistry((template(),)))
    assert answer(handler, ANNEX).recommendation["runbook"]["steps"] == ["step one"]
    assert answer(handler, S1).recommendation is None  # the same denial, no request for a runbook


def test_a_request_for_a_runbook_with_no_template_attaches_nothing(providers) -> None:
    handler = handler_for(providers, SimRunbookRegistry(()))
    got = answer(handler, ANNEX)
    assert got.recommendation is None
    assert got.diagnosis_class == CLASS_KEY  # the diagnosis itself is unchanged


def test_an_unsourced_physical_template_is_never_attached(providers) -> None:
    handler = handler_for(
        providers,
        SimRunbookRegistry((template(physical_intervention=True, approved_source=None),)),
    )
    assert answer(handler, ANNEX).recommendation is None


def test_a_registry_failure_aborts_the_turn_and_attaches_nothing(providers) -> None:
    handler = handler_for(providers, SimRunbookRegistry(Failure("PROVIDER_UNAVAILABLE")))
    result = run(handler, ANNEX)
    assert not is_ok(result) and result.code == "PROVIDER_UNAVAILABLE"
