"""Inbound port: ``POST /api/v1/destructive/proposals`` (contracts ``post_confirm``, story 2.3).

The confirmation is a distinct request that carries only ``{proposal_id, gate_token}``: no identity,
no role, no session. Until the executor exists (story 2.4) a successful confirmation answers the
proposal in ``confirmed``. A failure is a typed catalog error; ``CONFIRMATION_STALE`` carries the
delta in its message and its ``observed`` lines. No framework object appears here (R4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import ProposalDTO


class ConfirmUseCases(ABC):
    @abstractmethod
    def post_confirm(self, proposal_id: str, gate_token: str) -> Result[ProposalDTO]:
        """Confirm a ``dry_run`` proposal, or answer the persisted one on an identical replay."""
