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

## Impl-2 extension (2026-11-06)

- Stack: fullstack. The pytest harness above is kept as-is; Playwright (`@playwright/test` 1.65) and k6 2.3 are layered on.
- Added: `playwright.config.ts`, `tests/e2e/smoke.spec.ts`, `tests/e2e/pages/README.md`, `tests/nfr/smoke.js`,
  `test/atdd/README.md`, npm `test` script; `tests/README.md` updated for the three layers and Impl-2.
- Makefile: `lint`; `cov` on `src` with branch coverage and a 90% floor; `e2e` and `nfr` (with no-`waitForTimeout` / no-`sleep()` guards);
  `ci` = lint cov schema e2e nfr; `red-phase` removed from `test` and `ci`.
- Verification: `npx playwright test` 1 passed; `make cov` 979 passed, branch coverage 95.46%; `make ci` PASS (k6 p95 1.8 ms, 0 failed).
- Open: `test/ci/quality-gate.yml` still mirrors the Phase-3 gate (left for `/bmad-testarch-ci`).
