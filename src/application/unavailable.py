"""Stand-in use cases for a service whose session store is down.

The composition root registers this when the database cannot be opened or migrated, so every
session route answers with the typed safe failure (503, ``PROVIDER_UNAVAILABLE``) instead of a
crash, while ``/readyz`` reports the cause (AD-12).
"""

from __future__ import annotations

from src.domain.result import Failure, Result
from src.dto import AnswerEnvelopeDTO, GetSessionResponse, SessionDTO
from src.ports.inbound import CanonicalOutcome, SessionUseCases


class UnavailableSessionUseCases(SessionUseCases):
    def __init__(self, reason: str) -> None:
        self._failure = Failure("PROVIDER_UNAVAILABLE", observed=(reason,))

    def create_session(self, operator_role: str) -> Result[SessionDTO]:
        return self._failure

    def submit_query(
        self, session_id: str, query_text: str
    ) -> Result[AnswerEnvelopeDTO | CanonicalOutcome]:
        return self._failure

    def get_session(self, session_id: str) -> Result[GetSessionResponse]:
        return self._failure

    def reset_session(self, session_id: str) -> Result[None]:
        return self._failure
