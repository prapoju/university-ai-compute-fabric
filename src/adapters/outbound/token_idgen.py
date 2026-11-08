"""Ids that cannot be guessed: the gate token and the proposal id (IR-06, impl2-rules).

``SecureTokenIdGen`` wraps the deterministic generator and delegates every kind but these two, so
the ids of answers, claims and audit rows stay reproducible (FR-14). A gate token is ``gt-`` plus
``secrets.token_hex(16)`` and a proposal id is ``prop-`` plus ``secrets.token_hex(8)``: the shapes
of the contract (``GateToken``, ``IdString``), never a sequence.

The proposal id has to be secret too: ``GET /destructive/proposals/{pid}`` returns the proposal with
its token and the confirmation asks for nothing but the id and the token, so with sequential ids
anyone could read a token and confirm (story 2.4 review P-1). It lives apart from
``sim/idgen_adapter.py`` on purpose: that module is asserted to hold no randomness at all.
"""

from __future__ import annotations

import secrets

from src.domain.result import Ok, Result
from src.ports.outbound import IdGenPort

# kind -> (prefix, random bytes): hex width 2 * bytes, as the IdString and GateToken patterns say
_UNGUESSABLE: dict[str, tuple[str, int]] = {"gate_token": ("gt-", 16), "proposal": ("prop-", 8)}


class SecureTokenIdGen(IdGenPort):
    def __init__(self, inner: IdGenPort) -> None:
        self._inner = inner

    def new_id(self, kind: str) -> Result[str]:
        if kind in _UNGUESSABLE:
            prefix, size = _UNGUESSABLE[kind]
            return Ok(f"{prefix}{secrets.token_hex(size)}")
        return self._inner.new_id(kind)
