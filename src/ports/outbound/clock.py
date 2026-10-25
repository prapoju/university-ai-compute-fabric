"""OP-10 ``clock_port``: the only source of time (AD-2, DP-5, R2)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import ClockReadDTO


class ClockPort(ABC):
    @abstractmethod
    def now(self) -> Result[ClockReadDTO]:
        """A fresh ``ClockRead``; failure is ``Failure("CLOCK_UNAVAILABLE")``."""
