# Module 12 — TEA quality gate (local mirror of test/ci/quality-gate.yml).
# Uses '.RECIPEPREFIX = >' so recipes are indented with '>' (no hard tabs needed).
.RECIPEPREFIX = >
PY ?= python3
NFR_URL ?= http://127.0.0.1:8000

.PHONY: install test harness atdd red-phase schema lint cov e2e nfr ci clean

install:
> $(PY) -m pip install -r requirements-test.txt
> npm ci

## Fast gate: harness green + schemas valid.
test: harness schema

harness:
> $(PY) -m pytest tests -q --strict-markers

## Historical Phase-3 stub suite (test/atdd/README.md). Always red; not part of any gate.
atdd:
> $(PY) -m pytest test/atdd -q

## Assert every stub ATDD test fails on NotImplementedError. Historical; not part of any gate.
red-phase:
> $(PY) test/ci/red_phase_check.py

## Validate SQL / dto.py / events.schema.json / openapi.yaml.
schema:
> $(PY) test/ci/schema_check.py

lint:
> $(PY) -m ruff check .

## Branch coverage floor on src (docs/impl2-rules.md: >= 90%).
cov:
> $(PY) -m pytest tests -q --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=90

## Playwright E2E (playwright.config.ts starts uvicorn itself). waitForTimeout is banned.
e2e:
> @! grep -rnE --include='*.ts' '^[^/]*waitForTimeout' tests/e2e || { echo "waitForTimeout is banned (docs/impl2-rules.md)"; exit 1; }
> PY=$(PY) npx playwright test

## k6 smoke against a throwaway uvicorn on :memory:. sleep() is banned: executors pace the load.
nfr:
> @! grep -rnE --include='*.js' '^[^/]*\bsleep\(' tests/nfr || { echo "sleep() is banned in k6 scripts (docs/impl2-rules.md)"; exit 1; }
> @M12_DB_PATH=:memory: $(PY) -m uvicorn src.adapters.inbound.app:create_app --factory \
>   --host 127.0.0.1 --port 8000 --log-level warning & pid=$$!; \
>   trap 'kill $$pid' EXIT; \
>   curl -sf --retry 30 --retry-connrefused --retry-delay 1 $(NFR_URL)/healthz >/dev/null \
>   && BASE_URL=$(NFR_URL) k6 run --quiet tests/nfr/smoke.js

ci: lint cov schema e2e nfr
> @echo "TEA gate PASS"

clean:
> find . -type d -name __pycache__ -prune -exec rm -rf {} +
> find . -type d -name .pytest_cache -prune -exec rm -rf {} +
> rm -rf .coverage htmlcov test-results playwright-report
