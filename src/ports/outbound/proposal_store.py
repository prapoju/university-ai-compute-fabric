"""Internal port for the Module-12-OWNED proposals (AD-3, AD-4, AD-6, contracts section 5 I9, I21).

A dry-run inserts one proposal in state ``dry_run`` together with its snapshot (the selector and
the affected items) and its gate token (story 2.2). The confirmation reads it back and claims the
``dry_run -> confirmed`` transition (story 2.3); the dispatch states belong to story 2.4. Every
operation returns a typed ``Result`` (AD-12); when the application already holds a unit of work,
the insert and the claim join it.
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
    def get(self, proposal_id: str) -> Result[ProposalDTO | None]:
        """The stored proposal, rebuilt whole; a miss is ``Ok(None)``."""

    @abstractmethod
    def claim(self, proposal_id: str, gate_token: str, confirmed_at: str) -> Result[bool]:
        """The one conditional ``dry_run -> confirmed`` transition (AD-4, contracts claim).

        ``True`` when this call changed the row, ``False`` when the proposal is not in ``dry_run``
        or the token differs (another confirm won, or the token is wrong). It never raises for a
        lost race; the caller re-reads the proposal and decides.
        """

    @abstractmethod
    def highest_counters(self) -> Result[dict[str, int]]:
        """Highest stored numeric suffix for the ``proposal`` id kind (E43)."""
