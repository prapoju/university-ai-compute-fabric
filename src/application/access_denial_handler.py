"""The access-denial diagnoser (story 1.3, S1): the first end-to-end intent handler.

Order of a turn: extract the references -> resolve them exactly (AD-7) -> read the policy and
events -> diagnose in the pure domain (AD-2) -> check every claim is bound to the evidence ->
ask the LLM for prose once, guarded, with one retry (AD-8) -> mint claim ids (OP-13). Unresolved
references, unconfirmable denials and unbound claims are canonical outcomes that never reach the
LLM; any provider failure aborts the turn (AD-12).
"""

from __future__ import annotations

from src.application.entity_resolver import (
    Ambiguous,
    EntityResolver,
    MissingContext,
    Resolved,
    Unresolved,
)
from src.application.evidence_assembler import EvidenceAssembler
from src.application.pipeline import TurnInput, TurnOutput
from src.application.turn_support import (
    PROSE_ATTEMPTS,
    PROSE_INSTRUCTION,
    bind_or_downgrade,
    canonical_turn,
    clarification_turn,
    mint_claims,
    write_prose,
)
from src.domain import canonical_strings as cs
from src.domain.diagnosis import AccessDenialDiagnosis, CannotConfirm, diagnose_access_denial
from src.domain.intent import FOLLOW_UP_RULE_ID
from src.domain.references import (
    asks_for_runbook,
    extract_access_denial_references,
    extract_follow_up_reference,
    extract_policy_references,
    in_input_order,
)
from src.domain.result import Ok, Result, is_failure
from src.domain.runbook import is_renderable, runbook_recommendation
from src.dto import AnswerDTO
from src.ports.outbound import IdGenPort, LlmProsePort, RunbookRegistryPort

INTENT = "diagnose_access_denial"


class AccessDenialHandler:
    def __init__(
        self,
        *,
        resolver: EntityResolver,
        assembler: EvidenceAssembler,
        prose: LlmProsePort,
        idgen: IdGenPort,
        runbooks: RunbookRegistryPort,
    ) -> None:
        self._resolver = resolver
        self._assembler = assembler
        self._prose = prose
        self._idgen = idgen
        self._runbooks = runbooks

    def __call__(self, turn: TurnInput) -> Result[TurnOutput]:
        resolution = self._resolve(turn)
        if is_failure(resolution):
            return resolution
        found = resolution.value
        # a policy the query names (policy#...) must exist too: never explain a denial by a
        # clause that is not in state (AD-7, Annex 12.3). A missing entity outranks a
        # clarification: no answer to the clarification could make the diagnosis proceed.
        missing = self._resolver.missing_policies(extract_policy_references(turn.query))
        if is_failure(missing):
            return missing
        unresolved = (*(found.refs if isinstance(found, Unresolved) else ()), *missing.value)
        if unresolved:
            message = cs.entity_not_found(in_input_order(turn.query, unresolved))
            return Ok(self._canonical(turn, "ENTITY_NOT_FOUND", message, "ENTITY_NOT_FOUND"))
        if isinstance(found, Ambiguous):
            return Ok(self._clarify(turn, cs.ambiguous_reference(found.ref)))
        if isinstance(found, MissingContext):
            return Ok(self._clarify(turn, cs.R_MISSING_REFERENCES))

        records = self._assembler.gather(found.user, found.model, turn.now)
        if is_failure(records):
            return records
        outcome = diagnose_access_denial(
            found.user, found.model, records.value.clauses, records.value.events, turn.now
        )
        entities = (found.user.id, found.model.id)
        if isinstance(outcome, CannotConfirm):
            message = cs.cannot_confirm(outcome.checked)
            return Ok(
                self._canonical(
                    turn, "CANNOT_CONFIRM", message, "CANNOT_CONFIRM", outcome, entities
                )
            )
        return self._diagnose(turn, outcome, entities)

    # -- reference extraction + resolution -----------------------------------------------------
    def _resolve(
        self, turn: TurnInput
    ) -> Result[Resolved | Unresolved | Ambiguous | MissingContext | None]:
        if turn.decision.matched_rule_id == FOLLOW_UP_RULE_ID:
            ref = extract_follow_up_reference(turn.query)
            if ref is None:
                return Ok(MissingContext())
            return self._resolver.resolve_follow_up(ref, turn.context.resolved_entities)
        refs = extract_access_denial_references(turn.query)
        if refs is None:
            return Ok(MissingContext())
        return self._resolver.resolve_user_and_model(refs.user, refs.model)

    # -- the cited diagnosis ---------------------------------------------------------------------
    def _diagnose(
        self, turn: TurnInput, diagnosis: AccessDenialDiagnosis, entities: tuple[str, ...]
    ) -> Result[TurnOutput]:
        downgraded = bind_or_downgrade(turn, INTENT, diagnosis.claims, diagnosis.evidence, entities)
        if downgraded is not None:
            return Ok(downgraded)  # an unbound claim never renders (FR-13): no LLM, no claim id
        prose = self._write_prose(diagnosis)
        if is_failure(prose):
            return prose
        # ids are minted only once the turn can no longer fail on the LLM, so a rejected or
        # unavailable writer never leaves gaps in the claim id sequence
        runbook = self._runbook(turn, diagnosis)
        if is_failure(runbook):
            return runbook
        claims = mint_claims(self._idgen, diagnosis.claims)
        if is_failure(claims):
            return claims
        chain = ["observation", "evidence", "diagnosis"]
        if runbook.value is not None:
            chain.append("recommendation")  # annex 12.6: attached only when the query asks for it
        answer = AnswerDTO(
            answer_id=turn.answer_id,
            session_id=turn.session_id,
            query=turn.query,
            intent=INTENT,
            answer_chain=chain,
            diagnosis_class=diagnosis.diagnosis_class,
            claims=claims.value,
            evidence=list(diagnosis.evidence),
            recommendation=runbook.value,
            prose=prose.value,
        )
        return Ok(TurnOutput(answer, resolved_entities=entities))

    def _runbook(self, turn: TurnInput, diagnosis: AccessDenialDiagnosis) -> Result[dict | None]:
        """The registered runbook of the diagnosis class, only when the query asks for one (D-2).

        The template is keyed by the diagnosis class (I2-48). A class with no renderable template
        attaches nothing; a provider failure aborts the turn (AD-12).
        """
        if not asks_for_runbook(turn.query):
            return Ok(None)
        found = self._runbooks.get(diagnosis.diagnosis_class)
        if is_failure(found):
            return found
        if found.value is None or not is_renderable(found.value):
            return Ok(None)
        return Ok(runbook_recommendation(found.value))

    def _write_prose(self, diagnosis: AccessDenialDiagnosis) -> Result[str]:
        return write_prose(self._prose, diagnosis.evidence, diagnosis.fact_tokens)

    # -- canonical outcomes (never consult the LLM) ----------------------------------------------
    @staticmethod
    def _canonical(
        turn: TurnInput,
        code: str,
        message: str,
        stored: str,
        kept: CannotConfirm | None = None,
        entities: tuple[str, ...] = (),
    ) -> TurnOutput:
        evidence = kept.evidence if kept is not None else None
        return canonical_turn(
            turn, INTENT, code, message, stored=stored, kept_evidence=evidence, entities=entities
        )

    @staticmethod
    def _clarify(turn: TurnInput, reason: str) -> TurnOutput:
        return clarification_turn(turn, reason)


__all__ = ["INTENT", "PROSE_ATTEMPTS", "PROSE_INSTRUCTION", "AccessDenialHandler"]
