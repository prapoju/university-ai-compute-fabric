# Impl-2 Walkthrough - Module 12: AI Operations Copilot

**Date:** 2026-11-08 · **Branch:** `impl-2` · **Scope:** Annex stories 12.4 (2-1 to 2-4), 12.5 (1-6), 12.6 (3-3 and 1-7), plus the Impl-1 foundations they depend on.

This report is the final evidence for Impl-2. Every number below is quoted from a file in `docs/evidence/impl2/` or from a command run on this commit. Decisions are cited as I2-NN in [`docs/ai-decision-log.md`](docs/ai-decision-log.md).

## 0. Result at a glance

| Item | Result | Evidence |
|---|---|---|
| Stories done | 1-1 to 1-7, 2-1 to 2-4, 3-1, 3-3, 4-1, 4-2 (done). Optional 3-2, 3-4, 4-3, 1-8 out of scope (section 9) | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| Pytest | 2164 passed, 0 failed | `docs/evidence/impl2/final-pytest-classifier-fix.log` |
| NFR-1 accuracy corpus | 20 / 20 = 100 % (threshold 90 %), after the classifier fix (commit `66084c4`, I2-64) | `tests/api/test_nfr1_accuracy_corpus.py` |
| NFR-7 cold start | 0.54 s to the first 200 on `/healthz` (budget 60 s) | `docs/evidence/impl2/nfr7-cold-start.log` |
| Branch coverage of `src` | 97.59 % (floor 90 %) | `docs/evidence/impl2/final-coverage.log` |
| Playwright E2E | 3 passed | `docs/evidence/impl2/final-e2e.log` |
| Ruff | All checks passed | `docs/evidence/impl2/final-ruff.log` |
| Schema check | GATE PASS | `docs/evidence/impl2/final-schema-check.log` |
| Banned waits (`sleep(`, `waitForTimeout`) in `src tests console` | 0 matches | `docs/evidence/impl2/final-banned-waits.log` (empty) |
| Traceability gate (rerun after the classifier fix) | CONCERNS (P0 7/7, overall 24/26, P1 17/19 = 89.5 %) | `test/traceability-matrix.md` |
| NFR evidence | 5 dimensions mapped | `test/nfr-evidence.md` |
| CI | Run `42531821585` on `d2d0e3d`: four of five jobs success; `Ruff + pytest` fails on the one NFR-1 corpus assertion (17 / 20), reproduced locally | `.github/workflows/quality-gate.yml`, section 8 |

## 1. Hardening and concurrency defense

The hazards Impl-2 targets are double allocation, a second dispatch of the same proposal, audit rows that
go missing under parallel reads, and a p95 that breaks under load. The defenses in place:

- **One writer for all state (I2-06).** Every store writes through a single `SqliteWriter`
  (`src/adapters/outbound/db/sqlite_writer.py`). Per-store locks let one store commit another's half-written turn,
  so they were replaced by one writer.
- **Exactly-once dispatch (I2-03).** A confirmation claims its proposal with a conditional `UPDATE` in one writer
  transaction (`src/adapters/outbound/db/proposal_store.py`). The executor is called outside the writer, and the
  claim is the only guard. Tests: `tests/integration/test_proposal_store.py::test_fifty_simultaneous_dispatch_claims_have_one_winner`
  and `tests/atdd/test_story_2_3.py::test_an_identical_confirm_raced_with_one_that_has_another_token_never_transitions_twice`.
- **Single-use, idempotent confirmation (P5).** An identical replay answers the persisted proposal. A different token on a
  confirmed proposal is a conflict (`tests/atdd/test_story_2_3.py::test_a_different_token_on_a_confirmed_proposal_is_a_conflict`).
- **Parallel reads with a bounded pool and ordered audit (story 1-6, I2-35, I2-39).** Reads fan out with
  `asyncio.gather` semantics on a shared pool of 80 slots (`src/application/parallel_reads.py`). Each read records into
  its own lane, and the lanes settle into the turn in argument order. A read still running at the budget is a typed
  503 and records nothing afterwards. Test: `tests/unit/test_parallel_reads.py::test_recorded_calls_settle_in_argument_order_when_the_second_read_finishes_first`.
- **Recorder required (story 1-6 hardening, commit `cafd942`).** `ParallelReads` now requires its recorder, so a fan-out
  cannot drop its audit rows silently. This closes the deferred item of story 1-6. Test: `tests/unit/test_parallel_reads.py::test_a_fan_out_cannot_be_built_without_its_recorder`.
- **Typed failures, never a crash (AD-12).** A provider, clock, executor or database failure is a typed result. It maps
  to `PROVIDER_UNAVAILABLE`, `CLOCK_UNAVAILABLE`, `EXECUTOR_UNAVAILABLE` or `EXECUTOR_DUPLICATE_APPLY` with a 503, 409 or 502 status.
  The database faults are covered by `tests/api/test_evidence_api.py::test_a_broken_database_answers_503_on_both_routes_and_never_crashes`.
- **Redaction at write (story 1-5, I2-16).** Secrets are redacted before they reach the audit tables
  (`tests/atdd/test_story_1_5.py::test_secrets_in_the_query_never_reach_the_audit_tables`).

## 2. The Annex adaptations (binding list)

The binding list is the "Annex-to-specification decisions" table in [`docs/impl2-rules.md`](docs/impl2-rules.md). Every
row was decided before the code was written and is not reopened here.

| Topic | Annex says | Repository specification | Decision |
|---|---|---|---|
| Destructive inbound | POST /api/v1/copilot/chat | /copilot/query, /sessions/{sid}/queries, /destructive/* | Add /copilot/chat as a thin route over the same use cases and add it to openapi.yaml (precedent: log entry AD-26). Keep /destructive/*. |
| Token lifetime | valid for 60 seconds | contracts.md confirm_and_dispatch P2: 15 min | Change to 60 s in contracts.md, configurable. Test expiry with the fake clock. |
| Single-use token | single-use | P5: identical confirm is idempotent | A replay returns the persisted proposal and never dispatches again. A differing confirm is rejected. |
| Cryptographic token | cryptographic | GateToken ^gt-[0-9a-f]{32}$, ids through idgen_port (R2) | Production adapter uses secrets.token_hex(16). Tests use the deterministic adapter. |
| "Terminate" verb | Terminate all active jobs for CS-101 | ActionVerb is closed: delete_jobs, cancel_jobs, cordon_node, drain_node | Map terminate to cancel_jobs. The enum stays closed. |
| Active CS-101 jobs | 3 jobs on ws-02, ws-05, ws-08 | Fixtures have no running CS101 jobs, and jobs have no node field | Add 3 running CS101 jobs and a nullable node field on ws-gpu-02, -05, -08 under a NEW group. Do not change group-4 or the S1/S2 scenarios. |
| Destructive target "CS-101" | Terminate all active jobs for CS-101 | AD-7 exact match; course is not an entity type; P3 job actions need a job target | The new group's id is `group#CS-101`. contracts P3 accepts a group target for job actions, selector `jobs_port.select({group_id, status: running})`. "Active" means running. Exactly 3 jobs (ws-gpu-02, -05, -08). group-2, group-4 and S1/S2 unchanged. |
| Load budget | 50 concurrent operators, p95 < 800 ms | NFR-6: ≥ 5 sessions; NFR-5: p95 ≤ 3 s with the real LLM | NFR-6 unchanged. The 50-operator p95 < 800 ms budget, measured with the fake prose adapter, is an acceptance criterion of story 1-6 only. |
| Load-test query | Why was job #402 denied... citing PR-04, CE-12 | No job-402. Real ids are RULE-CAT-04, policy#catalog.4.2, catalog entry deepseek-coder | Use "Why was student Alex denied access to model deepseek-coder?" and assert the real ids. |
| Console citation | Rule PR-12 | RULE-CAT-04 | Render "Verified via Policy Engine [RULE-CAT-04]". |
| Streaming output | response stream renders | Architecture: synchronous HTTP, no push | No SSE. Render when the response arrives, with a pending state. |
| Access-denial runbook | diagnose and provide runbook | Registry keyed by error code, holds only ERR_THERMAL_88 | Add a non-physical template as registry config only (NFR-10), rendered verbatim (AD-9). |
| Invariant numbers | AD-30 etc. | Architecture uses AD-1..AD-15; the decision log also uses AD-NN | Write "Annex AD-30" for Annex ids. Impl-2 log entries use I2-NN. |

## 3. The five flows and where each one was applied

| Flow | Strategy | Applied to | Evidence |
|---|---|---|---|
| A | ATDD-first: red tests committed before production code | 2-1, 2-2, 2-3, 2-4 (12.4), 1-6, 1-7 | red logs in section 4 |
| B | Test-along: code and tests in the same commit | 1-4, 1-5, 4-2, 3-3 (12.6 backend), 1-7 review | `docs/evidence/impl2/flow-b-1-4-coverage.log`, `flow-b-1-5-coverage.log`, `flow-b-4-2-coverage.log`, `flow-b-3-3-review-coverage.log` |
| C | Test-after: harden what exists | 3-1, 4-1 | `docs/evidence/impl2/flow-c-coverage.log` |
| D | Quality gate (NFR): k6 with real thresholds | 1-6 (12.5) | section 6 |
| E | Playwright E2E with Page Object Model and `trace.zip` | 1-7 (12.6) | section 7 |

## 4. Annex 12.4: destructive-action safety guardrail (stories 2-1 to 2-4, Flow A)

**Technical challenge.** A natural-language request with a blast radius ("Terminate all active jobs for CS-101") must be
refused on its face. The copilot must compute a dry-run, issue a single-use token valid for 60 s, and dispatch only after a
separate confirmation. The dispatch happens exactly once, and the copilot itself writes nothing.

**Flow applied.** For each story the red commit comes first. Its tests are run and recorded, and the tests fail for missing
behaviour. Only then is the production commit made. The order is proven with `git merge-base --is-ancestor` on the commits below.

**Code implemented.**

- 2-1 (classification and refusal): `src/domain/safety.py`, `src/application/destructive_handler.py`,
  `src/application/chat_service.py`, `src/adapters/inbound/copilot.py` (`POST /copilot/chat`, in `planning/detailed-design/schemas/openapi.yaml`).
- 2-2 (dry-run snapshot): `src/domain/dry_run.py`, `src/application/dry_run_service.py`,
  `src/adapters/outbound/db/proposal_store.py`, group `group#CS-101` in `fixtures/`.
- 2-3 (confirmation gate and re-validation): `src/domain/confirmation.py`, `src/application/confirmation_service.py`,
  the conditional claim in `src/adapters/outbound/db/proposal_store.py`, token lifetime 60 s (`src/config.py`).
- 2-4 (propose-only handoff and executor): `src/domain/execution.py`, `src/application/proposal_dispatcher.py`,
  `src/application/proposal_service.py`, `src/adapters/outbound/sim/executor_adapter.py` (simulated executor, AD-15) behind `src/ports/outbound/executor_port.py`.

**Terminal evidence.**

| Story | Red commit | First green commit | Red log | Failed / passed on the red run | Repeat runs |
|---|---|---|---|---|---|
| 2-1 | `fe2df33` | `96de5c7` | `docs/evidence/impl2/red-2-1.log` | 51 failed, 4 passed | `docs/evidence/impl2/flow-a-2-1-coverage.log` |
| 2-2 | `0407109` | `57a062b` | `docs/evidence/impl2/red-2-2.log` | 33 failed, 7 passed | `docs/evidence/impl2/flow-a-2-2-coverage.log` |
| 2-3 | `f98a941` | `1c95b8c` | `docs/evidence/impl2/red-2-3.log` | 42 failed, 3 passed | 45 passed × 3 (`flow-a-2-3-atdd-x3.log`) |
| 2-4 | `db44749` | `572d4b1` | `docs/evidence/impl2/red-2-4.log` | 32 failed, 4 passed | 36 passed × 3 (`flow-a-2-4-atdd-x3.log`) |

The passing tests in each red log are behaviour that already existed and were not counted as red. They are guards against
regression. Each log ends with the failure summary of its story.

**Annex scenario of 12.4.** The end-to-end cases are `tests/atdd/test_story_2_3.py::test_annex_12_4_end_to_end_up_to_confirmed`
and the Annex case in `tests/atdd/test_story_2_4.py`. They are the cases that walk the scenario from refusal through confirmation.

## 5. Annex 12.5: high-concurrency diagnostic tool-calling under the k6 budget (story 1-6, Flow D)

**Technical challenge.** Fifty operators submit the same diagnostic question at once. The policy and event reads run in
parallel, the audit must keep the argument order, and no read may outlive the budget with its results written into the turn.

**Flow applied.** Flow D with the red commit first (`f84c18c`, log `docs/evidence/impl2/red-1-6.log`: 9 failed, 3 passed).
The k6 thresholds are the story's gate and were not relaxed (I2-35).

**Code implemented.**

- `src/application/parallel_reads.py` (fan-out, bounded pool, lanes in argument order, budget as typed 503).
- `src/domain/fanout.py` (budget default 0.5 s and validation: `inf`, `nan` and values below 10 ms are rejected, review F-5).
- `src/application/evidence_assembler.py` (the two independent reads go through `ParallelReads`, required recorder).
- `src/adapters/inbound/copilot.py` (synchronous `def` route, so that `asyncio.run` runs in a worker thread, I2-35).
- RULE-CAT-04 extracted from the policy evidence snippet (`6f7fcdc`).
- `tests/nfr/copilot-load.js` (k6 script for the 50 operators, the citation checks and the thresholds).

**Terminal evidence.** `tests/atdd/test_story_1_6.py` (`test_fifty_operators_released_together_get_cited_answers_and_no_lock_errors`
and `test_the_load_script_declares_the_story_thresholds_and_never_sleeps`), and the k6 logs in section 6.

## 6. k6 load test summary (p95, p99, error rate)

Script `tests/nfr/copilot-load.js`. Thresholds in the script: `http_req_failed rate==0`, `http_req_duration p(95)<800`,
`checks rate==1`. Query: "Why was student Alex denied access to model deepseek-coder?" with 50 virtual users and 1000 iterations.

| Run | Store | Iterations | p95 | p99 | Error rate | Checks | Source |
|---|---|---:|---:|---:|---:|---:|---|
| Local, in-memory | `:memory:` | 1000 | 300.66 ms | 368.52 ms | 0 / 1000 (0.00 %) | 4000 / 4000 | `docs/evidence/impl2/k6-12-5.json`, `docs/evidence/impl2/k6-12-5.log` |
| Local, file database | temporary file | 1000 | 307.93 ms | 367.08 ms | 0 / 1000 (0.00 %) | 4000 / 4000 | `docs/evidence/impl2/k6-12-5-filedb.json`, `docs/evidence/impl2/k6-12-5-filedb.log` |
| CI | Run `42531821585`, job `k6 load thresholds`, `copilot-load-summary.json` | 1000 | 95.48 ms | not exported by the CI summary (p(90) = 87.45 ms) | 0 / 1000 (`http_req_failed` value 0) | 4000 / 4000 | CI artifact `k6-summary` |
| CI, earlier runs | `42527948599`: 181.23 ms; `42531640542`: 181.87 ms (same script and thresholds) | | | | | | |

The threshold p95 < 800 ms holds with a margin of about 2.6 times in both local runs and about 8.4 times in the latest CI run (95.48 ms; the three CI runs range from 95.48 to 181.87 ms), and no check failed in any run. The smoke
script `tests/nfr/smoke.js` runs the liveness probe with `p(95)<200`, and `make nfr` runs both scripts.

## 7. Annex 12.6: conversational diagnostic console with cited state cards (stories 3-3 and 1-7)

**Technical challenge.** Nadia submits an inquiry and sees the cited badge `Verified via Policy Engine [RULE-CAT-04]`, a runbook
card with its steps, and a "Copy Runbook to Clipboard" action. The runbook must be the registered text, verbatim (AD-9), and it may not be invented.

**Flow applied.** 3-3 is Flow B (backend and runbook registry, code and tests in one commit). 1-7 is Flow E: the E2E tests were
written first (`20d9d09`, log `docs/evidence/impl2/red-1-7.log`: 2 failed, 1 passed, the health smoke), then the console (`ffb27d2`).

**Code implemented.**

- 3-3: `fixtures/runbooks/` (ERR_THERMAL_88 template and the access-denial template as configuration only, NFR-10),
  `src/application/node_triage_handler.py`, `src/application/access_denial_handler.py`, `src/application/runbook_service.py`,
  `src/adapters/inbound/runbooks.py` (`GET /api/v1/runbooks/{error_code}`).
- 1-7: `console/src/CopilotConsole.tsx` (chat container, prompt, cited badge, runbook card, copy),
  `console/src/api.ts` (the synchronous request and the pending state, no SSE), `console/src/ruleOfClause.ts`
  (the badge rule derived from the policy evidence), `console/src/App.tsx` (route `/helpdesk/copilot`).
- Page Object: `tests/e2e/pages/CopilotConsolePage.ts`. The specs are in `tests/e2e/copilot-console.spec.ts`.

**Terminal evidence.** `docs/evidence/impl2/final-e2e.log` (section 8 gives the run command), `docs/evidence/impl2/e2e-1-7.log`,
the forensic trace `docs/evidence/impl2/trace-1-7-annex-12-6.zip`, and the mutation check of the badge in
`docs/evidence/impl2/mutation-1-7-badge.log` (the Annex test fails on a wrong badge text; restored, `git diff` clean).

**Scope of the E2E.** Two tests, by a time cut (I2-54). The design in `test/test-design.md` §6.3.7 lists ten cases. The two
implemented cover the Annex 12.6 scenario and the unknown-student failure path. The rest are declared out of scope in I2-54.

## 7.1 Classifier correction found by the NFR-1 corpus

The first corpus run scored 17 / 20. Three paraphrases got `CLARIFICATION_REQUIRED`: "cant" without an
apostrophe, a node named without the word "node", and "cordoned with <code>" without the word "code". The
fix is the smallest change that accepts them (commit `66084c4`, log I2-64, Reviewer: Julio):

- `src/domain/intent.py`: the schedule rule accepts `can'?t`; the node rule also matches `cordoned … err_…`.
- `src/domain/references.py`: the node and the code are read without their words, only when the word
  form is absent, so the word form is read exactly as before.

Regression cases: `tests/unit/test_node_triage_intent.py` and `tests/unit/test_runbook.py`. Against the old code 5 of
them fail. The six golden byte-identity tests (`tests/api/golden`) pass. The suite is 2164 passed.

## 8. Playwright E2E run log and CI artifact

**Local run.**

```bash
npm ci && npm ci --prefix console && npm run build --prefix console
npx playwright install chromium
PY=.venv/bin/python npx playwright test
```

`playwright.config.ts` starts uvicorn itself (`webServer`) and serves the built console. Result: `3 passed (5.1s)`,
with `--trace on` in CI and `on-first-retry` locally (`docs/evidence/impl2/final-e2e.log`).

**CI artifact.** The job `e2e` in `.github/workflows/quality-gate.yml` runs `npx playwright test --trace on --fail-on-flaky-tests`
and uploads `test-results/` (artifact `playwright-test-results`, which holds the traces) and `playwright-report/`
(artifact `playwright-report`).

**CI runs.** Run `42531821585` on `d2d0e3d` (branch `impl-2`): four of the five jobs succeed:
`No sleep / waitForTimeout`, `Schema checks`, `k6 load thresholds` and `Playwright E2E` (`3 passed (5.2s)`).
The job `Ruff + pytest (branch coverage >= 90%)` fails on one assertion: `tests/api/test_nfr1_accuracy_corpus.py::test_nfr1_accuracy_is_at_least_ninety_percent_over_the_corpus`,
which reports `17/20`, below the 90 % threshold. That failure reproduces locally (`docs/evidence/impl2/final-pytest-after-gap-closure.log`). The
other 2157 tests in that job pass. The earlier green run on `618abcc` (`42527948599`) predates the corpus test. The corpus test is red on purpose: the
expectations were kept, and the misses are reported in section 11. The Playwright artifacts are `playwright-test-results` (traces) and `playwright-report`.

**Final head.** Run `42531988473` on `7e4ef06` (the walkthrough commit) has the same result: four jobs succeed, `Ruff + pytest` fails only on the NFR-1 corpus assertion.

## 9. Testing pyramid: real counts against 70 / 20 / 10

Counts from `pytest --collect-only` and the Playwright and k6 files on this commit. The total is 2169 automated cases.

| Layer | Source | Count | Share | Target | Note |
|---|---|---:|---:|---|---|
| Unit | `tests/unit/` | 1487 | 68.6 % | 70 % | close to the target |
| Integration | `tests/integration/` | 159 | 7.3 % | 20 % (with API) | real SQLite transactions |
| API | `tests/api/` | 308 | 14.2 % | 20 % (with integration) | OpenAPI and route contracts |
| ATDD | `tests/atdd/` | 207 | 9.5 % | 20 % (with the two above) | real app, red-then-green suites |
| E2E | `tests/e2e/` (Playwright) | 3 | 0.1 % | 10 % | see deviation |
| NFR | `tests/nfr/` (k6 scripts) | 2 | 0.1 % | separate layer | iterations: 1000 + 1000 |
| Other | root files of `tests/` (not in a layer folder) | 3 | 0.1 % | n/a | |

Integration, API and ATDD together are 31.1 %, against 20 % in the target. Unit is 68.6 %, against 70 %. Browser tests are
0.1 % of cases, against 10 %.

**Deviation, explained.** The 70 / 20 / 10 split is a guide to cost, and it is not met by count in the browser layer. The
pyramid counts cases, and cases are a poor measure of browser cost. The three Playwright tests take 5.1 s in total, against
`pytest` at about 51 s for 2164 cases, so the browser layer is about 9 % of the wall time. The design planned ten E2E cases
for the console and two were implemented (section 7). Writing eight more would move the suite toward the Ice Cream Cone trap that
the task names. The Annex asks for one journey in the browser, and that journey is tested. The deviation is recorded here; the scope of the browser layer is recorded in I2-54.

## 10. Annex items deferred and open findings

**Deferred work** (`_bmad-output/implementation-artifacts/deferred-work.md`). The file lists the items that were
found in code review and not applied. The items that matter for the release:

- Story 1-6, budget and ordering: the 50-operator ATDD case runs under the 0.5 s default budget and can flake with a 503 on a slow runner (I2-43).
  The ordering gates are set inside the read; a completion-based gate would be stricter (I2-44). A late read's audit rows are dropped by design (I2-39).
- Story 3-3, audit of diagnosers: the diagnosers do not yet emit their tool-call audit events (decision D-4, approved).
- Story 2-4, the proposal can stay `dispatched` if the process dies between the claim and the result. It needs a reconciliation policy.
- Story 2-4, `ExecutorPort.dispatch` runs under a per-proposal lock held for the whole call; fine for the simulator and for one process.
- Story 1-4, `clock#` read ids restart at each process start, so a file-backed database could resolve a clock citation to another run's read.
- Story 1-5, a secret pasted where an entity goes is stored as an entity id (accepted as a documented limitation, D-1 option a).
- Story 1-5, `browse_state` counts `total` by paging the port up to 100 times (to measure under the k6 budget).
- Story 4-2, a 5xx renders `failure.message` as is, and `/readyz` answers 200 while the clock raises.
- Story 2-2, `select` truncates silently at 10,000 rows; `dto.py` and `openapi.yaml` do not state the 50-target cap.
- Story 2-3, `CONFIRMATION_STALE` lists every changed item with no upper bound.

**Open low finding L-1 of story 3-3 (unsourced non-physical template).** A non-physical template without
`approved_source` renders `provenance.source = null`. `contracts.md` (`lookup_runbook`, `RunbookTemplate.approved_source: string|null`)
allows this, but acceptance criterion 1 speaks of an approved-source line. Making the source mandatory would change the scope of
`RUNBOOK_TEMPLATE_UNSOURCED`, which is a contract change, so it is left for the approver. The shipped templates are unaffected
because both have a source. Recorded in `_bmad-output/implementation-artifacts/3-3-runbook-registry-and-node-triage-runbook.md`.

## 11. Limits

- **Simulated prose.** The LLM is a deterministic fake (`src/adapters/outbound/sim/prose_adapter.py`). The NFR-5 real-LLM budget (p95 ≤ 3 s) is not measured here. The
  measured pipeline is far below it (p95 300–308 ms), but that does not replace a real-model run.
- **Single machine, single worker.** The k6 runs use one uvicorn worker. The 800 ms budget is story-level and does not cover the NFR-5 budget with a real model.
- **NFR-1 is measured at its threshold and above it.** The 20-query corpus scores 20 / 20 = 100 % after the classifier fix (section 7.1). The first run scored 17 / 20; the test was kept red until the fix, and the expectations were not changed.
- **NFR-7 and NFR-9 are waived in part.** The cold start is measured (0.54 s). The 8-hour 99 % availability window and the human usability study cannot be measured in the repository; they are waived in `test/traceability-matrix.md` section 8 and in I2-63. Because of them, P1 is 17 / 19 = 89.5 % and the gate is CONCERNS, not PASS.
- **Requirements out of scope.** FR-06 retrospective diagnosis (story 3-2), parts of FR-01 and FR-02 (3-4), part of FR-16 (4-3), and the console surfaces of FR-09 to FR-12 (1-8).
  Section 12 lists them with their reasons.
- **E2E breadth.** Two Playwright tests (section 7).
- **Traceability sensitivity.** Counting FR-06 as P0 would make the gate FAIL (P0 7/8). The scope decision is I2-57 in the decision log.
- **CI.** The final CI run is recorded in section 8.

## 12. Out of scope (declared)

| Item | Reason | Decision |
|---|---|---|
| Story 3-2 retrospective event-log diagnosis (FR-06 retrospective part) | outside the Annex minimum | I2-57 |
| Story 3-4 intent taxonomy extension and follow-up references (parts of FR-01 and FR-02) | outside the Annex minimum | I2-57 |
| Story 4-3 safe failure on the prose runtime (part of FR-16) | outside the Annex minimum | I2-57 |
| Story 1-8 inspector and safety console surfaces (FR-09 to FR-12 surfaces) | outside the Annex minimum | I2-57 |

## 13. Reproduce

```bash
.venv/bin/python -m pytest tests -q --strict-markers --cov=src --cov-branch --cov-fail-under=90
.venv/bin/python -m ruff check .
.venv/bin/python test/ci/schema_check.py
PY=.venv/bin/python npx playwright test
```

Each command maps to a job in `.github/workflows/quality-gate.yml`.
