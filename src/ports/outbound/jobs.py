"""OP-5 ``jobs_port``. Query-only; ``select`` is the dry-run enumeration source (AD-6)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import JobRecordDTO, SelectorDTO


class JobsPort(ABC):
    @abstractmethod
    def get(self, job_id: str) -> Result[JobRecordDTO | None]:
        """Record for ``job#...``; a miss is ``Ok(None)``."""

    @abstractmethod
    def select(self, selector: SelectorDTO) -> Result[list[JobRecordDTO]]:
        """Every record matching ``selector``, by ``id`` ascending, bounded by the store cap."""

    @abstractmethod
    def browse(self, q: str, page: int, page_size: int) -> Result[list[JobRecordDTO]]:
        """Case-folded exact-id match; empty ``q`` lists all."""
