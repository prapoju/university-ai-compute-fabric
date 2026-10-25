"""Pure session rules (FR-01, FR-02, D51): query normalisation, idle expiry, empty context."""

from __future__ import annotations

import re
from datetime import timedelta

from src.domain.error_catalog import fail
from src.domain.instants import parse_instant
from src.domain.result import Ok, Result
from src.dto import SessionContextDTO

MAX_QUERY_CHARS = 1000
IDLE_LIMIT_MINUTES = 30

_OPERATOR_ROLE = re.compile(r"role-[a-z0-9_-]{1,32}")  # contracts.md section 0.1 OperatorRole


def is_valid_operator_role(role: str) -> bool:
    """``OperatorRole``: a synthetic ``role-...`` id (NFR-11); fullmatch so no newline slips in."""
    return _OPERATOR_ROLE.fullmatch(role) is not None


def normalise_query(text: str) -> Result[str]:
    """Trim once, then apply the emptiness and length tests to that same trimmed value (P1)."""
    trimmed = text.strip()
    if len(trimmed) == 0:
        return fail("VALIDATION_EMPTY_QUERY")
    if len(trimmed) > MAX_QUERY_CHARS:
        return fail("VALIDATION_QUERY_TOO_LONG", n=len(trimmed))
    return Ok(trimmed)


def is_idle_expired(last_activity: str, now: str) -> bool:
    """True when the session has been idle for strictly more than 30 minutes."""
    idle = parse_instant(now) - parse_instant(last_activity)
    return idle > timedelta(minutes=IDLE_LIMIT_MINUTES)


def empty_context() -> SessionContextDTO:
    """A fresh, independent empty ``session.context``."""
    return SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[])
