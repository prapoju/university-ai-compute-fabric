"""Pure execution rules (story 2.4, FR-10, AD-3, AD-15; contracts ``executor_post_proposal``).

What each verb does to a record, whether an item is still in the state its snapshot promised,
how a result is classified against the scope and whether the executor answered in time. Nothing
here reads the clock or a store: the simulated executor and the dispatcher feed it values.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import Literal

from src.domain.instants import parse_instant
from src.dto import ActionVerb, AffectedItemDTO, JobRecordDTO, NodeRecordDTO

EXECUTOR_TIMEOUT_SECONDS = 5  # D31: after this the dispatcher marks the proposal failed
Record = JobRecordDTO | NodeRecordDTO
Classification = Literal["applied", "partial", "failed"]


def expected_keys(items: Sequence[AffectedItemDTO]) -> list[str]:
    """The keys the executor is asked to apply: the actionable items, in snapshot order."""
    return [item.key for item in items if item.actionable]


def still_promised(item: AffectedItemDTO, record: Record | None) -> bool:
    """The record is still in the state its snapshot item promised (the window of review D-1)."""
    return record is not None and item.actionable and record.status == item.actionable_value


def effect(verb: ActionVerb, record: Record) -> Record | None:
    """The record after ``verb``; ``None`` removes it (``delete_jobs``)."""
    if verb == "cancel_jobs":
        return record.model_copy(update={"status": "cancelled"})
    if verb == "delete_jobs":
        return None
    if verb == "cordon_node":
        return record.model_copy(update={"cordoned": True})
    return record.model_copy(update={"cordoned": True, "health": "draining"})  # drain_node


def classify(expected: Sequence[str], applied: Sequence[str]) -> Classification:
    """``applied`` when exactly the expected keys were applied, once each; fewer is ``partial``;
    anything outside the scope, or a key twice, is ``failed`` (never a success past the scope)."""
    wanted = set(expected)
    if len(set(applied)) != len(applied) or not set(applied) <= wanted:
        return "failed"
    return "applied" if set(applied) == wanted else "partial"


def within_limit(dispatched_at: str, returned_at: str) -> bool:
    """The executor answered in time: ``<= 5.000 s`` on the clock (the boundary is accepted)."""
    elapsed = parse_instant(returned_at) - parse_instant(dispatched_at)
    return elapsed <= timedelta(seconds=EXECUTOR_TIMEOUT_SECONDS)
