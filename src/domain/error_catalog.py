"""The typed error catalog (contracts.md section 4) as data.

One row per ``ErrorCode``: HTTP status, retryability and the human-readable message template.
Pure and framework-free, so the application ring can describe failures and any driving adapter
(REST today) can render them without re-deriving the rules.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain import canonical_strings as cs
from src.domain.result import Failure


@dataclass(frozen=True)
class ErrorSpec:
    status: int
    retryable: bool
    template: str


_PROVIDER = ErrorSpec(503, True, cs.S_PUA)

CATALOG: dict[str, ErrorSpec] = {
    "VALIDATION_EMPTY_QUERY": ErrorSpec(
        400, False, "Query must contain between 1 and 1000 characters; received 0."
    ),
    "VALIDATION_QUERY_TOO_LONG": ErrorSpec(
        400, False, "Query exceeds 1000 characters; received {n}."
    ),
    "VALIDATION_MALFORMED_BODY": ErrorSpec(
        400, False, "Request body does not match schema {schema_id}."
    ),
    "VALIDATION_BAD_ENTITY_TYPE": ErrorSpec(
        400, False, "Unknown entity type {value}; expected one of {enum}."
    ),
    "VALIDATION_BAD_ACTION": ErrorSpec(
        400,
        False,
        "Unknown action {value}; "
        "expected one of {{delete_jobs,cancel_jobs,cordon_node,drain_node}}.",
    ),
    "VALIDATION_BAD_ID_KIND": ErrorSpec(
        400, False, "Unknown id kind {value}; expected one of {enum}."
    ),
    "PAGINATION_INVALID": ErrorSpec(
        400, False, "Invalid pagination: page_size {v} exceeds cap 100."
    ),
    "SESSION_NOT_FOUND": ErrorSpec(404, False, "Session {sid} not found."),
    "SESSION_EXPIRED": ErrorSpec(410, False, "Session {sid} expired after 30 minutes idle."),
    "ENTITY_NOT_FOUND": ErrorSpec(404, False, cs.S_ENF),
    "CANNOT_CONFIRM": ErrorSpec(200, False, cs.S_CNC),
    "CLARIFICATION_REQUIRED": ErrorSpec(200, False, cs.S_CLR),
    "INTENT_NOT_SUPPORTED": ErrorSpec(200, False, cs.clarification("intent not supported")),
    "PROVIDER_UNAVAILABLE": _PROVIDER,
    "CLOCK_UNAVAILABLE": _PROVIDER,
    "LLM_UNAVAILABLE": _PROVIDER,
    "LLM_PROSE_REJECTED": _PROVIDER,
    "AUDIT_WRITE_FAILED": ErrorSpec(500, True, "Audit write failed for tool call {tool_call_id}."),
    "ACTION_REFUSED": ErrorSpec(200, False, cs.S_ARF),
    "PROPOSAL_NOT_FOUND": ErrorSpec(404, False, "Proposal {pid} not found."),
    "PROPOSAL_STATE_INVALID": ErrorSpec(
        409, False, "Proposal {pid} in state {state}; {action} not permitted."
    ),
    "GATE_TOKEN_INVALID": ErrorSpec(403, False, "Gate token invalid for proposal {pid}."),
    "CONFIRMATION_STALE": ErrorSpec(409, False, "Snapshot stale: {delta}."),
    "DRY_RUN_EMPTY_SET": ErrorSpec(409, False, "0 affected items; confirmation disabled."),
    "CONFIRMATION_CONFLICT": ErrorSpec(
        409, False, "Proposal {pid} already {state}; confirmation rejected."
    ),
    "EXECUTOR_UNAVAILABLE": _PROVIDER,
    "EXECUTOR_PARTIAL_APPLY": ErrorSpec(
        502, False, "Executor applied {applied_count} of {n} items."
    ),
    "EXECUTOR_DUPLICATE_APPLY": ErrorSpec(409, False, "Duplicate apply for proposal {pid}."),
    "RUNBOOK_NOT_FOUND": ErrorSpec(404, False, cs.S_RBX),
    "RUNBOOK_TEMPLATE_EMPTY": ErrorSpec(
        422, False, "Runbook template {template_id} rejected: steps list is empty."
    ),
    "RUNBOOK_TEMPLATE_UNSOURCED": ErrorSpec(
        422,
        False,
        "Runbook template {template_id} rejected: "
        "physical-intervention steps lack an approved source.",
    ),
}


def spec_for(code: str) -> ErrorSpec:
    return CATALOG[code]


def render(code: str, **params: object) -> str:
    """Fill the message template of ``code``; a missing parameter is a loud ``ValueError``."""
    template = CATALOG[code].template
    try:
        return template.format(**params)
    except KeyError as exc:
        raise ValueError(f"missing template parameter {exc.args[0]!r} for {code}") from exc


def fail(code: str, *, observed: tuple[str, ...] = (), **params: object) -> Failure:
    """A :class:`Failure` that already carries its rendered contract message."""
    return Failure(code, observed=observed, message=render(code, **params))
