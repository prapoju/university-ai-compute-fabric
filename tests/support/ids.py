"""Deterministic id factory (test double for outbound port OP-13 `idgen_port`).

Contract refs:
  - ``contracts.md`` §0.1 `IdKind` and `IdString`:
    ``sess|ans|clm|tc|aud|prop|evt``-``[0-9a-f]{16}``, ``gt-[0-9a-f]{32}``.
  - §0.1 note: ``evidence`` is intentionally **not** an `IdKind` (D67, X-02) — an
    `Evidence` row is keyed by ``(answer_id, citation_id)``.
  - §3 OP-13: ``new_id(kind) -> IdString``; "successive calls never return the same
    value"; "under seed, the sequence is fixed so FR-14 runs reproduce the same ids".

Every id in every test is minted here. No test may call ``uuid4``/``random`` (R2).
"""

from __future__ import annotations

import re

# (prefix, hex width) — §0.1 `IdString`
KIND_FORMAT: dict[str, tuple[str, int]] = {
    "session": ("sess-", 16),
    "answer": ("ans-", 16),
    "claim": ("clm-", 16),
    "tool_call": ("tc-", 16),
    "audit": ("aud-", 16),
    "proposal": ("prop-", 16),
    "gate_token": ("gt-", 32),
    "event": ("evt-", 16),
}

# §0.1 `IdKind` closed enum
ID_KINDS: tuple[str, ...] = tuple(KIND_FORMAT)

_ID_RE: dict[str, re.Pattern[str]] = {
    kind: re.compile(rf"^{re.escape(prefix)}[0-9a-f]{{{width}}}$")
    for kind, (prefix, width) in KIND_FORMAT.items()
}

# convenience: the literal §0.1 one-liner, for tests that want the raw pattern
ID_STRING_PATTERN = r"^(sess|ans|clm|tc|aud|prop|evt)-[0-9a-f]{16}$|^gt-[0-9a-f]{32}$"


def id_regex(kind: str) -> re.Pattern[str]:
    if kind not in _ID_RE:
        raise ValueError(f"unknown IdKind {kind!r}; expected one of {ID_KINDS}")
    return _ID_RE[kind]


def is_valid_id(value: object, kind: str) -> bool:
    """§0.1 `IdString` check for one kind."""
    return isinstance(value, str) and bool(id_regex(kind).match(value))


class IdFactory:
    """Seeded, monotonic-per-kind id source. Zero randomness."""

    def __init__(self, seed: int = 12) -> None:
        if seed < 0:
            raise ValueError("seed must be >= 0")
        self.seed = seed
        self._counters: dict[str, int] = {kind: seed for kind in ID_KINDS}

    def new_id(self, kind: str) -> str:
        """OP-13 ``new_id(kind)``. Unknown kind -> VALIDATION_BAD_ID_KIND analog."""
        if kind not in KIND_FORMAT:
            raise ValueError(f"VALIDATION_BAD_ID_KIND: {kind!r} not in {ID_KINDS}")
        prefix, width = KIND_FORMAT[kind]
        self._counters[kind] += 1
        return f"{prefix}{self._counters[kind]:0{width}x}"

    def session_id(self) -> str:
        return self.new_id("session")

    def answer_id(self) -> str:
        return self.new_id("answer")

    def claim_id(self) -> str:
        return self.new_id("claim")

    def tool_call_id(self) -> str:
        return self.new_id("tool_call")

    def audit_id(self) -> str:
        return self.new_id("audit")

    def proposal_id(self) -> str:
        return self.new_id("proposal")

    def gate_token(self) -> str:
        return self.new_id("gate_token")

    def event_id(self) -> str:
        return self.new_id("event")
