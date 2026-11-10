"""Inbound port: the dry-run of a destructive request (contracts.md section 5, story 2.2).

``post_dry_run`` is ``POST /api/v1/destructive/dry-runs``. ``dry_run_request`` is the same use case
for a request the chat already parsed (it can name a fleet scope, which has no ``target_refs``).
Both answer a stored ``dry_run`` proposal, or a canonical outcome when the request needs a
clarification or names nothing that exists, or a typed failure. No framework object (R4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.result import Result
from src.domain.safety import DestructiveRequest
from src.dto import ProposalDTO
from src.ports.inbound.session_use_cases import CanonicalOutcome


@dataclass(frozen=True)
class DryRunOutcome:
    """The stored proposal plus what a chat reply shows next to it."""

    proposal: ProposalDTO
    impact_summary: str
    token_expires_at: str
    confirmation_enabled: bool


class DestructiveUseCases(ABC):
    @abstractmethod
    def post_dry_run(
        self, query_text: str, action: str, target_refs: list[str], session_id: str
    ) -> Result[DryRunOutcome | CanonicalOutcome]:
        """``POST /api/v1/destructive/dry-runs``."""

    @abstractmethod
    def dry_run_request(
        self, session_id: str, request: DestructiveRequest
    ) -> Result[DryRunOutcome | CanonicalOutcome]:
        """The dry-run of a destructive request the chat parsed (a named target or a fleet)."""
