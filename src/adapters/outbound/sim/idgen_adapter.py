"""Seeded simulated ``idgen_port`` (OP-13): deterministic, monotonic, thread-safe.

Every id is a per-kind counter rendered in the contract's ``IdString`` format, so an identical
run reproduces identical ids (FR-14) and nothing in the system touches ``uuid``/``random`` (R2).
``from_counters`` seeds the counters above everything already persisted, so a restart on a file
database never reissues an id (E43).
"""

from __future__ import annotations

import threading
from collections.abc import Mapping

from src.domain.error_catalog import fail
from src.domain.result import Ok, Result
from src.ports.outbound import IdGenPort

# contracts.md section 0.1 IdString: kind -> (prefix, hex width)
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


class SimIdGen(IdGenPort):
    def __init__(self, counters: Mapping[str, int] | None = None) -> None:
        self._counters: dict[str, int] = {kind: 0 for kind in KIND_FORMAT}
        self._counters.update({k: v for k, v in (counters or {}).items() if k in KIND_FORMAT})
        self._lock = threading.Lock()

    @classmethod
    def from_counters(cls, highest: Mapping[str, int]) -> SimIdGen:
        """Continue after the highest numeric suffix already stored for each kind."""
        return cls(highest)

    def new_id(self, kind: str) -> Result[str]:
        if kind not in KIND_FORMAT:
            return fail("VALIDATION_BAD_ID_KIND", value=kind, enum=sorted(KIND_FORMAT))
        prefix, width = KIND_FORMAT[kind]
        with self._lock:
            self._counters[kind] += 1
            number = self._counters[kind]
        return Ok(f"{prefix}{number:0{width}x}")
