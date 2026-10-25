"""OP-6 ``nodes_port``. Query-only: no cordon/drain/scheduling method exists (AD-13)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import NodeRecordDTO, SelectorDTO


class NodesPort(ABC):
    @abstractmethod
    def get(self, node_id: str) -> Result[NodeRecordDTO | None]:
        """Record for ``node#...``; a miss is ``Ok(None)``."""

    @abstractmethod
    def select(self, selector: SelectorDTO) -> Result[list[NodeRecordDTO]]:
        """Every record matching ``selector``, by ``id`` ascending, bounded by the store cap."""

    @abstractmethod
    def browse(self, q: str, page: int, page_size: int) -> Result[list[NodeRecordDTO]]:
        """Case-folded exact-id match; empty ``q`` lists all."""
