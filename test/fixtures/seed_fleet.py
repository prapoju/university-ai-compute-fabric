"""``seed_fleet`` — the Plan-2 fleet profile (many 1x24 GB nodes + one 2x48 GB node).

Re-exports the canonical implementation from ``tests/support/fleet.py``.
Anchors: OP-6 ``nodes_port``; contracts §0.3 ``NodeRecord``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

from support.fleet import Fleet, NodeRecord, NodeSpec, build_fleet  # noqa: E402

__all__ = ["Fleet", "NodeRecord", "NodeSpec", "build_fleet"]
