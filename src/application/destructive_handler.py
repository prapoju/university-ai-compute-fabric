"""The destructive-request refusal (story 2.1, Annex 12.4, AD-4, AD-11, NFR-8).

Order of a turn: read the verb and the target from the query (pure, ``domain.safety``) -> resolve
the target exactly through the read-only ports (AD-7) -> check the verb fits that kind of target
(contracts P3) -> answer the canonical ``Action refused.`` The refusal is a stored, audited
session turn; it creates no proposal row and mints no gate token (review D-1, I2-01), and it never
reaches the prose writer (AD-2, AD-8). The handler holds read-only ports only, so it cannot write
to simulated state at all (AD-1, AD-3).
"""

from __future__ import annotations

from src.application.entity_resolver import EntityResolver, Unresolved
from src.application.pipeline import TurnInput, TurnOutput
from src.application.turn_support import canonical_turn, clarification_turn
from src.domain import canonical_strings as cs
from src.domain.error_catalog import fail
from src.domain.intent import normalise_query
from src.domain.result import Ok, Result, is_failure
from src.domain.safety import INTENT_CODE, Compound, Fleet, accepts, parse_destructive

INTENT = INTENT_CODE


class DestructiveRefusalHandler:
    def __init__(self, *, resolver: EntityResolver) -> None:
        self._resolver = resolver

    def __call__(self, turn: TurnInput) -> Result[TurnOutput]:
        request = parse_destructive(normalise_query(turn.query))
        if request is None:  # routed here by the classifier, so a verb is there; stay safe anyway
            return Ok(clarification_turn(turn, cs.R_NO_INTENT))
        if isinstance(request, Compound):
            return Ok(clarification_turn(turn, request.reason))

        target = request.target
        entities: tuple[str, ...] = ()
        described = f"{request.verb} on the whole fleet"
        if not isinstance(target, Fleet):
            resolution = self._resolver.resolve_target(target.kind, target.token)
            if is_failure(resolution):
                return resolution  # a provider outage is never "not found" (AD-12)
            found = resolution.value
            if isinstance(found, Unresolved):
                message = cs.entity_not_found(found.refs)
                return Ok(canonical_turn(turn, INTENT, "ENTITY_NOT_FOUND", message))
            entities = (found.key,)
            described = f"{request.verb} on {found.key}"

        if not accepts(request.verb, target):
            return fail("VALIDATION_BAD_ACTION", value=described)
        return Ok(canonical_turn(turn, INTENT, "ACTION_REFUSED", cs.S_ARF, entities=entities))


__all__ = ["INTENT", "DestructiveRefusalHandler"]
