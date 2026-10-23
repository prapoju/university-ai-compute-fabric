"""``fake_clock`` — deterministic, advanceable time (no real sleep).

Re-exports the canonical implementation from ``tests/support/clock.py``.
Anchors: OP-10 ``clock_port``; contracts §0.1 ``ClockRead``; rule I-CLK-1
(never reads wall-clock).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

from support.clock import ClockRead, FakeClock, format_instant, parse_instant  # noqa: E402

__all__ = ["FakeClock", "ClockRead", "format_instant", "parse_instant"]
