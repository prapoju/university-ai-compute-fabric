"""OP-1 ``users_port`` (contracts.md section 3). Query-only."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import UserRecordDTO


class UsersPort(ABC):
    @abstractmethod
    def get(self, id: str) -> Result[UserRecordDTO | None]:
        """Record for an ``EntityKey`` such as ``user#alex``; a miss is ``Ok(None)``."""

    @abstractmethod
    def browse(self, q: str, page: int, page_size: int) -> Result[list[UserRecordDTO]]:
        """Case-folded exact-id match; empty ``q`` lists all. ``page_size`` is capped at 100."""

    @abstractmethod
    def by_ids(self, ids: list[str]) -> Result[list[UserRecordDTO]]:
        """Every key must have type ``user`` (``VALIDATION_BAD_ENTITY_TYPE`` otherwise)."""
