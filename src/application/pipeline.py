"""The answer pipeline: from a routing decision to an ``Answer`` (walking-skeleton seam).

``classify`` (domain) decides *which* intent; this module decides *what the turn returns*:

* a clarification is a canonical outcome (HTTP 200 ``ErrorBody`` on the wire, D58) and is also
  stored as an ``Answer`` with ``canonical = CLARIFICATION`` so ``GET`` shows the turn;
* a routed intent with a registered handler is delegated to it - stories 1.3 (access denial),
  3.1 (schedule/window) and 4.1 (anti-fabrication) register theirs here, no other code changes;
* a routed intent with **no** handler yet returns an observation-only ``Answer`` (the chain stops
  at ``observation``), which is exactly the walking-skeleton behaviour of story 1.2.

Pure application ring: it imports ports and domain only (R3), never an adapter.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from src.domain import canonical_strings as cs
from src.domain.intent import Clarify, Routed
from src.domain.result import Ok, Result
from src.dto import AnswerDTO, ClockReadDTO, SessionContextDTO
from src.ports.inbound import CanonicalOutcome

CLARIFICATION_INTENT = "clarification"
OBSERVATION_ROUTED = "Routed to {intent} by {rule}; the diagnosis is not available yet."


@dataclass(frozen=True)
class TurnInput:
    """Everything a handler may use for one turn (one ``now`` per request)."""

    session_id: str
    answer_id: str
    query: str
    now: ClockReadDTO
    decision: Routed | Clarify
    context: SessionContextDTO


@dataclass(frozen=True)
class TurnOutput:
    answer: AnswerDTO
    canonical: CanonicalOutcome | None = None  # set => the wire response is the 200 ErrorBody
    resolved_entities: tuple[str, ...] = ()  # entities this turn added to the session context


IntentHandler = Callable[[TurnInput], Result[TurnOutput]]


class AnswerPipeline:
    def __init__(self, handlers: Mapping[str, IntentHandler] | None = None) -> None:
        self._handlers: dict[str, IntentHandler] = dict(handlers or {})

    def register(self, intent_code: str, handler: IntentHandler) -> None:
        """Plug in the diagnoser for ``intent_code`` (replaces the observation-only answer)."""
        self._handlers[intent_code] = handler

    def respond(self, turn: TurnInput) -> Result[TurnOutput]:
        decision = turn.decision
        if isinstance(decision, Clarify):
            return Ok(self._clarification(turn, decision))
        handler = self._handlers.get(decision.intent_code)
        if handler is not None:
            return handler(turn)
        return Ok(self._observation_only(turn, decision))

    @staticmethod
    def _clarification(turn: TurnInput, decision: Clarify) -> TurnOutput:
        message = cs.clarification(decision.reason)
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

    @staticmethod
    def _observation_only(turn: TurnInput, decision: Routed) -> TurnOutput:
        answer = AnswerDTO(
            answer_id=turn.answer_id,
            session_id=turn.session_id,
            query=turn.query,
            intent=decision.intent_code,
            answer_chain=["observation"],
            claims=[],
            evidence=[],
            prose=OBSERVATION_ROUTED.format(
                intent=decision.intent_code, rule=decision.matched_rule_id
            ),
        )
        return TurnOutput(answer)
