"""Gate tokens that cannot be guessed (story 2.2, IR-06, docs/impl2-rules.md).

``SecureTokenIdGen`` wraps the deterministic generator: every kind but the gate token is delegated,
so the ids of answers, claims and audit rows stay reproducible (FR-14), while a token is ``gt-``
plus ``secrets.token_hex(16)``, which is exactly the ``GateToken`` pattern and never a sequence a
previous run could predict. It lives apart from ``sim/idgen_adapter.py`` on purpose: that module is
asserted to hold no randomness at all.
"""

from __future__ import annotations

import secrets

from src.domain.result import Ok, Result
from src.ports.outbound import IdGenPort


class SecureTokenIdGen(IdGenPort):
    def __init__(self, inner: IdGenPort) -> None:
        self._inner = inner

    def new_id(self, kind: str) -> Result[str]:
        if kind == "gate_token":
            return Ok(f"gt-{secrets.token_hex(16)}")
        return self._inner.new_id(kind)
