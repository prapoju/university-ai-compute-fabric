"""Deterministic, advanceable clock (test double for outbound port OP-10 `clock_port`).

Contract refs:
  - ``planning/detailed-design/contracts.md`` §0.1 `ClockRead`
    ``{read_id, instant, source}``; citation id `clock#{read_id}`.
  - §3 OP-10 `clock_port`: ``now() -> ClockRead``; ``read_id`` matches
    ``^clk-[0-9a-f]{16}$``, ``source == "clock"``.
  - §1 `answer_query` "Time": the core never calls ``datetime.now()``/``time.time()``
    (I-CLK-1); every time rule consumes this port.

No real time is ever consulted. Tests advance the clock explicitly, which is what
makes the determinism invariants (I2, NFR-7) testable without ``sleep``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

# §3 OP-10 Distinct Q / §0.1
READ_ID_RE = re.compile(r"^clk-[0-9a-f]{16}$")
# §0.1 Instant
INSTANT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z$")

# S1/S2/S3 scenarios all sit at 15:00 (planning/ux/C-UX-Scenarios). A fixed default
# keeps seeded runs reproducible.
DEFAULT_START = "2026-10-16T15:00:00.000Z"


def parse_instant(value: str) -> datetime:
    """Parse an `Instant` (§0.1) into an aware UTC datetime."""
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not INSTANT_RE.match(text):
            raise ValueError(f"not an Instant (§0.1): {value!r}")
        fmt = "%Y-%m-%dT%H:%M:%S.%fZ" if "." in text else "%Y-%m-%dT%H:%M:%SZ"
        dt = datetime.strptime(text, fmt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_instant(value: datetime) -> str:
    """Format a datetime as an `Instant` (§0.1) with millisecond precision."""
    dt = value.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


@dataclass(frozen=True)
class ClockRead:
    """§0.1 `ClockRead`."""

    read_id: str
    instant: str
    source: str = "clock"

    def __post_init__(self) -> None:
        if not READ_ID_RE.match(self.read_id):
            raise ValueError(f"read_id violates OP-10 format: {self.read_id!r}")
        if self.source != "clock":
            raise ValueError("ClockRead.source must equal 'clock'")

    @property
    def citation_id(self) -> str:
        """§0.1: a clock citation id is ``clock#{read_id}``."""
        return f"clock#{self.read_id}"

    def as_dict(self) -> dict[str, str]:
        return {"read_id": self.read_id, "instant": self.instant, "source": self.source}


class FakeClock:
    """Advanceable in-memory clock implementing OP-10.

    ``read_id`` is a zero-padded hex counter, so a fresh clock is fully
    reproducible: the Nth ``now()`` always returns the same id (I2 / OP-13
    "under seed, the sequence is fixed so FR-14 runs reproduce the same ids").
    """

    def __init__(self, start: str = DEFAULT_START) -> None:
        self._instant = parse_instant(start)
        self._counter = 0
        self.reads: list[ClockRead] = []

    def now(self) -> ClockRead:
        """OP-10 ``now()`` — returns a fresh, unique, reproducible `ClockRead`."""
        self._counter += 1
        read = ClockRead(read_id=f"clk-{self._counter:016x}", instant=self.current)
        self.reads.append(read)
        return read

    def advance(
        self,
        *,
        seconds: float = 0,
        minutes: float = 0,
        hours: float = 0,
        days: float = 0,
    ) -> str:
        """Move the clock forward; returns the new `Instant`."""
        delta = timedelta(seconds=seconds, minutes=minutes, hours=hours, days=days)
        if delta < timedelta(0):
            raise ValueError("FakeClock only moves forward")
        self._instant += delta
        return self.current

    def set(self, instant: str) -> str:
        """Pin the clock to an absolute `Instant` (e.g. a scenario 'now')."""
        self._instant = parse_instant(instant)
        return self.current

    def advance_to(self, instant: str) -> str:
        """Advance to an absolute instant; must not move backwards."""
        target = parse_instant(instant)
        if target < self._instant:
            raise ValueError("FakeClock only moves forward")
        self._instant = target
        return self.current

    @property
    def current(self) -> str:
        """The current `Instant` without issuing a read."""
        return format_instant(self._instant)

    @property
    def issued(self) -> int:
        """How many reads this clock has issued (audit/assert convenience)."""
        return self._counter


def as_clock_read(value: Any) -> ClockRead:
    """Coerce a mapping/dict into a `ClockRead` (adapter boundary helper)."""
    if isinstance(value, ClockRead):
        return value
    return ClockRead(
        read_id=value["read_id"],
        instant=value["instant"],
        source=value.get("source", "clock"),
    )
