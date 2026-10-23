"""Module 12 — mandatory test fixtures (Step 3.2).

The canonical implementations live in the harness package ``tests/support`` (see
``tests/README.md`` for the full contract each fixture anchors to). This package
exposes the five **mandatory** fixtures under the workshop's ``test/fixtures/`` path
without duplicating code.

| Fixture | Module | Contract anchor |
|---|---|---|
| ``fake_clock``    | ``fake_clock.py``    | OP-10 ``clock_port``; §0.1 ``ClockRead`` |
| ``seed_fleet``    | ``seed_fleet.py``    | OP-6 ``nodes_port``; §0.3 ``NodeRecord`` |
| ``sim_telemetry`` | ``sim_telemetry.py`` | scripted GPU/heartbeat/metric injector |
| ``db``            | ``db.py``            | ``001_module12_copilot_schema.sql``; AD-10 |
| ``explain_assert``| ``explain_assert.py``| AD-2, AD-8, AD-11; §0.5 ``Intent`` |

The same fixtures are declared as pytest fixtures in ``tests/conftest.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parents[2] / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
