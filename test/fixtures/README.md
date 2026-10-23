# Module 12 — Mandatory fixtures (Step 3.2)

Thin re-exports of the canonical harness fixtures that live in `tests/support/`.
The workshop submission tree asks for the fixtures under `test/fixtures/`; the
implementations stay single-sourced in `tests/support/` so they are not duplicated.

| Fixture | Import | Anchors |
|---|---|---|
| `fake_clock` | `from fixtures.fake_clock import FakeClock` | OP-10 `clock_port`; §0.1 `ClockRead`; I-CLK-1 |
| `seed_fleet` | `from fixtures.seed_fleet import build_fleet` | OP-6 `nodes_port`; §0.3 `NodeRecord` |
| `sim_telemetry` | `from fixtures.sim_telemetry import SimTelemetry` | scripted faults (S3) |
| `db` | `from fixtures.db import TestDatabase` | `001_*.sql`; AD-10 |
| `explain_assert` | `from fixtures.explain_assert import explain_assert` | AD-2, AD-8, AD-11; §0.5 |

The same five fixtures are declared as pytest fixtures in `tests/conftest.py`, so
tests can also take them by name:

```python
def test_s3_grounds_every_claim(fake_clock, seed_fleet, sim_telemetry, explain_assert):
    sim_telemetry.script_thermal_fault("node#ws-gpu-11")
    ...
```

See `tests/README.md` for the full contract each fixture guarantees.
