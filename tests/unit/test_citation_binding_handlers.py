"""Story 1.4 - both diagnosers downgrade an unbound answer to ``S_CNC`` before the LLM (FR-13).

Real fixtures, real ports, the real pure diagnosis. Only the diagnosis result is bent after the
fact (a stray citation, an uncited claim, a duplicated evidence entry) to reach a state the
diagnosers never produce, so the guard in the handlers is what is under test.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.adapters.outbound.db.migrate import apply_migrations
from src.adapters.outbound.db.session_store import SqliteSessionStore
from src.adapters.outbound.db.sqlite_writer import SqliteWriter
from src.adapters.outbound.sim.idgen_adapter import SimIdGen
from src.adapters.outbound.sim.prose_adapter import SimProse
from src.application import access_denial_handler, window_diagnosis_handler
from src.application.access_denial_handler import AccessDenialHandler
from src.application.entity_resolver import EntityResolver
from src.application.evidence_assembler import EvidenceAssembler
from src.application.pipeline import TurnInput
from src.application.window_diagnosis_handler import WindowDiagnosisHandler
from src.config import PROJECT_ROOT
from src.domain import canonical_strings as cs
from src.domain.intent import Routed, classify
from src.domain.result import is_ok
from src.dto import ClockReadDTO, SessionContextDTO, SessionDTO
from src.ports.inbound import CanonicalOutcome

pytestmark = pytest.mark.unit

S1 = "why was alex denied deepseek-coder"
S2 = "why can't group 4 run their fine-tuning job right now"
NOW = ClockReadDTO(
    read_id="clk-0000000000000001", instant="2026-10-16T15:00:00.000Z", source="clock"
)
STRAY = "policy#not-in-the-evidence"


def stray_citation(diagnosis):
    first, *rest = diagnosis.claims
    bent = replace(first, citations=(*first.citations, STRAY))
    return replace(diagnosis, claims=(bent, *rest))


def uncited_claim(diagnosis):
    first, *rest = diagnosis.claims
    return replace(diagnosis, claims=(replace(first, citations=()), *rest))


def duplicated_evidence(diagnosis):
    extra = diagnosis.evidence[0].model_copy(update={"position": len(diagnosis.evidence)})
    return replace(diagnosis, evidence=(*diagnosis.evidence, extra))


def bend(monkeypatch, module, name: str, how) -> None:
    real = getattr(module, name)
    monkeypatch.setattr(module, name, lambda *args, **kwargs: how(real(*args, **kwargs)))


def access_denial(providers, prose: SimProse, idgen: SimIdGen) -> AccessDenialHandler:
    return AccessDenialHandler(
        resolver=EntityResolver(users=providers.users, catalog=providers.catalog),
        assembler=EvidenceAssembler(policy=providers.policy, events=providers.event_store),
        prose=prose,
        idgen=idgen,
    )


def window(providers, prose: SimProse, idgen: SimIdGen) -> WindowDiagnosisHandler:
    return WindowDiagnosisHandler(
        resolver=EntityResolver(
            users=providers.users, catalog=providers.catalog, groups=providers.groups
        ),
        jobs=providers.jobs,
        windows=providers.windows,
        prose=prose,
        idgen=idgen,
    )


CASES = {
    "s1": (access_denial, access_denial_handler, "diagnose_access_denial", S1),
    "s2": (window, window_diagnosis_handler, "diagnose_schedule_window", S2),
}


def migrated_store() -> SqliteSessionStore:
    writer = SqliteWriter.open(":memory:")
    apply_migrations(writer, PROJECT_ROOT / "migrations")
    return SqliteSessionStore(writer)


def run(handler, query: str):
    decision = classify(query, [])
    assert isinstance(decision, Routed), decision
    turn = TurnInput(
        session_id="sess-0000000000000001",
        answer_id="ans-0000000000000001",
        query=query,
        now=NOW,
        decision=decision,
        context=SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[]),
    )
    result = handler(turn)
    assert is_ok(result), result
    return result.value


@pytest.mark.parametrize("scenario", CASES)
@pytest.mark.parametrize(
    "how",
    [stray_citation, uncited_claim, duplicated_evidence],
    ids=["stray", "uncited", "duplicate"],
)
def test_an_unbound_answer_downgrades_to_cannot_confirm_without_llm_or_claim_ids(
    providers, monkeypatch, scenario: str, how
) -> None:
    build, module, function, query = CASES[scenario]
    honest = run(build(providers, SimProse(), SimIdGen()), query).answer
    bend(monkeypatch, module, function, how)
    prose, idgen = SimProse(), SimIdGen()

    output = run(build(providers, prose, idgen), query)

    # the gathered evidence is kept for audit, each id once (a duplicate keeps its first entry)
    checked = [entry.citation_id for entry in honest.evidence]
    assert output.canonical == CanonicalOutcome("CANNOT_CONFIRM", cs.cannot_confirm(checked))
    assert output.answer.prose == cs.S_CNC.format(checked_list=", ".join(checked))
    assert output.answer.canonical == "CANNOT_CONFIRM"
    assert output.answer.claims == [] and output.answer.diagnosis_class is None
    assert output.answer.evidence == honest.evidence
    assert prose.call_count == 0  # the LLM never saw an unbound answer
    assert idgen.new_id("claim").value == "clm-0000000000000001"  # no claim id was drawn

    # and the downgraded turn is storable: no claim row, the evidence primary key holds
    store = migrated_store()
    session = SessionDTO(
        session_id="sess-0000000000000001",
        created_at=NOW.instant,
        operator_role="role-operations",
        context=SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[]),
        status="active",
    )
    assert is_ok(store.create(session, NOW.instant))
    assert is_ok(store.append_turn(session.session_id, output.answer, session.context, NOW.instant))
    stored = store.list_turns(session.session_id).value
    assert [(t.canonical, t.claims, t.evidence) for t in stored] == [
        ("CANNOT_CONFIRM", [], honest.evidence)
    ]


@pytest.mark.parametrize("scenario", CASES)
def test_a_bound_answer_is_untouched_by_the_guard(providers, scenario: str) -> None:
    build, _, _, query = CASES[scenario]
    prose = SimProse()
    output = run(build(providers, prose, SimIdGen()), query)
    assert output.canonical is None and output.answer.claims
    assert prose.call_count == 1
