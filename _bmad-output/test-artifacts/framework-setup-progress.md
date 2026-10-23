# Test Framework Setup — Progress

- **Workflow:** bmad-testarch-framework
- **Project:** Module 12 — AI Operations Copilot
- **Status:** complete (harness runnable; `39 passed`)
- **Date:** 2026-10-16

## Preflight

- Python 3.11.15, SQLite 3.50.4 (>= 3.35, AD-10 satisfied).
- pytest 9.1.1 present; `pytest-asyncio`, `hypothesis`, `pytest-cov` were missing and were
  installed from `requirements-test.txt`.
- `bmad-testarch-framework` is not installed in this repo; executed per the inline command
  against the backend (pytest) profile rather than the skill's Playwright default.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Framework | pytest + pytest-asyncio + hypothesis | Project stack is Python/FastAPI; no UI to drive. |
| Test dir | `tests/` (repo root) | Skill default; `ARCHITECTURE.md` structural seed uses `tests/`. |
| Database | in-memory SQLite from `001_module12_copilot_schema.sql` | Real DDL/triggers/partial indexes, zero external services; SQLite is the project store. |
| Time | `fake_clock` only; no `sleep` | AD-2 / I-CLK-1 determinism; enables I2/FR-14 identity tests. |
| Ids | `IdFactory` (seeded) | OP-13 / R2: no `uuid4`/`random` anywhere in tests. |
| Fleet count | `DEFAULT_STANDARD_NODE_COUNT = 31` + one 2×48 GB node | Brief says "many" 24 GB machines + one 2×48 GB; count is a tunable knob, not a contract. |

## Artifacts

- `pytest.ini`, `requirements-test.txt`, `.python-version`
- `tests/conftest.py`, `tests/support/{__init__,clock,fleet,telemetry,db,explain,ids,builders}.py`
- `tests/unit/*`, `tests/integration/test_db_schema.py`, `tests/api/.gitkeep`,
  `tests/test_example.py`
- `tests/README.md` (main deliverable)
- Cross-reference: `test/test-design.md` (risk register, level allocation, thresholds)

## Verification

- `python -m pytest -q` -> **39 passed in 0.99s**
- `asyncio: mode=Mode.AUTO`; hypothesis example runs under `-m determinism`.
