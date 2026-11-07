"""Internal port for the Module-12-OWNED tool-call audit (AD-10, FR-11, contracts.md I14, I20).

Append-only: there is no update or delete operation. ``append`` writes ``tool_calls`` and
``audit_records`` rows together and applies the retention cap in the same transaction; when the
application already holds a unit of work, the append joins it. Every operation returns a typed
``Result`` (AD-12).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from src.domain.result import Result
from src.dto import AuditRecordDTO, ToolCallDTO


@dataclass(frozen=True)
class AuditEntry:
    """One audit row and the tool call it records (``None`` for an executor row)."""

    tool_call: ToolCallDTO | None
    record: AuditRecordDTO


class AuditStorePort(ABC):
    @abstractmethod
    def append(self, entries: Sequence[AuditEntry]) -> Result[None]:
        """Store every entry, in order, or none of them; then rotate above the retention cap."""

    @abstractmethod
    def page(
        self, session_id: str, offset: int, limit: int
    ) -> Result[tuple[list[AuditRecordDTO], int]]:
        """A session's rows ascending by ``(timestamp, audit_id)``, and its retained total."""

    @abstractmethod
    def highest_counters(self) -> Result[dict[str, int]]:
        """Highest stored numeric suffix for the ``tool_call`` and ``audit`` id kinds (E43)."""
