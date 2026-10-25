"""Provider reads for the access-denial diagnosis (AD-1: read-only, AD-12: all or nothing).

Fetches the policy clauses of the model and the user's recent ``access_denied`` events. Any
provider failure aborts the turn: a diagnosis is never built from partial evidence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.domain.instants import add_seconds
from src.domain.result import Failure, Ok, Result, is_failure
from src.dto import (
    AccessPolicyClauseDTO,
    ClockReadDTO,
    ModelCatalogEntryDTO,
    OperationalEventDTO,
    UserRecordDTO,
)
from src.ports.outbound import EventStorePort, EventWindow, PolicyPort

LOOK_BACK_SECONDS = 30 * 24 * 3600  # events of the last 30 days (story 1.3, D3)
_END_PAD_SECONDS = 0.001  # the window is half-open: include an event stamped exactly "now"


@dataclass(frozen=True)
class DenialRecords:
    clauses: tuple[AccessPolicyClauseDTO, ...]
    events: tuple[OperationalEventDTO, ...]


class EvidenceAssembler:
    def __init__(self, *, policy: PolicyPort, events: EventStorePort) -> None:
        self._policy = policy
        self._events = events

    def gather(
        self, user: UserRecordDTO, model: ModelCatalogEntryDTO, now: ClockReadDTO
    ) -> Result[DenialRecords]:
        clauses = self._policy.for_model(model.id)
        if is_failure(clauses):
            return clauses
        try:
            window = EventWindow(
                add_seconds(now.instant, -LOOK_BACK_SECONDS),
                add_seconds(now.instant, _END_PAD_SECONDS),
            )
        except (OverflowError, ValueError) as exc:  # a clock at the edge of the calendar
            return Failure("PROVIDER_UNAVAILABLE", observed=(f"event window: {exc}",))
        events = self._events.query(user.id, "access_denied", window)
        if is_failure(events):
            return events
        return Ok(DenialRecords(tuple(clauses.value), tuple(events.value)))

    def missing_policies(self, refs: Sequence[str]) -> Result[tuple[str, ...]]:
        """The ``policy#...`` references that are not in state, in input order.

        A malformed id is a miss ("no such clause"); a provider failure aborts the turn.
        """
        missing: list[str] = []
        for ref in refs:
            found = self._policy.get(ref)
            if is_failure(found):
                if found.code.startswith("VALIDATION_"):
                    missing.append(ref)
                    continue
                return found
            if found.value is None:
                missing.append(ref)
        return Ok(tuple(missing))


__all__ = ["LOOK_BACK_SECONDS", "DenialRecords", "EvidenceAssembler"]
