"""Inbound port: the evidence and citation reads the REST adapter drives (contracts.md section 2).

``get_answer_evidence`` returns an answer's stored ``EvidenceSet``; ``get_citation`` resolves one
citation to its current source record and the snippet stored for it. Both are read-only and
return a typed ``Result`` whose failures are catalog errors (``ENTITY_NOT_FOUND``,
``PROVIDER_UNAVAILABLE``). No framework object appears in a signature (R4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import GetAnswerEvidenceResponse, GetCitationResponse


class EvidenceUseCases(ABC):
    @abstractmethod
    def get_answer_evidence(self, answer_id: str) -> Result[GetAnswerEvidenceResponse]:
        """``GET /api/v1/answers/{aid}/evidence`` - the stored set, ascending by ``position``."""

    @abstractmethod
    def get_citation(self, citation_id: str) -> Result[GetCitationResponse]:
        """``GET /api/v1/citations/{cid}`` - the source record and the stored snippet."""
