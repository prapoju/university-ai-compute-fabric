"""Inbound port: raw state inspection the REST adapter drives (contracts.md section 2, FR-12).

``get_state_record`` returns one record exactly as its provider port holds it; ``browse_state``
pages through one entity type. Both are read-only (AD-1) and return a typed ``Result`` whose
failures are catalog errors. No framework object appears in a signature (R4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import BrowseStateResponse, RecordDTO


class StateUseCases(ABC):
    @abstractmethod
    def get_state_record(self, entity_type: str, id: str) -> Result[RecordDTO]:
        """``GET /api/v1/state/{entity_type}/{id}`` - the bare record (story 1.5 D7)."""

    @abstractmethod
    def browse_state(
        self, entity_type: str, q: str, page: int, page_size: int
    ) -> Result[BrowseStateResponse]:
        """``GET /api/v1/state/{entity_type}?q=&page=&page_size=`` - a capped page and a total."""
