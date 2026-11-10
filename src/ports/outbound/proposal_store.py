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
from src.dto import ExecutorResultDTO, ProposalDTO


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
    def begin_dispatch(self, proposal_id: str, at: str) -> Result[bool]:
        """The one conditional ``confirmed -> dispatched`` transition (contracts claim, C5).

        Run in the same transaction as ``claim``: together they are the contract's single commit
        of ``dry_run -> confirmed -> dispatched``. ``True`` when this call changed the row.
        """

    @abstractmethod
    def record_result(
        self, proposal_id: str, state: str, result: ExecutorResultDTO, at: str
    ) -> Result[bool]:
        """``dispatched -> executed | failed`` with the executor result (C6); ``True`` if changed"""

    @abstractmethod
    def mark_failed(self, proposal_id: str, at: str) -> Result[bool]:
        """``dispatched -> failed`` with no executor result (no answer in time)."""

    @abstractmethod
    def supersede(self, proposal_id: str, at: str) -> Result[bool]:
        """``failed -> superseded`` (C7); ``False`` when the proposal is not ``failed``."""

    @abstractmethod
    def highest_counters(self) -> Result[dict[str, int]]:
        """Highest stored numeric suffix for the ``proposal`` id kind (E43)."""
