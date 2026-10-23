# Module 12 — TEA quality gate (local mirror of test/ci/quality-gate.yml).
# Uses '.RECIPEPREFIX = >' so recipes are indented with '>' (no hard tabs needed).
.RECIPEPREFIX = >
PY ?= python3

.PHONY: install test harness atdd red-phase schema cov ci clean

install:
> $(PY) -m pip install -r requirements-test.txt

## Full gate: harness green + ATDD red-for-the-right-reason + schemas valid.
test: harness red-phase schema

harness:
> $(PY) -m pytest tests -q --strict-markers

## Raw ATDD run (expected to be red in the solutioning stop-point).
atdd:
> $(PY) -m pytest test/atdd -q

## Assert every ATDD test fails on the interface stub (NotImplementedError).
red-phase:
> $(PY) test/ci/red_phase_check.py

## Validate SQL / dto.py / events.schema.json / openapi.yaml.
schema:
> $(PY) test/ci/schema_check.py

## Coverage floors (post-implementation; test-design.md §3).
cov:
> $(PY) -m pytest tests -q --cov=service --cov=module12 --cov-report=term-missing --cov-fail-under=90

ci: test
> @echo "TEA gate PASS"

clean:
> find . -type d -name __pycache__ -prune -exec rm -rf {} +
> find . -type d -name .pytest_cache -prune -exec rm -rf {} +
> rm -rf .coverage htmlcov
