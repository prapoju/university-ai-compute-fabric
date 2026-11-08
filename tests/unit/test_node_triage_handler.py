"""Story 3.3 - the node-triage diagnoser below the HTTP layer (Annex 12.6, AD-9, AD-12)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from src.adapters.outbound.sim.fixtures_adapter import SimRunbookRegistry
from src.adapters.outbound.sim.idgen_adapter import SimIdGen
from src.adapters.outbound.sim.prose_adapter import SimProse
from src.application.entity_resolver import EntityResolver
from src.application.node_triage_handler import NodeTriageHandler
from src.application.pipeline import TurnInput, TurnOutput
from src.domain import canonical_strings as cs
from src.domain.intent import Routed, classify
from src.domain.result import Failure, Ok, Result, is_ok
from src.dto import ClockReadDTO, ProsePromptDTO, RunbookTemplateDTO, SessionContextDTO
from src.ports.inbound import CanonicalOutcome
from src.ports.outbound import LlmProsePort

pytestmark = pytest.mark.unit

S3 = "Node ws-gpu-11 is cordoned with code ERR_THERMAL_88. What should I do?"
NOW = "2026-10-16T15:00:00.000Z"


@dataclass
class CountingProse(LlmProsePort):
    """The real simulated writer, counting calls: a canonical miss must never call it."""

    inner: SimProse = field(default_factory=SimProse)
    calls: int = 0

    def compose(self, prompt: ProsePromptDTO) -> Result[str]:
        self.calls += 1
        return self.inner.compose(prompt)


def handler_for(providers, *, runbooks=None, prose=None) -> tuple[NodeTriageHandler, CountingProse]:
    counting = prose or CountingProse()
    handler = NodeTriageHandler(
        resolver=EntityResolver(
            users=providers.users, catalog=providers.catalog, nodes=providers.nodes
        ),
        nodes=providers.nodes,
        runbooks=runbooks or providers.runbook_registry,
        prose=counting,
        idgen=SimIdGen(),
    )
    return handler, counting


def run(handler: NodeTriageHandler, query: str = S3) -> TurnOutput:
    result = run_result(handler, query)
    assert is_ok(result), result
    return result.value


def run_result(handler: NodeTriageHandler, query: str = S3):
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


def template(**changes: object) -> RunbookTemplateDTO:
    base = {
        "template_id": "rb-test",
        "error_code": "ERR_THERMAL_88",
        "steps": ["only step"],
        "required_tools": [],
        "safety_warnings": [],
        "physical_intervention": True,
        "approved_source": None,
        "version": "1.0",
    }
    return RunbookTemplateDTO(**{**base, **changes})


def test_s3_calls_the_writer_once_and_resolves_the_node(providers) -> None:
    handler, prose = handler_for(providers)
    output = run(handler)
    assert prose.calls == 1
    assert output.canonical is None
    assert output.resolved_entities == ("node#ws-gpu-11",)


def test_an_unknown_code_is_the_canonical_miss_with_no_writer_call(providers) -> None:
    # the node reports ERR_THERMAL_88 but the registry holds no template for it at all
    handler, prose = handler_for(providers, runbooks=SimRunbookRegistry(()))
    output = run(handler)
    assert output.canonical == CanonicalOutcome(
        "RUNBOOK_NOT_FOUND", "no runbook available for code ERR_THERMAL_88."
    )
    assert output.answer.recommendation is None
    assert output.answer.claims == [] and output.answer.evidence == []
    assert output.answer.diagnosis_class == "no_runbook_available"
    assert prose.calls == 0


def test_a_physical_template_without_an_approved_source_renders_unavailability(providers) -> None:
    registry = SimRunbookRegistry((template(physical_intervention=True, approved_source=None),))
    handler, prose = handler_for(providers, runbooks=registry)
    output = run(handler)
    assert output.canonical == CanonicalOutcome(
        "RUNBOOK_NOT_FOUND", "no runbook available for code ERR_THERMAL_88."
    )
    assert output.answer.recommendation is None
    assert prose.calls == 0


def test_a_non_physical_template_renders_its_steps_without_a_source(providers) -> None:
    registry = SimRunbookRegistry(
        (template(physical_intervention=False, approved_source=None, steps=["a", "b"]),)
    )
    handler, _ = handler_for(providers, runbooks=registry)
    output = run(handler)
    assert output.answer.recommendation["runbook"]["steps"] == ["a", "b"]
    assert output.answer.recommendation["runbook"]["provenance"]["source"] is None


def test_a_missing_code_or_node_is_a_clarification_never_a_miss(providers) -> None:
    handler, prose = handler_for(providers)
    output = run(handler, "Node ws-gpu-11 is cordoned with code. What should I do?")
    assert output.canonical == CanonicalOutcome(
        "CLARIFICATION_REQUIRED", cs.clarification(cs.R_MISSING_NODE)
    )
    assert prose.calls == 0


def test_a_provider_failure_aborts_the_turn_and_never_fabricates_steps(providers) -> None:
    handler, prose = handler_for(
        providers, runbooks=SimRunbookRegistry(Failure("PROVIDER_UNAVAILABLE"))
    )
    decision = classify(S3, [])
    turn = TurnInput(
        session_id="sess-0000000000000001",
        answer_id="ans-0000000000000001",
        query=S3,
        now=ClockReadDTO(read_id="clk-0000000000000001", instant=NOW, source="clock"),
        decision=decision,
        context=SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[]),
    )
    result = handler(turn)
    assert not is_ok(result) and result.code == "PROVIDER_UNAVAILABLE"
    assert prose.calls == 0


class FactLeakingProse(LlmProsePort):
    """A writer that always states the node id: the guard rejects it after one retry (AD-2)."""

    def __init__(self) -> None:
        self.calls = 0

    def compose(self, prompt: ProsePromptDTO) -> Result[str]:
        self.calls += 1
        return Ok("Node ws-gpu-11 is in fault; follow the steps.")


def test_prose_that_states_a_fact_is_rejected_after_one_retry_and_no_answer_renders(
    providers,
) -> None:
    leaking = FactLeakingProse()
    handler, _ = handler_for(providers, prose=leaking)
    result = run_result(handler)
    assert not is_ok(result) and result.code == "LLM_PROSE_REJECTED"
    assert leaking.calls == 2  # the first try and one retry (PROSE_ATTEMPTS)
