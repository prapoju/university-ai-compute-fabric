"""OP-7 ``reservations_port``. Query-only; intervals are half-open ``[start, end)``."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import ReservationRecordDTO


class ReservationsPort(ABC):
    @abstractmethod
    def get(self, reservation_id: str) -> Result[ReservationRecordDTO | None]:
        """Record for ``reservation#...``; a miss is ``Ok(None)``."""

    @abstractmethod
    def browse(self, q: str, page: int, page_size: int) -> Result[list[ReservationRecordDTO]]:
        """Case-folded exact-id match; empty ``q`` lists all."""
