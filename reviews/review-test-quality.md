---
title: Test Quality Review — module12_contracts.test.py
workflow: bmad-testarch-test-review
status: complete
review_set: test/atdd/
reviewed_files: [test/atdd/module12_contracts.test.py]
context_files: [test/atdd/module12_interface.py, planning/detailed-design/contracts.md, test/test-design.md]
test_stack_type: backend (pytest)
detected_stack: backend
overall_score: 97
overall_grade: A
recommendation: Request Changes
created: 2026-10-16
updated: 2026-10-16
---

# Test Quality Review: module12_contracts.test.py

**Reviewer:** Master Test Architect (TEA `bmad-testarch-test-review`)
**Review set:** `test/atdd/` — 1 file, 121 tests (`@pytest.mark.atdd`)
**Stack:** Python 3.11 · pytest 9.x · `pytest-asyncio` · `hypothesis` (backend / contract suite)
**Runner note:** Registry rows bound to Playwright, Cypress, Maestro, and Pact are **not applicable** to a pytest suite; their gates are closed and scored `PASS (n/a)`.

---

## Executive Summary

**Overall Score:** `97 / 100` — **Grade A**
**Recommendation:** **Request Changes** (derived: ≥ 1 `HIGH` violation)
**Scope:** ATDD red-phase contract suite for the Module 12 inbound-port interface. Every test calls `module12_interface.CopilotInboundPort` (or a `§1` core-operation method); with no implementation the stub raises `NotImplementedError`, so **all 121 tests are currently red by design** — the correct ATDD red-phase state, not a test-quality defect.

### Key Strengths

- **Assertions are real and behavior-shaped.** Tests assert return values, resulting Module-12-owned state (`s.sessions`/`s.answers`/`s.proposals`), emitted audit events, executor side effects, and — for rejections — *what did not happen* (`s.store.mutations == []`, `not s.answers`, `not s.executor.calls`).
- **No tautologies or self-configured mocks.** Collaborator assertions observe calls the SUT is expected to *drive*; no test asserts a value it stubbed in. No `CRITICAL` rows fired.
- **Determinism by construction.** `FakeClock`, seeded `IdFactory`, fixed `NOW`; no wall-clock reads, no `sleep`, no `uuid4`/`random` (satisfies AD-2 / FR-14 / R2).
- **Clean fixtures/builders.** Per-test `svc()`, `seed_session`/`seed_proposal`, and record builders (`node_record`, `job_record`, `event_record`, `window_record`, `runbook_template`) route setup through factories rather than inline literal soup.
- **Requirement-anchored names.** Test names state the contract (`*_happy_*`, `*_precondition_*`, `*_fault_*`, `*_invariant_*`, `test_edge_ec_*`, `test_explainability_*`).

### Key Weaknesses

1. **`HIGH — H5 Oversize test file:** 1,500 lines (cap 1,000). One file carries the entire 121-test contract surface for 27 operations.
2. **`HIGH — H3 Conditional assertion:** two tests branch on the SUT result to decide *what* to assert, so a wrong shape can still pass.

### Summary

A high-quality contract suite whose only real defects are structural (file size) and two conditional
assertions. No test proves nothing; the suite would earn an `Approve` were the two `H3` rows and the
oversize file fixed. Recommendation is `Request Changes` strictly because the registry binds any `HIGH`
row to that verdict.

---

## Quality Criteria Assessment

| Criterion | Status | Violations | Basis |
|---|---|---|---|
| BDD Format (Given-When-Then) | ✅ PASS (n/a) | 0 | names state behavior; project uses no Gherkin convention (`bddNaming` absent) |
| Test IDs | ⚠️ WARN | 0 (prose) | no stable per-test IDs; L3 targets DOM lookups (n/a for pytest) — see recommendation |
| Priority Markers (P0/P1/P2/P3) | ✅ PASS (n/a) | 0 | convention not established in baseline corpus (`priorityMarkers` absent) |
| Hard Waits (sleep, waitForTimeout) | ✅ PASS | 0 | no `sleep`/timers; `FakeClock` only |
| Determinism (no conditionals) | ❌ FAIL | 2 | H3 (2) |
| Isolation (cleanup, no shared state) | ✅ PASS | 0 | fresh `svc()` per test; module-level `SAMPLE` noted (order does not change outcome) |
| Fixture Patterns | ✅ PASS | 0 | setup via `svc()`, `seed_*`, builders |
| Data Factories | ✅ PASS | 0 | `SampleData`, `IdFactory(seed=…)`, record builders |
| Network-First Pattern | ✅ PASS (n/a) | 0 | no network |
| Playwright Utils Adoption | ✅ PASS (n/a) | 0 | precondition `playwrightUtilsActive` false |
| Pact.js Utils Adoption | ✅ PASS (n/a) | 0 | no Pact artifacts |
| Explicit Assertions | ✅ PASS | 0 | C3/C4/C5/C6/C7 do not fire |
| Test Length (≤1000 lines) | ❌ FAIL | 1 | H5 (1,500 lines) |
| Test Duration (≤1.5 min) | ✅ PASS (n/a) | 0 | red phase — no runtime; no waits |
| Flakiness Patterns | ❌ FAIL | 2 | H1/H2/H4/C6 clear; H3 (2) |
| Disabled or Focused Tests | ✅ PASS | 0 | no `.skip`/`.only`/`xfail` |
| Mobile Flow Patterns | ✅ PASS (n/a) | 0 | not a Maestro flow |

`M4` (ungrouped suite) and `L6` (magic value) fired below the FAIL threshold and appear under Recommendations.

---

## Quality Score Breakdown

```
Registry deduction ledger (fixed severities, deduped by row@file:line):
  CRITICAL × 10 =   0  × 10 =   0
  HIGH     ×  5 =   3  ×  5 = -15   (H5 ×1, H3 ×2)
  MEDIUM   ×  2 =   1  ×  2 =  -2   (M4 ×1)
  LOW      ×  1 =   1  ×  1 =  -1   (L6 ×1)
                              ------
  Deductions                 = -18

Bonuses (each 0 or 5):
  excellentBdd        = +5   (every test name states behavior, not implementation)
  comprehensiveFixtures = +5 (setup routed through fixtures/builders)
  dataFactories       = +5   (test data from factories, not hardcoded literals)
  networkFirst        = +0   (n/a)
  perfectIsolation    = +0   (module-level `SAMPLE` shared; see Recommendations)
  allTestIds          = +0   (n/a)
                              ------
  Bonus total               = +15

Score = clamp(0,100, 100 - 18 + 15) = 97  →  Grade A
Recommendation = Request Changes   (HIGH > 0)
```

---

## Critical Issues (Must Fix)

None. No `CRITICAL` registry row fired: no disabled/focused tests, no tautologies, no zero-assertion
bodies, no mock-asserted-against-itself, no unreachable assertions.

---

## Recommendations (Should Fix)

### 1. Split the 1,500-line file (`H5`, HIGH)
`test/atdd/module12_contracts.test.py:1` — 1,500 lines exceeds the 1,000-line cap.
Suggested split by contract surface (mirrors the file's own section banners):
`atdd/test_core_resolve_evidence.py` (`§1` resolve/assemble), `atdd/test_diagnosers.py`
(`§1` diagnose_*), `atdd/test_proposal_flow.py` (`§1` propose/confirm), `atdd/test_routes_sessions_state.py`
(`§2` sessions/state), `atdd/test_routes_destructive_executor.py` (`§2` destructive/executor),
`atdd/test_edge_explainability.py` (EC + explainability). Keep `conftest.py`/`module12_interface.py` shared.

### 2. Remove conditional assertions (`H3`, HIGH)
- `test/atdd/module12_contracts.test.py:512` — `if isinstance(mismatched, CanonicalOutcome): … else: …`
  decides what to assert. Choose one contract (the canonical `S_RBX` outcome) and assert it unconditionally;
  if both are legal per `contracts.md`, split into two tests.
- `test/atdd/module12_contracts.test.py:821` — `if proposal["state"] == "executed": … else: …`.
  Assert the invariant that must hold in *both* branches (`applied_count <= n`, and success only when
  `applied_count == n`), without branching on state.

### 3. Group tests for localizable failures (`M4`, MEDIUM)
1,200+ lines with 121 top-level `def test_*` and only comment banners. Use pytest classes
(`class TestResolveEntities:`) or split modules (recommendation 1) so `-k`/report output carries a subject.

### 4. Name the magic values (`L6`, LOW)
Replace bare domain literals with named constants: ref-array cap `33` (`:252`), query cap `1001` (`:608`),
page-size caps `101` (`:986`) / `50` (`:1066`), out-of-range page `9999` (`:994`). Constants such as
`THERMAL_CODE`, `TRIAGE_NODE`, `NOW` already follow this pattern — extend it.

### 5. Isolate the shared `SAMPLE` fixture (`H4` advisory)
`test/atdd/module12_contracts.test.py:56` — module-level `SAMPLE = SampleData(IdFactory(seed=12), …)` is
stateful (`SAMPLE.ids.answer_id()` advances a counter). It does not currently change any outcome (tests
that use it do not assert the generated id), but it makes id values order-dependent. Move it into a
function-scoped fixture.

### 6. Add explicit stable test IDs (traceability)
No test carries a stable ID. The trace matrix (`test/traceability-matrix.md`) currently keys on function
names. Add a `pytest.mark` id or a `CASES`/`TC-###` marker so stories (Phase 4) can bind to cases that
survive renames.

---

## Best Practices Found

1. **Recording-double observation pattern.** `OperationalStore`/`AuditLog`/`RecordingExecutor`/`Metrics`
   observe what the SUT *must drive*, including negative evidence (`mutations == []`), which is exactly the
   shape an anti-fabrication/safety suite needs (`test/atdd/module12_interface.py:188`).
2. **Deterministic time/ids.** `FakeClock` + seeded `IdFactory` + fixed `NOW` make FR-14/I2 testable and
   kill the entire flakiness class (H1/H2) at the source.
3. **Contract-taxonomy naming.** `happy` / `precondition` / `fault` / `invariant` suffixes (per
   `contracts.md §1/§2`) make gaps auditable by grep — used directly by the trace workflow.
4. **Canonical-string byte-exactness.** `s_enf`/`s_cnc`/`s_rbx` helpers assert the literal contracts.md §0
   constants rather than re-typing prose.

---

## Test File Analysis

### File Metadata
- **File:** `test/atdd/module12_contracts.test.py`
- **Lines:** 1,500 · **Tests:** 121 · **Fixtures/doubles:** shared via `module12_interface.py` + `tests/support/*`
- **Markers:** `pytestmark = [pytest.mark.atdd]`

### Test Structure
- `§1 Core domain`: `resolve_entities`, `assemble_evidence`, `diagnose_access_denial`,
  `diagnose_schedule_window`, `diagnose_retrospective`, `diagnose_node_triage`, `lookup_runbook`,
  `answer_query`, `propose_destructive_action`, `confirm_and_dispatch`.
- `§2 Inbound routes`: sessions, state reads, audit read, destructive flow.
- `§2 Executor routes`: frozen AD-15 contract.
- Edge case (R-01) + explainability (AD-2/AD-8/AD-11).

### Test Scope
Integration-level contract tests against the inbound-port seam (in-process, no external services).

### Assertions Analysis
Real return/state/event assertions; negative assertions for rejections; ~121 tests each with ≥ 1 assertion
and no unreachable assertions.

---

## Context and Integration

### What the Context Said
- **Oracle:** `planning/prd.md` FR-01..FR-16 / NFR-1..NFR-11.
- **Contract:** `planning/detailed-design/contracts.md` (§0 strings, §1 ops, §2 routes, §4 errors, §5 invariants).
- **Interface under test:** `test/atdd/module12_interface.py` — every operation raises `NotImplementedError` (red phase).
- **Design:** `test/test-design.md` (risk register, level allocation, thresholds).

### Related Artifacts
- `test/traceability-matrix.md` (produced this run)
- `test/nfr-evidence.md` (NFR evidence ledger)
- `tests/` (green harness: unit/integration; passes as of framework setup)

---

## Knowledge Base References

TEA fragments consulted: `test-quality.md`, `test-levels-framework.md`, `data-factories.md`,
`timing-debugging.md`, `selector-resilience.md` (n/a — backend), and the criteria registry
(`steps-c/criteria-registry.md`). Registry rows keyed to Playwright/Cypress/Maestro/Pact were evaluated and
their gates closed for a pytest runner.

---

## Next Steps

### Immediate Actions (Before Merge)
1. Split the file (Rec. 1, `H5`).
2. De-conditionalize the two tests (Rec. 2, `H3`).

### Follow-up Actions (Future PRs)
3. Group/section tests (Rec. 3).
4. Name magic values (Rec. 4).
5. Move `SAMPLE` to a fixture (Rec. 5).
6. Add stable test IDs before Phase 4 (Rec. 6).

### Re-Review Needed?
Yes — after the `H5`/`H3` fixes, re-run `bmad-testarch-test-review test/atdd/` to flip the verdict to `Approve`.

---

## Decision

**Recommendation:** **Request Changes** (score 97, Grade A; derived from `HIGH > 0`).
The suite is fundamentally sound — no `CRITICAL` findings — but the registry binds any `HIGH` row to
`Request Changes`. Fixing the oversize file and the two conditional assertions is cheap and moves the
verdict to `Approve`.

---

## Appendix

### Violation Summary by Location

| Row | Severity | File:Line | Description |
|---|---|---|---|
| H5 | HIGH | `test/atdd/module12_contracts.test.py:1` (file) | 1,500 lines > 1,000 cap |
| H3 | HIGH | `test/atdd/module12_contracts.test.py:512` | `if isinstance(mismatched, CanonicalOutcome)` selects the assertion |
| H3 | HIGH | `test/atdd/module12_contracts.test.py:821` | `if proposal["state"] == "executed"` selects the assertion |
| M4 | MEDIUM | `test/atdd/module12_contracts.test.py:1` (file) | 121 tests, no class/`describe` grouping |
| L6 | LOW | `test/atdd/module12_contracts.test.py:252, 608, 986, 994, 1066` | unnamed domain literals (33 / 1001 / 101 / 9999 / 50) |

### Quality Trends

First review of this file (no prior trend).

---

## Review Metadata

- **Workflow:** `bmad-testarch-test-review` (create mode; inline execution — skill not installed in repo, resolved from TEA module cache)
- **Registry:** TEA criteria registry, fixed severities, dedup by `row@file:line`
- **Review context:** red-phase ATDD suite; red status is intended and is not scored as a defect
- **Determinism of this review:** findings keyed to registry rows + file locations

## Reviewed Files
- `test/atdd/module12_contracts.test.py`

## Review Context
- `test/atdd/module12_interface.py` (interface stub — read only, not scored)
- `planning/detailed-design/contracts.md` (contract — read only, not scored)
- `test/test-design.md` (design — read only, not scored)

## Excluded From Review Set
- `test/atdd/conftest.py` (bootstrap, no tests)
- `tests/**` (separate green harness, not in this review scope)
- `test/nfr-evidence.md`, `test/test-design.md` (context artifacts)
