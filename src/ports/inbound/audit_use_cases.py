"""Inbound port: the per-session audit page the REST adapter drives (contracts.md section 2).

``get_audit_page`` is read-only and is not itself audited (Q3). It returns a typed ``Result``
whose failures are catalog errors (``PAGINATION_INVALID``, ``SESSION_NOT_FOUND``,
``PROVIDER_UNAVAILABLE``). No framework object appears in a signature (R4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import GetAuditPageResponse


class AuditUseCases(ABC):
    @abstractmethod
    def get_audit_page(
        self, session_id: str, page: int, page_size: int
    ) -> Result[GetAuditPageResponse]:
        """``GET /api/v1/sessions/{sid}/audit`` - ascending by ``(timestamp, audit_id)``."""
