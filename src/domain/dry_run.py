"""Pure dry-run rules (story 2.2, FR-09, AD-4, AD-6): the selector, the items and the summary.

Given an action and a resolved target, decide *which provider query* enumerates the affected items,
*which items* count and what each one's status is, and *how the impact reads* to the operator.
Nothing here resolves an entity, reads the clock or touches state: the application ring feeds it
records, and the selector it builds is persisted and re-executed at confirmation, never re-derived
from the query text (AD-6, contracts L1).

The status filter comes from the action: ``cancel_jobs`` acts on ``running`` jobs ("active") and
``delete_jobs`` on ``pending`` ones (story 2.2 D3). A single ``job`` target is selected by id, with
no status filter, so a job already in a terminal status is listed as not actionable (D55).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.domain.instants import add_seconds
from src.domain.safety import JOB_VERBS, TargetKind
from src.dto import ActionVerb, AffectedItemDTO, JobRecordDTO, NodeRecordDTO, SelectorDTO

JOBS_PORT = "jobs_port.select"  # the only two values the proposals table allows (E39)
NODES_PORT = "nodes_port.select"
FILTER_METHOD = "filter"  # the Selector.method the simulated providers understand

# the status a job action selects (D3); "active" means running (docs/impl2-rules.md)
ACTION_STATUS: dict[ActionVerb, str] = {"cancel_jobs": "running", "delete_jobs": "pending"}
_LIVE_JOB = frozenset({"pending", "running"})
_ADJECTIVE = {"running": "active", "pending": "pending"}
_PAST = {
    "cancel_jobs": "terminated",
    "delete_jobs": "deleted",
    "cordon_node": "cordoned",
    "drain_node": "drained",
}
EMPTY_SUMMARY = "0 affected items"

Record = JobRecordDTO | NodeRecordDTO


@dataclass(frozen=True)
class Selection:
    """The provider query of a dry-run: the port operation it names and its filter parameters."""

    method: str  # JOBS_PORT or NODES_PORT, what is persisted
    params: dict

    def persisted(self) -> SelectorDTO:
        """The selector as it is stored and returned (``DryRunSnapshot.selector``)."""
        return SelectorDTO(method=self.method, params=self.params)

    def query(self) -> SelectorDTO:
        """The query the port runs; re-executing a stored selector rebuilds exactly this."""
        return SelectorDTO(method=FILTER_METHOD, params=self.params)


def reexecution_query(stored: SelectorDTO) -> SelectorDTO:
    """The port query for a stored selector (its params; the method names the port operation)."""
    return SelectorDTO(method=FILTER_METHOD, params=stored.params)


def _one_or_many(keys: Sequence[str]) -> str | list[str]:
    return keys[0] if len(keys) == 1 else list(keys)


def build_selector(action: ActionVerb, kind: TargetKind | None, keys: Sequence[str]) -> Selection:
    """The selector for ``action`` aimed at ``keys`` of ``kind`` (``None``: the whole fleet)."""
    if action in JOB_VERBS:
        status = ACTION_STATUS[action]
        if kind is None:
            return Selection(JOBS_PORT, {"status": status})
        if kind == "group":
            return Selection(JOBS_PORT, {"group_id": _one_or_many(keys), "status": status})
        if kind == "job":
            return Selection(JOBS_PORT, {"id": _one_or_many(keys)})
    elif kind is None:
        return Selection(NODES_PORT, {})
    elif kind == "node":
        return Selection(NODES_PORT, {"node_ids": list(keys)})
    raise ValueError(f"{action} cannot act on a {kind} target")  # the caller checks the pair first


def _is_actionable(record: Record) -> bool:
    if isinstance(record, JobRecordDTO):
        return record.status in _LIVE_JOB
    return record.status != "fault"  # a node in fault is already out of service


def enumerate_items(records: Sequence[Record]) -> list[AffectedItemDTO]:
    """One item per record, by key, each with its own status and whether it is actionable."""
    return [
        AffectedItemDTO(
            key=record.id,
            actionable=_is_actionable(record),
            actionable_field="status",
            actionable_value=record.status,
        )
        for record in sorted(records, key=lambda r: r.id)
    ]


def confirmation_enabled(items: Sequence[AffectedItemDTO]) -> bool:
    """Confirmation needs at least one actionable item (contracts Q-fail)."""
    return any(item.actionable for item in items)


def impact_summary(action: ActionVerb, selection: Selection, records: Sequence[Record]) -> str:
    """What the action would do, in one sentence; only actionable records count."""
    actionable = [r for r in records if _is_actionable(r)]
    if not actionable:
        return EMPTY_SUMMARY
    count = len(actionable)
    if action in JOB_VERBS:
        adjective = _ADJECTIVE.get(str(selection.params.get("status", "")), "")
        noun = f"{adjective} job" if adjective else "job"
        nodes = sorted(
            {
                r.node.removeprefix("node#")
                for r in actionable
                if isinstance(r, JobRecordDTO) and r.node
            }
        )
        where = f" across nodes {', '.join(nodes)}" if nodes else ""
    else:
        noun, where = "node", ""
    plural = noun if count == 1 else f"{noun}s"
    return f"{count} {plural} will be {_PAST[action]}{where}"


def token_expiry(snapshot_timestamp: str, ttl_seconds: int) -> str:
    """When the gate token lapses: the snapshot instant plus the lifetime, never a confirm time."""
    return add_seconds(snapshot_timestamp, ttl_seconds)
