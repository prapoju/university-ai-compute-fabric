"""Stand-in use cases for a service whose session store is down.

The composition root registers these when the database cannot be opened or migrated, so every
session, evidence and citation route answers with the typed safe failure (503,
``PROVIDER_UNAVAILABLE``) instead of a crash, while ``/readyz`` reports the cause (AD-12).
"""

from __future__ import annotations

from src.domain.result import Failure, Result
from src.domain.safety import DestructiveRequest
from src.dto import (
    AnswerEnvelopeDTO,
    GetAnswerEvidenceResponse,
    GetAuditPageResponse,
    GetCitationResponse,
    GetSessionResponse,
    SessionDTO,
)
from src.ports.inbound import (
    AuditUseCases,
    CanonicalOutcome,
    DestructiveUseCases,
    DryRunOutcome,
    EvidenceUseCases,
    SessionUseCases,
)


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


class UnavailableEvidenceUseCases(EvidenceUseCases):
    def __init__(self, reason: str) -> None:
        self._failure = Failure("PROVIDER_UNAVAILABLE", observed=(reason,))

    def get_answer_evidence(self, answer_id: str) -> Result[GetAnswerEvidenceResponse]:
        return self._failure

    def get_citation(self, citation_id: str) -> Result[GetCitationResponse]:
        return self._failure


class UnavailableDestructiveUseCases(DestructiveUseCases):
    def __init__(self, reason: str) -> None:
        self._failure = Failure("PROVIDER_UNAVAILABLE", observed=(reason,))

    def post_dry_run(
        self, query_text: str, action: str, target_refs: list[str], session_id: str
    ) -> Result[DryRunOutcome | CanonicalOutcome]:
        return self._failure

    def dry_run_request(
        self, session_id: str, request: DestructiveRequest
    ) -> Result[DryRunOutcome | CanonicalOutcome]:
        return self._failure


class UnavailableAuditUseCases(AuditUseCases):
    def __init__(self, reason: str) -> None:
        self._failure = Failure("PROVIDER_UNAVAILABLE", observed=(reason,))

    def get_audit_page(
        self, session_id: str, page: int, page_size: int
    ) -> Result[GetAuditPageResponse]:
        return self._failure
