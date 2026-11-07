"""Pieces every diagnoser shares: guarded prose, claim ids and the canonical turn shapes.

The LLM writes connective prose once per answer; the domain guard rejects any fact in it and the
turn retries once before failing with ``LLM_PROSE_REJECTED`` (AD-2, AD-8). Canonical outcomes
(clarification, ``ENTITY_NOT_FOUND``, ``CANNOT_CONFIRM``) are stored as turns and never consult the
LLM. An answer that cites an id outside its own evidence set never renders: it downgrades to
``CANNOT_CONFIRM`` before any prose is written or claim id minted (story 1.4, FR-13).
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from src.application.pipeline import CLARIFICATION_INTENT, TurnInput, TurnOutput
from src.domain import canonical_strings as cs
from src.domain.citations import is_bound
from src.domain.diagnosis import ClaimDraft
from src.domain.prose_guard import scan_prose
from src.domain.result import Failure, Ok, Result, is_failure
from src.dto import AnswerDTO, ClaimDTO, EvidenceDTO, ProsePromptDTO
from src.ports.inbound import CanonicalOutcome
from src.ports.outbound import IdGenPort, LlmProsePort

PROSE_ATTEMPTS = 2  # the first try plus one retry (AD-8)
PROSE_INSTRUCTION = (
    "Write one or two neutral sentences that connect the evidence sections below. "
    "Do not name any user, model, role, policy, rule, event, time or reason: "
    "the structured claims already carry every fact."
)


def write_prose(
    port: LlmProsePort, evidence: Sequence[EvidenceDTO], fact_tokens: Collection[str]
) -> Result[str]:
    """Prose that passes the guard, or the typed failure (an unavailable writer is not retried)."""
    prompt = ProsePromptDTO(
        evidence_sections=[entry.snippet for entry in evidence], instruction=PROSE_INSTRUCTION
    )
    leaked: list[str] = []
    for _ in range(PROSE_ATTEMPTS):
        written = port.compose(prompt)
        if is_failure(written):
            return written
        if not written.value.strip():
            leaked = ["<empty prose>"]  # nothing to connect the evidence: same as a rejection
            continue
        leaked = scan_prose(written.value, fact_tokens)
        if not leaked:
            return written
    return Failure("LLM_PROSE_REJECTED", observed=tuple(leaked))


def mint_claims(idgen: IdGenPort, drafts: Sequence[ClaimDraft]) -> Result[list[ClaimDTO]]:
    """Claim ids come only from OP-13, minted once the turn can no longer fail on the LLM."""
    claims: list[ClaimDTO] = []
    for draft in drafts:
        claim_id = idgen.new_id("claim")
        if is_failure(claim_id):
            return claim_id
        claims.append(
            ClaimDTO(
                claim_id=claim_id.value, text=draft.text, claim_citations=list(draft.citations)
            )
        )
    return Ok(claims)


def bind_or_downgrade(
    turn: TurnInput,
    intent: str,
    drafts: Sequence[ClaimDraft],
    evidence: Sequence[EvidenceDTO],
    entities: tuple[str, ...] = (),
) -> TurnOutput | None:
    """``None`` when every claim is bound to the evidence; otherwise the ``S_CNC`` turn.

    A claim that cites nothing is unbound too: it downgrades here instead of failing later in
    ``mint_claims`` on ``ClaimDTO``'s ``min_length=1``.

    The downgrade keeps the gathered evidence for audit, stores no claim and names what was
    checked: the evidence citation ids in ``position`` order (D2). A duplicated id is kept once
    (its first entry, positions renumbered), so the stored set still satisfies the ``evidence``
    primary key. It runs before the prose call, so an unbound answer spends no LLM call and no
    claim id.
    """
    if is_bound(drafts, evidence):
        return None
    kept: dict[str, EvidenceDTO] = {}
    for entry in sorted(evidence, key=lambda e: e.position):
        kept.setdefault(entry.citation_id, entry)
    renumbered = [
        entry.model_copy(update={"position": position})
        for position, entry in enumerate(kept.values())
    ]
    return canonical_turn(
        turn,
        intent,
        "CANNOT_CONFIRM",
        cs.cannot_confirm(list(kept)),
        stored="CANNOT_CONFIRM",
        kept_evidence=renumbered,
        entities=entities,
    )


def canonical_turn(
    turn: TurnInput,
    intent: str,
    code: str,
    message: str,
    *,
    stored: str | None = None,
    kept_evidence: Sequence[EvidenceDTO] | None = None,
    entities: tuple[str, ...] = (),
) -> TurnOutput:
    """A canonical response that is also stored as the turn (D58); evidence kept when given."""
    evidence = list(kept_evidence) if kept_evidence is not None else []
    answer = AnswerDTO(
        answer_id=turn.answer_id,
        session_id=turn.session_id,
        query=turn.query,
        intent=intent,
        answer_chain=["observation", "evidence"] if kept_evidence is not None else ["observation"],
        canonical=stored or code,
        claims=[],
        evidence=evidence,
        prose=message,
    )
    return TurnOutput(answer, canonical=CanonicalOutcome(code, message), resolved_entities=entities)


def clarification_turn(turn: TurnInput, reason: str) -> TurnOutput:
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
