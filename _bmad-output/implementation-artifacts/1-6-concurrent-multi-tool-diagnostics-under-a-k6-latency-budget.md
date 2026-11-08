# Story 1.6: Concurrent multi-tool diagnostics under a k6 latency budget

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Nadia (and every other operator on shift),
I want a multi-tool diagnostic query to answer quickly even when 50 colleagues ask at once,
so that the Copilot stays usable at the busiest moment of the day.

## Acceptance Criteria

Source: `planning/epics.md` Story 1.6. Requirements: FR-04, FR-13, NFR-3, NFR-5, NFR-6, AD-1, AD-2, AD-12. Annex 12.5. Flow D (quality gate / NFR). Binding invariants: AD-1 → contracts §5 I18; AD-12 → contracts §5 I17; AD-2/AD-8 → contracts §5 I2, I3. Test design: `test/test-design.md` §6.3.5. Review: `reviews/review-impl2-shift-left.md` D-2.1 to D-2.6 (log I2-06).

1. **Concurrent independent reads, sequential evidence order.** Given the S1 fixture estate and `POST /api/v1/copilot/query`, when the orchestrator needs the policy and events reads for one query, then the independent read-only tool calls are dispatched concurrently with `asyncio.gather`, results are assembled in the fixed `EvidenceSet` order (positions unchanged vs. the sequential path, FR-14), and no tool call writes (AD-1).

2. **Safe failure, never a crash.** A tool call that exceeds the fan-out budget or fails returns the typed safe-failure answer (`PROVIDER_UNAVAILABLE`, HTTP 503), never an unhandled exception or HTTP 500 (AD-12). The budget is a wall-time `asyncio.timeout` around the gather, not a Clock-port read, so each turn still takes exactly one clock read (review D-2.5). No evidence is rendered from a partial fan-out.

3. **k6 at 50 operators.** Given 50 concurrent operators each sending `Why was student Alex denied access to model deepseek-coder?`, when k6 runs `tests/nfr/copilot-load.js`, then 100% of responses are HTTP 200 and cite `RULE-CAT-04`, `policy#catalog.4.2` and catalog entry `deepseek-coder` (100% cited accuracy, NFR-3), the measured p95 latency is strictly < 800 ms including queued single-writer latency (R1), and the run records 0 unhandled tool-timeout exceptions.

4. **Scope of the 800 ms budget.** The budget is measured with the deterministic fake prose adapter on one uvicorn worker. It is a story-level budget. NFR-6 (≥ 5 sessions) and the NFR-5 real-LLM budget (p95 ≤ 3 s) are unchanged and reported as a separate lane (Annex 12.5 adaptation, recorded in the decision log of this increment).

5. **Evidence archived.** The k6 summary (p95, p99, error rate) is saved to `docs/evidence/impl2/k6-12-5.json` by `k6 run --summary-export`, never hand-edited.

## Tasks / Subtasks

- [ ] Task 1: Parallel read dispatcher in the application ring (AC: 1, 2)
  - [ ] 1.1 Add `ParallelReads` in `src/application/` (stdlib only). Input: an ordered sequence of read thunks. It runs `asyncio.run(asyncio.gather(*(asyncio.to_thread(call) for call in calls)))` inside the worker thread, under `asyncio.timeout(budget)`.
  - [ ] 1.2 Reserve the recorder slots in argument order **before** the gather (story 1.5 D4). `ToolCallRecorder` appends in completion order otherwise. Mint tool-call ids before the gather as well (review D-2.3).
  - [ ] 1.3 Each thunk converts an unexpected exception to `Failure`. After the gather, report the first failure in **argument** order, never completion order (review D-2.4).
  - [ ] 1.4 Timeout → `Failure("PROVIDER_UNAVAILABLE")`. Cancellation reaches every child and the dispatcher awaits them, so no orphan tasks remain.
  - [ ] 1.5 Only independent reads fan out: `policy.for_model` and `event_store.query` (both need only the resolved user/model). Keep user and model resolution and `missing_policies` sequential, because they can end the turn (review §2).
  - [ ] 1.6 Budget is a setting (`M12_TOOL_FANOUT_BUDGET_SECONDS`, default chosen and recorded in the Dev Agent Record). It reads no clock.
  - [ ] 1.7 Docstring note on `ToolCallRecorder` that parallel fan-out must reserve slots in argument order (story 1.5 forward constraint).

- [ ] Task 2: Route stays synchronous (AC: 1)
  - [ ] 2.1 `ParallelReads` is called from inside the existing sync request path (`def` route on FastAPI's thread pool). `asyncio.run` inside a running loop raises, so the route must stay `def`. Add a route-audit assertion that `/copilot/query` and `/copilot/chat` are not `async def` (review §2, D-2.6).
  - [ ] 2.2 Do not change the ports (OP-1..OP-15) to async.

- [ ] Task 3: ATDD suite against the real app (AC: 1–3, test design §6.3.5)
  - [ ] 3.1 `tests/atdd/test_story_1_6.py`. Gates forced with `asyncio.Event` / `threading.Barrier`. No `sleep`, no `waitForTimeout`.
  - [ ] 3.2 Permutation cases: sequential baseline, forward, reverse and 3 seeded permutations. `EvidenceSet` membership, positions, citation ids and claim set are byte-identical to the sequential path. Repeat each 3×.
  - [ ] 3.3 Deterministic idgen: `answer_id`, `claim_id` and `tool_call_id` identical across permutations.
  - [ ] 3.4 Gate that never opens with budget 0 → `PROVIDER_UNAVAILABLE` 503, no partial evidence. One clock read per turn.
  - [ ] 3.5 One slow tool of N: remaining tasks cancelled and awaited; run under `-W error`; no "Task was destroyed but it is pending".
  - [ ] 3.6 Two tools fail completing in both orders → identical body (first failure in argument order). One tool raises, all tools raise → typed 503, never 500, no traceback.
  - [ ] 3.7 Every tool port records 0 mutating calls (AD-1, I18).
  - [ ] 3.8 Concurrency on a real SQLite file: 50 in-process requests across 50 sessions released by `Barrier(50)` → 50 × HTTP 200, 50 distinct `answer_id`s, audit rows = 50 × tool calls per query, 0 `database is locked`, 0 HTTP 500, `PRAGMA journal_mode` = `wal`.
  - [ ] 3.9 (integration, `tests/integration/`, not the ATDD file) Cross-store interleaving on the shared connection: store A fails mid-transaction (injected at the port) while store B commits. A's rows absent, B's present.

- [ ] Task 4: k6 load script (AC: 3, 5)
  - [ ] 4.1 `tests/nfr/copilot-load.js`: `constant-vus`, 50 VUs, 20 iterations each (1 000 requests). Each request opens its own session via `/copilot/query`.
  - [ ] 4.2 Thresholds: `http_req_failed` rate == 0, `checks` rate == 1.0 (status 200 **and** body cites `RULE-CAT-04`, `policy#catalog.4.2`, `deepseek-coder`), `http_req_duration` p(95) < 800. p99 and error rate recorded.
  - [ ] 4.3 No `sleep(` anywhere in the script. Follow the header style of `tests/nfr/smoke.js`.
  - [ ] 4.4 Extraction of `RULE-CAT-04` from the policy evidence `snippet` is a fixed pattern pinned by a unit test. Do not add a DTO field (contract unchanged).

- [ ] Task 5: Run and archive evidence (AC: 3, 4, 5)
  - [ ] 5.1 Uvicorn with one worker, `M12_DB_PATH=:memory:`: `python -m uvicorn src.adapters.inbound.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --log-level warning`. Wait with `curl --retry` on `/healthz`, not with a sleep.
  - [ ] 5.2 `k6 run --summary-export=docs/evidence/impl2/k6-12-5.json tests/nfr/copilot-load.js`.
  - [ ] 5.3 Repeat with `M12_DB_PATH` pointing to a temporary file. Record both results in the Dev Agent Record (p95, p99, error rate). Save logs under `docs/evidence/impl2/`.
  - [ ] 5.4 Server log scan for `Traceback` = 0.
  - [ ] 5.5 If p95 ≥ 800 ms: measure, optimise the writer hand-off or the dispatcher, and do **not** relax the threshold. If it still fails, stop and report (no threshold change without approval).

- [ ] Task 6: Makefile (optional, minimal)
  - [ ] 6.1 `make nfr` currently runs only `smoke.js`. Either extend that recipe with `copilot-load.js` in the same commit or record in the Dev Agent Record that it is run by hand. The CI job already runs every `tests/nfr/*.js`.

- [ ] Task 7: Regression and gates
  - [ ] 7.1 Before and after the change, run these queries through `POST /api/v1/copilot/query` and compare the output: S1 `Why was student Alex denied access to model deepseek-coder?`, S2 `Why can't Group 4 run their fine-tuning job right now?`, edge `Why was ghost_user_99 denied access to model deepseek-coder?`, S3 `Node ws-gpu-11 is cordoned with code ERR_THERMAL_88. What should I do?`, and 12.6 `Student Alex was denied model deepseek-coder. Diagnose and provide runbook.` Output must not change for any of them that already worked.
  - [ ] 7.2 `ruff check .`, `test/ci/schema_check.py`, `cmp src/dto.py planning/detailed-design/schemas/dto.py`, `diff` of both `sprint-status.yaml` copies, pytest with `--cov-fail-under=90`.
  - [ ] 7.3 Route audit (`tests/api/test_contract_routes.py`): no route added, so `SERVED_IN_THIS_STORY` and `openapi.yaml` stay as they are.

## Dev Notes

### Non-negotiable rules for this story

- Flow D. Code and ATDD in the same story. The k6 threshold is an acceptance gate; never relax it. If it fails after optimising, stop and ask (E.6).
- Ids come only from `idgen_port`. Time comes only from the `Clock` port. The dispatcher reads neither. It uses `turn.now` passed in.
- Pure logic stays in `src/domain`. The dispatcher lives in `src/application` and imports only stdlib and ports (R3, architecture import test).
- No `time.sleep`, `asyncio.sleep`, `setTimeout`, `waitForTimeout` or k6 `sleep()` in `src`, `tests` or `console`.
- Literals only from `src/domain/canonical_strings.py`.
- Never mock the unit under test. Fakes only at outbound ports (clock, idgen, prose, latency-gated tool adapters).
- The LLM never states a fact (AD-2, AD-8). Prose stays behind the existing guard.

### What already exists (do not rebuild)

- `EvidenceAssembler.gather` (`src/application/evidence_assembler.py`): reads `policy.for_model` then `event_store.query` sequentially, and already returns `Failure` with `PROVIDER_UNAVAILABLE` for a window edge. Extend it with the dispatcher, do not add a second assembler.
- `AccessDenialHandler` (`src/application/access_denial_handler.py`) orders a turn: resolve → `missing_policies` → gather → pure diagnosis → bind → prose → mint claims. Keep that order. Only the gather changes.
- `SessionService.submit_query` (`src/application/session_service.py`) takes one clock read inside the per-session guard, mints `answer_id` before the recorder turn, and writes audit rows after the pipeline inside one writer transaction (log I2-15 D1).
- `ToolCallRecorder` and the generic `audited()` wrapper (`src/application/tool_audit.py`): ambient through `contextvars`. `asyncio.to_thread` copies the context, so recording keeps working in worker threads (log I2-15 D4).
- `SqliteWriter` (`src/adapters/outbound/db/sqlite_writer.py`): one connection, one `RLock`, `BEGIN IMMEDIATE`. Concurrency safety rests on it; do not open a second writer.
- `tests/nfr/smoke.js`: header and threshold conventions to copy.

### Design decisions (from the review, confirmed in the log)

- **Order (D-2.1).** `gather` returns argument order. Positions are assigned after the gather by the pure domain over that tuple. Never `as_completed`; never append inside a task.
- **Clock (D-2.2).** Tasks receive `turn.now`. One read per turn stays true (contracts `answer_query` P3, R2).
- **Ids and audit (D-2.3).** No task mints an id or writes an audit row. Tool-call ids are minted before the gather in fixed tool order. Audit rows are written after it in the same order.
- **Failure (D-2.4).** First failure in argument order is reported. No evidence is emitted on any failure.
- **Timeout (D-2.5).** `asyncio.timeout(budget)` around the gather is wall-time infrastructure, stamps nothing, and is not a clock read. Test-design rows that measure a tool on the fake clock are superseded by the rows in §6.3.5 as written.
- **Where the loop lives (D-2.6).** Request path and ports stay sync. `ParallelReads` runs `asyncio.run` inside the worker thread. A route that calls it must stay `def`. Going async end to end was considered and rejected: it would require rewriting the per-session guard and the store for no latency gain on in-process fakes.

### Current state of the files this story changes

- `src/application/evidence_assembler.py`: sequential `for_model` then `query`. Changes to call `ParallelReads` for these two independent reads. Its `Failure` shapes and the window edge handling stay identical.
- `src/application/tool_audit.py`: `ToolCallRecorder.record` appends in call order. With fan-out it must receive pre-reserved slots (Task 1.2). Also note the open deferred item: `audited` computes params for every call even with no active turn (see deferred work). Measure under k6 before changing it.
- `src/application/session_service.py`: unchanged except if the budget setting is passed through `Settings`.
- `src/adapters/inbound/copilot.py`: `copilot_query` stays `def`. Add the route-audit assertion only.
- `src/config.py`: new setting `M12_TOOL_FANOUT_BUDGET_SECONDS`.

### Previous story intelligence (1-5)

- Story 1.5 deliberately left a forward constraint: a parallel fan-out appends in completion order, so `ParallelReads` must reserve recorder slots in argument order before the gather (1.5 D4; deferred work).
- 1.5 mutation work showed that tests passing by scan order or hash order hide mutants. For fan-out, make the expected order differ from insertion order in at least one case (completion order forced by gates, not by luck).
- 1.5 ATDD redaction case: put the secret in an entity slot so it reaches a port parameter. Apply the same discipline to the new gates: each case must fail if the behaviour breaks.
- Deferred 1-5: `audited` builds bound params and `_dump` on every port call even with no active turn, and `/state` browse pages up to 100 times for `total`. Measure under the k6 budget before optimising (check the recorder is active first).

### Git intelligence

- Recent commits on `impl-2`: story 2.4 (executor, proposal id fix I2-33), then docs for trap audit and epic 2 closure. Story 2.4 changed the copilot route area (`/copilot/chat`) and the executor; expect merge-free edits but re-run the regression script.

### Latest tech notes

- k6: use `constant-vus` (50 VUs × 20 iterations) or `per-vu-iterations`. Do not use `sleep()`. `--summary-export` writes the JSON used as evidence.
- FastAPI: a `def` route runs in the thread pool (anyio default limit 40 threads). With 50 concurrent requests the pool may queue; measure, do not raise the limit without evidence. If the limit is raised, record the number and reason in the log.
- Python 3.11 `asyncio.timeout` is available (used for the wall budget).

### Project Structure Notes

- New code: `src/application/parallel_reads.py` (or the existing `evidence_assembler.py` if the helper stays small). Tests: `tests/atdd/test_story_1_6.py`, `tests/unit/` for pattern extraction and dispatcher ordering, `tests/api/` for the route audit.
- Evidence: `docs/evidence/impl2/k6-12-5.json`, the file-DB run log and the hammer report. Never hand-edited.
- The repository layout is `src/{domain,ports,application,adapters}` (log AD-03). `epics.md` paths `service/...` do not apply.

### References

- [Source: planning/epics.md#Story-1.6]
- [Source: reviews/review-impl2-shift-left.md §2 (D-2.1 to D-2.6), §4 (concurrency test seam)]
- [Source: test/test-design.md#6.3.5]
- [Source: _bmad-output/implementation-artifacts/1-5-tool-call-audit-log-and-state-inspection-viewer.md#Decisions (D1, D4)]
- [Source: docs/ai-decision-log.md I2-06, I2-15]
- [Source: planning/detailed-design/contracts.md §5 I2, I3, I17, I18; `answer_query` P3, R2]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Story created in ready-for-dev state. Open decision for the dev run: the Task 2 route shape (sync `def` per review D-2.6). Any different route shape changes the review decision and must be logged before code.

### File List
