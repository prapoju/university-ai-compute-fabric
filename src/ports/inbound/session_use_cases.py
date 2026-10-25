"""Inbound port: the session use cases the REST adapter drives (contracts.md section 2).

The router depends on this interface only. Operations return a typed ``Result`` whose failures
are catalog errors (``SESSION_NOT_FOUND``, ``VALIDATION_EMPTY_QUERY``, ...). No framework
object (``Request``/``Response``) appears in a signature (R4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.result import Result
from src.dto import AnswerEnvelopeDTO, GetSessionResponse, SessionDTO


@dataclass(frozen=True)
class CanonicalOutcome:
    """A canonical response (D58): HTTP 200 whose body is an ``ErrorBody`` with the literal."""

    code: str  # an ErrorCode such as CLARIFICATION_REQUIRED
    message: str  # the canonical literal, verbatim


class SessionUseCases(ABC):
    @abstractmethod
    def create_session(self, operator_role: str) -> Result[SessionDTO]:
        """``POST /api/v1/sessions``."""

    @abstractmethod
    def submit_query(
        self, session_id: str, query_text: str
    ) -> Result[AnswerEnvelopeDTO | CanonicalOutcome]:
        """``POST /api/v1/sessions/{sid}/queries``."""

    @abstractmethod
    def get_session(self, session_id: str) -> Result[GetSessionResponse]:
        """``GET /api/v1/sessions/{sid}`` - read-only."""

    @abstractmethod
    def reset_session(self, session_id: str) -> Result[None]:
        """``DELETE /api/v1/sessions/{sid}`` - idempotent."""
