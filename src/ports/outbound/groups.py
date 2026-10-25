"""OP-4 ``groups_port``. Query-only."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import GroupRecordDTO


class GroupsPort(ABC):
    @abstractmethod
    def get(self, group_id: str) -> Result[GroupRecordDTO | None]:
        """Record for ``group#...``; a miss is ``Ok(None)``."""

    @abstractmethod
    def browse(self, q: str, page: int, page_size: int) -> Result[list[GroupRecordDTO]]:
        """Case-folded exact-id match; empty ``q`` lists all."""
