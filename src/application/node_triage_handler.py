"""The node-triage diagnoser (story 3.3, Annex 12.6): what to do about a cordoned node.

Order of a turn: extract the node and the code -> resolve the node exactly (AD-7) -> read the node
record -> check the node is cordoned and reports the queried code (contracts.md
``diagnose_node_triage`` P1, P2) -> look up the template for the code (exact, AD-9) -> render its
steps verbatim (AD-9) -> bind the claims -> guarded prose, once (AD-8) -> mint claim ids. A miss
is the canonical literal ``no runbook available for code {code}.`` and never reaches the LLM; a
template without an approved source is a miss too (AD-9). Any provider failure aborts the turn
(AD-12): a runbook is never fabricated.
"""

from __future__ import annotations

from src.application.entity_resolver import EntityResolver, Unresolved
from src.application.pipeline import TurnInput, TurnOutput
from src.application.turn_support import (
    bind_or_downgrade,
    canonical_turn,
    clarification_turn,
    mint_claims,
    write_prose,
)
from src.domain import canonical_strings as cs
from src.domain.references import extract_node_triage_references, in_input_order
from src.domain.result import Failure, Ok, Result, is_failure
from src.domain.runbook import diagnose_node_triage, is_renderable, runbook_miss
from src.dto import AnswerDTO, NodeRecordDTO
from src.ports.inbound import CanonicalOutcome
from src.ports.outbound import IdGenPort, LlmProsePort, NodesPort, RunbookRegistryPort

INTENT = "diagnose_node_triage"
NO_RUNBOOK = "no_runbook_available"  # DiagnosisClass of a triage that renders no steps


class NodeTriageHandler:
    def __init__(
        self,
        *,
        resolver: EntityResolver,
        nodes: NodesPort,
        runbooks: RunbookRegistryPort,
        prose: LlmProsePort,
        idgen: IdGenPort,
    ) -> None:
        self._resolver = resolver
        self._nodes = nodes
        self._runbooks = runbooks
        self._prose = prose
        self._idgen = idgen

    def __call__(self, turn: TurnInput) -> Result[TurnOutput]:
        refs = extract_node_triage_references(turn.query)
        if refs is None:
            return Ok(clarification_turn(turn, cs.R_MISSING_NODE))
        resolved = self._resolver.resolve_target("node", refs.node)
        if is_failure(resolved):
            return resolved
        if isinstance(resolved.value, Unresolved):
            message = cs.entity_not_found(in_input_order(turn.query, resolved.value.refs))
            return Ok(canonical_turn(turn, INTENT, "ENTITY_NOT_FOUND", message))

        record = self._nodes.get(resolved.value.key)
        if is_failure(record):
            return record
        if record.value is None:  # resolved a moment ago: a vanished record is a provider fault
            return Failure("PROVIDER_UNAVAILABLE", observed=("node record vanished",))
        node = record.value

        # contracts.md P1/P2: the node is checked before the template is looked up
        miss = runbook_miss(node, refs.code)
        if miss is not None:
            return Ok(self._no_runbook(turn, node, miss))

        template = self._runbooks.get(refs.code)
        if is_failure(template):
            if not template.code.startswith("VALIDATION_"):  # a malformed code is no template
                return template
            template = Ok(None)
        if template.value is None or not is_renderable(template.value):
            return Ok(self._no_runbook(turn, node, refs.code))

        diagnosis = diagnose_node_triage(node, template.value)
        downgraded = bind_or_downgrade(
            turn, INTENT, diagnosis.claims, diagnosis.evidence, (node.id,)
        )
        if downgraded is not None:
            return Ok(downgraded)  # an unbound claim never renders (FR-13): no LLM, no claim id
        prose = write_prose(self._prose, diagnosis.evidence, diagnosis.fact_tokens)
        if is_failure(prose):
            return prose
        claims = mint_claims(self._idgen, diagnosis.claims)
        if is_failure(claims):
            return claims
        answer = AnswerDTO(
            answer_id=turn.answer_id,
            session_id=turn.session_id,
            query=turn.query,
            intent=INTENT,
            answer_chain=["observation", "evidence", "diagnosis", "recommendation"],
            diagnosis_class=diagnosis.diagnosis_class,
            claims=claims.value,
            evidence=list(diagnosis.evidence),
            recommendation=diagnosis.recommendation,
            prose=prose.value,
        )
        return Ok(TurnOutput(answer, resolved_entities=(node.id,)))

    @staticmethod
    def _no_runbook(turn: TurnInput, node: NodeRecordDTO, code: str) -> TurnOutput:
        """The canonical miss: the literal names ``code``, no steps, no LLM (D-3)."""
        answer = AnswerDTO(
            answer_id=turn.answer_id,
            session_id=turn.session_id,
            query=turn.query,
            intent=INTENT,
            answer_chain=["observation"],
            diagnosis_class=NO_RUNBOOK,
            claims=[],
            evidence=[],
            prose=cs.S_RBX.format(code=code),
        )
        return TurnOutput(
            answer,
            canonical=CanonicalOutcome("RUNBOOK_NOT_FOUND", cs.S_RBX.format(code=code)),
            resolved_entities=(node.id,),
        )


__all__ = ["INTENT", "NodeTriageHandler"]
