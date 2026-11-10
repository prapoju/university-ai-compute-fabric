"""Inbound port: reading a proposal and re-dispatching a failed one (contracts ``get_proposal`` and
``post_re_dispatch``, story 2.4).

A re-dispatch is a **new** proposal through the full gate (a fresh dry-run, a new token and its own
confirmation); it never applies anything and never reuses the parent's token (PD-6, AD-3). No
framework object appears here (R4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import ProposalDTO
from src.ports.inbound.destructive_use_cases import DryRunOutcome
from src.ports.inbound.session_use_cases import CanonicalOutcome


class ProposalUseCases(ABC):
    @abstractmethod
    def get_proposal(self, proposal_id: str) -> Result[ProposalDTO]:
        """``GET /api/v1/destructive/proposals/{pid}`` - read-only."""

    @abstractmethod
    def post_re_dispatch(
        self, parent_proposal_id: str, query_text: str, action: str, target_refs: list[str]
    ) -> Result[DryRunOutcome | CanonicalOutcome]:
        """``POST /api/v1/destructive/proposals/{pid}/re-dispatches``."""
