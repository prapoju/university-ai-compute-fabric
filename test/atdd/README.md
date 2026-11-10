# test/atdd: historical Phase-3 contract suite

This directory is the ATDD suite written at the Phase-3 solutioning stop-point, before any
product code existed. Keep it as a **source of contract cases**, not as a gate.

## Why it stays red

Every test in `module12_contracts.test.py` calls the stub `module12_interface.CopilotInboundPort`,
and every stub method raises `NotImplementedError`. The stub is never wired to `src/`, so no
test here can pass. Red is the designed state: `test/ci/red_phase_check.py` (`make red-phase`)
only proves that each test fails *for the right reason* (it reached the stub) and not on an
import or collection error.

For that reason `make test` and `make ci` no longer run `red-phase`. A suite that can never go
green proves nothing about the implementation.

## How to use it

When you write an acceptance test for a story, read the matching cases here (happy path,
precondition violation, invariant, the R-01 edge case, explainability) and port the
assertions to a real suite.

## Where the real ATDD suites live

`tests/atdd/test_story_<id>.py`. Those suites call the real app (`create_app`) and run
under `make harness`, `make cov` and `make ci` (docs/impl2-rules.md, Test rules).
Do not add tests here, and do not edit this suite to make it pass.
