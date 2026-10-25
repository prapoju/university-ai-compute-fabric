"""Simulated, freezable ``clock_port`` (OP-10). The only time source in the system (DP-5).

Real time is never consulted: the clock starts at an injected ``Instant`` and only moves when
a scenario advances it, which is what makes determinism (AD-2, FR-14) testable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.domain.instants import format_instant, parse_instant
from src.domain.result import Failure, Ok, Result
from src.dto import ClockReadDTO
from src.ports.outbound import ClockPort


class SimClock(ClockPort):
    def __init__(self, start: str) -> None:
        self._instant: datetime = parse_instant(start)
        self._counter = 0
        self._failed = False

    # -- ClockPort -----------------------------------------------------------------------------
    def now(self) -> Result[ClockReadDTO]:
        if self._failed:
            return Failure("CLOCK_UNAVAILABLE", observed=("simulated clock failure",))
        self._counter += 1
        return Ok(
            ClockReadDTO(
                read_id=f"clk-{self._counter:016x}",
                instant=format_instant(self._instant),
                source="clock",
            )
        )

    # -- simulation controls (not part of the port) --------------------------------------------
    @property
    def available(self) -> bool:
        """Whether a read would succeed; unlike ``now()`` it consumes no read id."""
        return not self._failed

    def advance(
        self, *, seconds: float = 0, minutes: float = 0, hours: float = 0, days: float = 0
    ) -> None:
        delta = timedelta(seconds=seconds, minutes=minutes, hours=hours, days=days)
        if delta < timedelta(0):
            raise ValueError("the simulated clock only moves forward")
        self._instant += delta

    def set(self, instant: str) -> None:
        target = parse_instant(instant)
        if target < self._instant:
            raise ValueError("the simulated clock only moves forward")
        self._instant = target.astimezone(UTC)

    def fail(self) -> None:
        self._failed = True

    def recover(self) -> None:
        self._failed = False
