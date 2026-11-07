---
stepsCompleted: ['step-01-preflight', 'step-02-generate-pipeline', 'step-03-configure-quality-gates', 'step-04-validate-and-summary']
lastStep: 'step-04-validate-and-summary'
lastSaved: '2026-11-06'
---

# CI pipeline setup (Impl-2, TG-I2-5)

## Preflight
- Git repo with GitHub remote; `ci_platform: github-actions`, `test_stack_type: fullstack` (config).
- Frameworks: pytest (pytest.ini), Playwright (playwright.config.ts), k6 (tests/nfr/).
- Local run: ruff clean; 979 passed, branch coverage of src 95.46%; schema_check GATE PASS.

## Pipeline
`.github/workflows/quality-gate.yml` replaces `test/ci/quality-gate.yml` (deleted). Triggers: push to
main and impl-2, pull_request, workflow_dispatch. Python 3.11, Node 24.

| Job | Gate |
|---|---|
| banned-waits | grep for sleep( / from time import sleep / waitForTimeout / wait_for_timeout in src, tests, console/src; missing dirs skipped; comment lines ignored; grep exit 1 = pass, >1 = fail. Second step, tests/ only: setTimeout used as a wait (new Promise(... setTimeout ...), promisify(setTimeout), timers/promises) |
| lint-test | ruff, then pytest --cov=src --cov-branch --cov-fail-under=90 |
| schema | test/ci/schema_check.py (no red-phase step) |
| nfr | grafana/setup-k6-action (k6 2.3.0), uvicorn on :memory:, curl --retry wait, every tests/nfr/*.js, k6-summary artifact |
| e2e | npx playwright test --trace on --fail-on-flaky-tests; test-results/ and playwright-report/ always uploaded |

playwright.config.ts unchanged (`trace: 'on-first-retry'`).

## Validation (local)
- banned-waits: clean tree exit 0; planted time.sleep / waitForTimeout exit 1; shellcheck clean.
- k6: pass exit 0; forced threshold breach exit 99; summary JSON written.
- Playwright: 1 passed with CI=1; test-results/**/trace.zip and playwright-report/ produced.

## Not included
- Burn-in loop and sharding: one E2E spec today; `--fail-on-flaky-tests` with retries: 1 covers flakiness.
- Workflow not yet executed on GitHub (no actionlint locally).
