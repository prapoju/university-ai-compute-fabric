"""OP-13 ``idgen_port``: the only source of generated ids (contracts.md section 3.1, R2).

No component draws ids from ``uuid4``/``random`` directly. Under a seeded simulated adapter the
sequence is fixed, so FR-14 runs reproduce the same ids, and a restart never reissues an id that
is already persisted (E43).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result


class IdGenPort(ABC):
    @abstractmethod
    def new_id(self, kind: str) -> Result[str]:
        """A fresh ``IdString`` for ``kind`` (``session``, ``answer``, ...).

        A kind outside the ``IdKind`` enum is ``Failure("VALIDATION_BAD_ID_KIND")``.
        """
