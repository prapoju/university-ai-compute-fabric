"""OP-2 ``catalog_port`` - the model catalog. Query-only."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import ModelCatalogEntryDTO


class CatalogPort(ABC):
    @abstractmethod
    def get(self, model_id: str) -> Result[ModelCatalogEntryDTO | None]:
        """Entry for ``model#...``; a miss is ``Ok(None)``."""

    @abstractmethod
    def browse(self, q: str, page: int, page_size: int) -> Result[list[ModelCatalogEntryDTO]]:
        """Case-folded exact-id match; empty ``q`` lists all."""
