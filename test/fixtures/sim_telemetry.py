"""``sim_telemetry`` — scripted GPU / heartbeat / metric injector (fault generator).

Re-exports the canonical implementation from ``tests/support/telemetry.py``.
``script_thermal_fault()`` reproduces scenario S3 (``node#ws-gpu-11``,
``ERR_THERMAL_88``, cordoned). Time steps come from ``fake_clock``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

from support.telemetry import Sample, SimTelemetry  # noqa: E402

__all__ = ["SimTelemetry", "Sample"]
