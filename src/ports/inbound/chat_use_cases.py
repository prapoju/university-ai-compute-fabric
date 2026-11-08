"""Inbound port: ``POST /api/v1/copilot/chat`` (Annex 12.4, story 2.2).

One chat message opens a session, submits the query and, when it was a destructive request that was
refused, adds the dry-run of that request. The refusal is always first and always stored (D8).
No framework object appears here (R4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.result import Result
from src.dto import AnswerEnvelopeDTO
from src.ports.inbound.destructive_use_cases import DryRunOutcome
from src.ports.inbound.session_use_cases import CanonicalOutcome


@dataclass(frozen=True)
class ChatRefusal:
    """The canonical refusal and the dry-run that accompanies it."""

    refusal: CanonicalOutcome
    dry_run: DryRunOutcome


class ChatUseCases(ABC):
    @abstractmethod
    def chat(
        self, operator_role: str, query: str
    ) -> Result[AnswerEnvelopeDTO | CanonicalOutcome | ChatRefusal]:
        """Every outcome of a submitted query, plus the dry-run of a refused destructive request."""
