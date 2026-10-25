"""The access-denial diagnoser (story 1.3, S1): the first end-to-end intent handler.

Order of a turn: extract the references -> resolve them exactly (AD-7) -> read the policy and
events -> diagnose in the pure domain (AD-2) -> mint claim ids (OP-13) -> ask the LLM for prose
once, guarded, with one retry (AD-8). Unresolved references and unconfirmable denials are
canonical outcomes that never reach the LLM; any provider failure aborts the turn (AD-12).
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
from src.application.pipeline import CLARIFICATION_INTENT, TurnInput, TurnOutput
from src.domain import canonical_strings as cs
from src.domain.diagnosis import AccessDenialDiagnosis, CannotConfirm, diagnose_access_denial
from src.domain.intent import FOLLOW_UP_RULE_ID
from src.domain.prose_guard import scan_prose
from src.domain.references import extract_access_denial_references, extract_follow_up_reference
from src.domain.result import Failure, Ok, Result, is_failure
from src.dto import AnswerDTO, ClaimDTO, ProsePromptDTO
from src.ports.inbound import CanonicalOutcome
from src.ports.outbound import IdGenPort, LlmProsePort

INTENT = "diagnose_access_denial"
PROSE_ATTEMPTS = 2  # the first try plus one retry (AD-8)
PROSE_INSTRUCTION = (
    "Write one or two neutral sentences that connect the evidence sections below. "
    "Do not name any user, model, role, policy, rule, event, time or reason: "
    "the structured claims already carry every fact."
)


class AccessDenialHandler:
    def __init__(
        self,
        *,
        resolver: EntityResolver,
        assembler: EvidenceAssembler,
        prose: LlmProsePort,
        idgen: IdGenPort,
    ) -> None:
        self._resolver = resolver
        self._assembler = assembler
        self._prose = prose
        self._idgen = idgen

    def __call__(self, turn: TurnInput) -> Result[TurnOutput]:
        resolution = self._resolve(turn)
        if is_failure(resolution):
            return resolution
        found = resolution.value
        if isinstance(found, Unresolved):
            message = cs.entity_not_found(found.refs)
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
        claims: list[ClaimDTO] = []
        for draft in diagnosis.claims:
            claim_id = self._idgen.new_id("claim")
            if is_failure(claim_id):
                return claim_id
            claims.append(
                ClaimDTO(
                    claim_id=claim_id.value, text=draft.text, claim_citations=list(draft.citations)
                )
            )
        prose = self._write_prose(diagnosis)
        if is_failure(prose):
            return prose
        answer = AnswerDTO(
            answer_id=turn.answer_id,
            session_id=turn.session_id,
            query=turn.query,
            intent=INTENT,
            answer_chain=["observation", "evidence", "diagnosis"],
            diagnosis_class=diagnosis.diagnosis_class,
            claims=claims,
            evidence=list(diagnosis.evidence),
            prose=prose.value,
        )
        return Ok(TurnOutput(answer, resolved_entities=entities))

    def _write_prose(self, diagnosis: AccessDenialDiagnosis) -> Result[str]:
        prompt = ProsePromptDTO(
            evidence_sections=[entry.snippet for entry in diagnosis.evidence],
            instruction=PROSE_INSTRUCTION,
        )
        leaked: list[str] = []
        for _ in range(PROSE_ATTEMPTS):
            written = self._prose.compose(prompt)
            if is_failure(written):
                return written  # an unavailable writer is not retried
            leaked = scan_prose(written.value, diagnosis.fact_tokens)
            if not leaked:
                return written
        return Failure("LLM_PROSE_REJECTED", observed=tuple(leaked))

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
        evidence = list(kept.evidence) if kept is not None else []
        chain = ["observation", "evidence"] if kept is not None else ["observation"]
        answer = AnswerDTO(
            answer_id=turn.answer_id,
            session_id=turn.session_id,
            query=turn.query,
            intent=INTENT,
            answer_chain=chain,
            canonical=stored,
            claims=[],
            evidence=evidence,
            prose=message,
        )
        return TurnOutput(
            answer, canonical=CanonicalOutcome(code, message), resolved_entities=entities
        )

    @staticmethod
    def _clarify(turn: TurnInput, reason: str) -> TurnOutput:
        message = cs.clarification(reason)
        answer = AnswerDTO(
            answer_id=turn.answer_id,
            session_id=turn.session_id,
            query=turn.query,
            intent=CLARIFICATION_INTENT,
            answer_chain=["observation"],
            canonical="CLARIFICATION",
            claims=[],
            evidence=[],
            prose=message,
        )
        return TurnOutput(answer, canonical=CanonicalOutcome("CLARIFICATION_REQUIRED", message))


__all__ = ["INTENT", "PROSE_ATTEMPTS", "PROSE_INSTRUCTION", "AccessDenialHandler"]
