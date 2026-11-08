"""Internal port for the Module-12-OWNED proposals (AD-3, AD-4, AD-6, contracts section 5 I9, I21).

Story 2.2 only adds: a dry-run inserts one proposal in state ``dry_run`` together with its snapshot
(the selector and the affected items) and its gate token. Reads and the later states belong to the
confirmation and dispatch stories. Every operation returns a typed ``Result`` (AD-12); when the
application already holds a unit of work the insert joins it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import ProposalDTO


class ProposalStorePort(ABC):
    @abstractmethod
    def add(self, proposal: ProposalDTO, created_at: str) -> Result[None]:
        """Insert a ``dry_run`` proposal whole, or nothing; a duplicate token is a failure."""

    @abstractmethod
    def highest_counters(self) -> Result[dict[str, int]]:
        """Highest stored numeric suffix for the ``proposal`` id kind (E43)."""
