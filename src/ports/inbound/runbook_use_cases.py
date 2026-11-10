"""Inbound port of ``get_runbook`` (contracts.md section 2, ``GET /api/v1/runbooks/{code}``)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import GetRunbookResponse


class RunbookUseCases(ABC):
    @abstractmethod
    def get_runbook(self, error_code: str) -> Result[GetRunbookResponse]:
        """The registered template for the exact ``error_code``: steps and provenance (AD-9)."""
