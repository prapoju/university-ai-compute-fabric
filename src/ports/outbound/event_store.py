"""OP-9 ``event_store_port`` - historical operational events. Query-only."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.result import Result
from src.dto import OperationalEventDTO


@dataclass(frozen=True)
class EventWindow:
    """Half-open ``[start, end)`` interval of ``Instant`` strings; ``start < end``."""

    start: str
    end: str


class EventStorePort(ABC):
    @abstractmethod
    def query(
        self, entity_ref: str, type: str, window: EventWindow
    ) -> Result[list[OperationalEventDTO]]:
        """Events matching ``entity_ref`` and ``type`` with ``timestamp`` in ``window``.

        Ordered by ``timestamp`` then ``event_id`` ascending. An unknown ``type`` or an
        empty/inverted window is ``Failure("VALIDATION_MALFORMED_BODY")``.
        """
