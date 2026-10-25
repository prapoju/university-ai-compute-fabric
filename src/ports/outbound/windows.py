"""OP-8 ``windows_port`` - policy windows. Query-only."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import PolicyWindowDTO


class WindowsPort(ABC):
    @abstractmethod
    def get(self, window_id: str) -> Result[PolicyWindowDTO | None]:
        """Record for ``window#...``; a miss is ``Ok(None)``."""

    @abstractmethod
    def list(self) -> Result[list[PolicyWindowDTO]]:
        """All windows in stable ``window_id`` order (AD-2, AD-14)."""
