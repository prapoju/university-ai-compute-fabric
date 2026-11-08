---
baseline_commit: 3054c0a
---

# Story 2.4: Propose-only handoff, simulated executor and executor-failure safety

Status: ready-for-dev

<!-- Impl-2 Flow A (ATDD-first), Annex 12.4, last of four stories (2-1 .. 2-4). The red phase is
     recorded BEFORE any production code. This story completes the Annex: after the confirm claim the
     dispatcher hands the proposal to the executor port exactly once; the simulated executor is the
     only writer of simulated state; the result is recorded with an `actor = executor` audit row; an
     unavailable, late or partial executor leaves a safe, visible `failed` proposal; a failed one can
     be re-dispatched as a new proposal; and the four contract routes still not served are served.
     Decisions D1-D14 were applied by the story author following the contract, the task statement and
     the rubric. D1 (it changes a committed ATDD, guide E.6), D2, D5, D7 and D9 touch the contract or
     the behaviour of earlier stories: the user confirms them before the red phase is committed. -->

## Story

As Nadia,
I want a confirmed proposal handed to the executor under a frozen contract while the Copilot stays mutation-free,
so that the Copilot never executes, and the difference is visible in the console.

## Acceptance Criteria

Source: `planning/epics.md` Story 2.4 (the console criteria of UX-DR8, the delegation card labels and the `alertdialog`, belong to stories 1-7 and 1-8), `test/test-design.md` section 6.3.4, `docs/impl2-rules.md`, task statement Annex 12.4 (pages 30-31 of the PDF). Requirements: FR-10, FR-16 (executor failure), AD-1, AD-3, AD-13, AD-15, PD-6, D31, D32, D33. Contracts: `confirm_and_dispatch` P5, P6, Q1-Q3, Q-fail, L1, L2; `post_confirm`; `get_proposal`; `post_re_dispatch`; `executor_post_proposal`; `executor_get_proposal`; OP-15; section 5 I9, I10, I18, I21; catalog `EXECUTOR_UNAVAILABLE`, `EXECUTOR_PARTIAL_APPLY`, `EXECUTOR_DUPLICATE_APPLY`, `PROPOSAL_STATE_INVALID`, `PROPOSAL_NOT_FOUND`, `GATE_TOKEN_INVALID`, `DRY_RUN_EMPTY_SET`, `VALIDATION_MALFORMED_BODY`.

1. **The Annex scenario runs to `executed` (D1, FR-10).** Chat with `Terminate all active jobs for CS-101`, then `POST /destructive/proposals` with the token: HTTP 200, a `Proposal` in `executed` with `confirmation` (caption `S_CAP`) and `executor_result = {status: applied, applied_records: [job#job-8901, job#job-8902, job#job-8903], applied_count: 3, timestamp, source: executor}`. The row went `dry_run -> confirmed -> dispatched -> executed` (one transition each). `GET /state/jobs/job-8901`, `-8902` and `-8903` now report `cancelled`; no other record of the estate changed.
2. **The Copilot writes nothing; only the executor mutates (AD-1, AD-3, D2).** Every record of the nine read-only stores is identical before the dry-run and after it, and before the confirm and after it, **except** the items the executor applied. A static check keeps it: no port of the provider ring has a write method, and only the simulated executor adapter holds a write handle to the stores.
3. **Exactly one executor call per confirmed proposal (I10, AD-3).** Two confirms raced on `Barrier(2)`, and 50 on `Barrier(50)`, make exactly one `executor.dispatch` call, one `actor = executor` audit row and one `dispatched -> executed` transition; every response is a 200 `Proposal` in `executed`, 0 HTTP 500. A sequential identical replay answers the persisted `executed` proposal and calls the executor 0 more times.
4. **The audit tells the Copilot's proposal from the executor's mutation (FR-10, AD-10, D9).** After the Annex confirm the session audit has the copilot rows of the dry-run and the confirm, and exactly one more row with `actor = executor`, `tool_call_id = null`, `proposal_id` set, `result_summary.tool_name = executor.dispatch`, `status` and `applied_count`, and the timestamp of the executor's **own** clock read (E44). The row never holds the token. A second row with `actor = executor` for the same `proposal_id` is impossible (the unique index) and surfaces as a typed failure, never a second success.
5. **The frozen request is forwarded verbatim (AD-15, D6).** The dispatcher sends `{proposal_id, action, selector, gate_token, dry_run_ref: {proposal_id}}` and nothing else: the persisted selector and the stored token, never a re-derived scope. `POST /executor/v1/proposals` with a `dry_run_ref.proposal_id` that differs from `proposal_id`, an extra field or a missing one answers 400 `VALIDATION_MALFORMED_BODY`, and applies nothing.
6. **The executor applies the snapshot's items by key and nothing else (Q1, Q2, D13).** It never re-enumerates scope. An item that is no longer actionable when it is applied (a job that finished in the window of the 2-3 review item D-1) is skipped, and then `applied_count < len(affected_items)`: the result is `partial`, never a success larger or silently smaller than the scope.
7. **An unavailable executor is a safe, visible failure (FR-16, D31, D4).** With the executor down, the confirm answers 503 `EXECUTOR_UNAVAILABLE`; the proposal is `failed` with its snapshot and confirmation preserved and no `executor_result`; no `actor = executor` row; the estate is unchanged; advancing the fake clock 10 minutes triggers no second call (no auto-retry).
8. **The executor has 5.000 s on the fake clock (D31, D4).** A response that takes 4.999 s is `executed`. One that takes 5.000 s is accepted (`<=`, as the token lifetime); one that takes 5.001 s is `EXECUTOR_UNAVAILABLE`, `failed`. A late response is **not** recorded on the proposal and never causes a second apply: the executor's own record (`GET /executor/v1/proposals/{pid}`) shows what it did, the proposal stays `failed`.
9. **A partial apply is `failed` and visible (Q2, D33, D5).** When the executor applies fewer items than the snapshot, the proposal is `failed` with `executor_result.status = partial` and the real `applied_records` and `applied_count`; the confirm answers HTTP 502 `EXECUTOR_PARTIAL_APPLY` whose **body is the `Proposal`** (AD-15 amendment A16). An executor result with **more** applied records than the scope is `partial`/`failed`, never `executed`.
10. **The executor cannot be used to bypass the confirmation (AD-3, D7).** `POST /executor/v1/proposals` for a proposal that is not `dispatched` (a `dry_run` one, with its real token) is refused (409 `PROPOSAL_STATE_INVALID`) and applies nothing; with a wrong token it is 403 `GATE_TOKEN_INVALID`; for an unknown proposal 404 `PROPOSAL_NOT_FOUND`.
11. **A second apply is rejected, an identical retry is not an error (E35, D11).** `POST /executor/v1/proposals` twice with the identical request answers the stored `ExecutorResult` both times (one apply); a second request for the same `proposal_id` that differs (another action or selector) is 409 `EXECUTOR_DUPLICATE_APPLY` and applies nothing.
12. **`GET /executor/v1/proposals/{pid}` and `GET /destructive/proposals/{pid}` are served (D6).** The first answers the stored `ExecutorResult` (404 `PROPOSAL_NOT_FOUND` when the executor has none); the second the persisted `Proposal` (with `executor_result` once resolved) and 404 `PROPOSAL_NOT_FOUND` otherwise. Both are read-only.
13. **Re-dispatch is a new proposal through the full gate (PD-6, L2, D8).** `POST /destructive/proposals/{pid}/re-dispatches` for a `failed` parent whose snapshot was non-empty answers 200 with a **new** `Proposal` in `dry_run`, `supersedes_proposal_id = parent`, a fresh snapshot and a **new** token; the parent becomes `superseded`, unless it was already (partly) applied, in which case it stays `failed`. The parent's token confirms nothing of the child (403). Re-dispatch of a `dispatched`, `executed`, `confirmed`, `dry_run` or `superseded` parent is 409 `PROPOSAL_STATE_INVALID`; an unknown parent 404; a parent whose snapshot had nothing actionable 409 `DRY_RUN_EMPTY_SET`. The child still needs its own confirmation: re-dispatch never applies anything.
14. **Failures leave nothing half-written (AD-12).** A failure before the `confirmed -> dispatched` claim writes nothing (the 2.3 behaviour); a failure of the audit write while recording the result leaves the proposal in `dispatched`, never `executed` without its audit row, and the confirm answers the typed failure; the executor's apply is not repeated by any retry.
15. **The contract surface is complete (AD-13).** `SERVED_IN_THIS_STORY` equals the operations of `openapi.yaml` except `GET /runbooks/{id}` (story 3-3); no state-mutating route exists outside `/api/v1/destructive/*` and `/executor/v1/*`.
16. **Nothing that already works changes (IR-12).** The refusal, the dry-run, the chat reply and the confirmation up to the claim keep their behaviour; the tests of 2.3 that asserted `confirmed` after the confirm change **only** as D1 says, with a log entry and the user's approval; `migrations/001_*.sql` is not touched.
17. **Gate.** `ruff check .` is clean, `test/ci/schema_check.py` passes, `src/dto.py` equals `planning/detailed-design/schemas/dto.py` byte for byte, both `epics.md` and both `sprint-status.yaml` copies are identical, branch coverage of `src` stays at 90% or above, the full `pytest` passes, and the ATDD of this story passes three times in a row.

## Tasks / Subtasks

- [ ] **Task 1: ATDD red phase** (AC: 1-15) -> `test(story-2.4): ATDD red phase, recorded before production code`
  - [ ] 1.1 Write `tests/atdd/test_story_2_4.py` against the real app on a file database, one case per row of "ATDD cases". No `skip`, no `xfail`; ruff before the official run.
  - [ ] 1.2 Run `pytest tests/atdd/test_story_2_4.py -q --tb=short 2>&1 | tee docs/evidence/impl2/red-2-4.log`, check that every failure is missing behaviour, label the cases that already pass as regression guards, show the log and **wait for the user** before committing. No production code before that commit.
  - [ ] 1.3 Write the ATDD checklist `_bmad-output/test-artifacts/atdd-checklist-2-4-propose-only-handoff-simulated-executor-and-executor-failure-safety.md`.
- [ ] **Task 2: The executor port, the simulated executor and the effect rules** (AC: 2, 5, 6, 8, 9, 11) -> `feat(story-2.4): executor port and the simulated executor`
  - [ ] 2.1 `src/ports/outbound/executor_port.py` (OP-15: `dispatch(request) -> Result[ExecutorResult]`, `get(proposal_id)`), `src/domain/execution.py` (the effect of each verb, the classification of a result: `applied` | `partial` | `failed`, the 5 s rule), and the adapter `src/adapters/outbound/sim/executor_adapter.py` with its controls (`down`, `delay_seconds`, `apply_only`, `calls`). `RecordStore` gains a guarded `replace`/`remove` that **only** the executor adapter reaches (it is built from the same stores the read ports use).
  - [ ] 2.2 Unit and integration tests: every verb's effect on the stores; items applied by key and never re-enumerated; an item no longer actionable is skipped; idempotent retry and `EXECUTOR_DUPLICATE_APPLY`; the executor's own clock read; the frozen request validation; a static test that no provider port has a write method and that only the executor adapter mutates a store.
- [ ] **Task 3: Proposal store: dispatch, result, failure, supersede** (AC: 3, 7, 9, 13, 14) -> `feat(story-2.4): proposal store dispatch, result and supersede transitions`
  - [ ] 3.1 `ProposalStorePort`: `claim` becomes `dry_run -> confirmed -> dispatched` in one statement pair (contracts claim), `record_result(...)` (C6, conditional on `dispatched`, writing `executed` or `failed` and the executor columns), `mark_failed(proposal_id, ...)` (C6 without a result), `supersede(parent)` (C7, conditional on `failed`). All join the caller's transaction and answer whether this call changed the row.
  - [ ] 3.2 Integration tests on the real schema: each transition once and never twice, the state-machine trigger, the CHECKs (`confirmed_at` required, the all-or-nothing executor columns), 50 simultaneous dispatch claims with one winner, rollback with the caller.
- [ ] **Task 4: The dispatcher and the confirmation that dispatches** (AC: 1, 3, 4, 7, 8, 9, 14, 16) -> `feat(story-2.4): dispatcher, exactly-once dispatch and executor failure safety`
  - [ ] 4.1 `src/application/proposal_dispatcher.py`: after the claim, build the frozen request from the stored proposal, call the executor port once outside the writer, measure the 5 s on the clock, classify, and record the result and the `actor = executor` audit row in one writer transaction (ids minted before). `ConfirmationService` calls it and answers `executed`, 503 `EXECUTOR_UNAVAILABLE` or 502 `EXECUTOR_PARTIAL_APPLY`; an identical replay of a settled proposal still answers the persisted one.
  - [ ] 4.2 Adapt the tests of 2.3 that asserted `confirmed` after the confirm, exactly as D1 lists, in the same commit, with the log entry. Unit tests with a failing double for each collaborator and for the executor (down, slow, partial, more than the scope, duplicate).
- [ ] **Task 5: The four routes and the re-dispatch** (AC: 5, 10, 11, 12, 13, 15) -> `feat(story-2.4): get_proposal, executor routes and re-dispatch`
  - [ ] 5.1 `GET /api/v1/destructive/proposals/{pid}`; `POST /executor/v1/proposals` and `GET /executor/v1/proposals/{pid}` as a thin facade over the same executor adapter, validating the token and the `dispatched` state through a read of the proposal store (D7); `POST /api/v1/destructive/proposals/{pid}/re-dispatches` through `DryRunService` with `supersedes`, the parent's `superseded` transition in the same transaction. `UnavailableDispatch...` stand-ins. Add the four operations to `SERVED_IN_THIS_STORY` in the same commit; after it the set equals `openapi.yaml` minus `GET /runbooks/{id}`.
  - [ ] 5.2 Amend the text of `openapi.yaml` and `contracts.md` for D2, D5, D7 and D9 (no schema, no DTO unless the user approves a change).
- [ ] **Task 6: Gate, hammer, mutation check and evidence** (AC: 17) -> `test(story-2.4): green phase evidence`
  - [ ] 6.1 The tests of Task 1 pass **without having been edited**, three times in a row (`git diff <red commit> -- tests/atdd/test_story_2_4.py docs/evidence/impl2/red-2-4.log` is empty).
  - [ ] 6.2 Mutation check (see Testing standards), the full `pytest`, branch coverage, `ruff check .`, `schema_check`, the three `diff` checks. Evidence in `docs/evidence/impl2/flow-a-2-4-coverage.log` and `flow-a-2-4-atdd-x3.log`.

## Dev Notes

### What exists today (verified at baseline `3054c0a`)

- Story 2.3: `ConfirmationService.post_confirm` runs P1, P5, P2, P4, P3 and the claim `dry_run -> confirmed` with the audit rows in one transaction; it answers a `Proposal` in `confirmed` and **stops there**. `ProposalStorePort` has `add`, `get`, `claim`, `highest_counters`. `confirmed` rows have `confirmed_at`; the table already has the executor columns and `trg_proposals_state_machine` (`confirmed -> dispatched -> executed | failed`; `superseded` is terminal).
- Declared and not served (computed from `openapi.yaml` and `SERVED_IN_THIS_STORY`): `GET /destructive/proposals/{pid}`, `POST /destructive/proposals/{pid}/re-dispatches`, `POST /executor/v1/proposals`, `GET /executor/v1/proposals/{pid}` (this story) and `GET /runbooks/{id}` (3-3). The plan and the epics speak of "7 missing operations"; stories 2.1-2.3 already served the others.
- `dto.py` already has `ExecutorRequestDTO` (validates `dry_run_ref.proposal_id == proposal_id`), `ExecutorResultDTO`, `ProposalDTO`, `PostConfirmResponse`, `ConfirmationDTO`, `AuditRecordDTO.actor` and `proposal_id`; the catalog has `EXECUTOR_UNAVAILABLE` (as provider unavailable, 503), `EXECUTOR_PARTIAL_APPLY` 502, `EXECUTOR_DUPLICATE_APPLY` and the others. There is **no** executor port, adapter or dispatcher.
- `audit_records` has `actor`, `proposal_id`, a nullable `tool_call_id` and the unique partial index `ux_audit_executor_apply` (one `actor = executor` row per `proposal_id`). `AuditStorePort.append` takes `AuditEntry(tool_call=None, record=...)` for an executor row.
- The simulated estate is immutable: `RecordStore` keeps a tuple of records and answers deep copies; the read ports have no write method (a unit test pins it). So today **nothing can mutate the estate**.
- `SimClock.advance(seconds=...)` moves the shared simulated clock forward; the executor adapter can hold the same clock. `PortFault` patches a Sim adapter class before `create_app`.
- `DryRunService` is the model for a use case that writes a proposal and audit rows in one transaction; `ConfirmationService` for the claim, the revalidation and the rejection log.
- The 2.3 ATDD (`tests/atdd/test_story_2_3.py`) asserts `state == "confirmed"` after the confirm in 14 places and `estate(client) == before` in 2; `tests/unit/test_confirmation_service.py` and `tests/api/test_confirm_route.py` assert it in 9 more.

### Decisions (applied by the story author; override before the red phase is committed)

- **D1. The confirm now dispatches, so the 2.3 tests that assert `confirmed` must change (guide E.6, needs the user).** The contract's `confirm_and_dispatch` dispatches inside the confirm, the Annex says "dispatch exactly once to a simulated executor", and the plan put the dispatch tail in this story. Once the dispatcher is wired, a confirm answers `executed`, so the 14 assertions of the frozen 2.3 ATDD (`state == "confirmed"`, the row states, the Annex case, `estate == before`) and the 9 of its unit and API tests are wrong by design. **Recommended:** change exactly those assertions in the commit that wires the dispatcher (Task 4.2): `confirmed` becomes `executed` in the body and the row, the `estate == before` of the Annex case becomes "exactly the three CS-101 jobs are cancelled", and the replay, hammer and audit cases keep their meaning (the audit gains the executor row). One log entry (I2-xx) lists each changed assertion and why. **Alternative (not recommended):** a setting that turns the dispatcher off by default would keep 2.3 as is, but the real app would not run the Annex scenario unless configured, and it hides the real behaviour behind a flag.
- **D2. The executor is the only writer of simulated state, and what each verb does (needs the user).** `cancel_jobs` sets the job's `status` to `cancelled`; `delete_jobs` removes the job record from the jobs store; `cordon_node` sets `cordoned = true`; `drain_node` sets `cordoned = true` and `health = "draining"`. Items keep the `actionable_field = "status"` of 2.2; the field an effect writes is the verb's, and the contract text says so (Task 5.2). `RecordStore` gains a guarded `replace` and `remove` that only the simulated executor reaches; nothing else in the provider ring can write.
- **D3. Dispatch in one claim and one result transaction.** `claim` takes the proposal `dry_run -> confirmed -> dispatched` in one writer transaction (the contract: the two transitions commit together) with the audit rows of the confirm. The executor is called **after** that commit and outside the writer. The result (state `executed` or `failed`, the executor columns) and the `actor = executor` audit row are a second transaction (C6), conditional on `dispatched`.
- **D4. The 5 s timeout and the late response.** The sim executor advances the shared fake clock by its `delay_seconds` while it works, the dispatcher reads the clock before and after the call, and a call that took more than 5.000 s is `EXECUTOR_UNAVAILABLE`. A call that raises or reports down is the same. The proposal becomes `failed` (no executor columns) through a conditional `UPDATE ... WHERE state = 'dispatched'`. A late result is **not** written on the proposal (the contract allows either; the guard of the conditional update and the unique audit index make this the simpler, safer choice); the executor's own store keeps it and `GET /executor/v1/proposals/{pid}` shows it. There is no retry of any kind.
- **D5. Partial apply (needs the user).** `applied_count < len(affected_items)` makes `executor_status = partial`, the proposal `failed`, and the confirm answers 502 `EXECUTOR_PARTIAL_APPLY` whose body is the `Proposal` (contracts A16); the catalog template is not used for the body. `applied_count > len(affected_items)`, or applied keys outside the snapshot, is classified `partial`/`failed`, never `executed`. A fully applied result is `applied` and `executed`.
- **D6. The frozen request and the routes.** The dispatcher builds `ExecutorRequestDTO` from the stored row (`proposal_id`, `action`, the persisted selector, the stored token, `dry_run_ref`), so nothing is re-derived. The HTTP executor routes are a facade over the **same** sim adapter (the replacement point is the port): `POST /executor/v1/proposals` dispatches through it, `GET` reads its record. `GET /destructive/proposals/{pid}` reads the store.
- **D7. The executor refuses an unconfirmed proposal (needs the user).** The contract says the executor validates the token against the stored proposal. A client holding a `dry_run` proposal's token could otherwise call `POST /executor/v1/proposals` directly and apply it with no confirmation, which breaks AD-3. The sim executor therefore reads the proposal (read only) and accepts only a **`dispatched`** one with the matching token: another state is 409 `PROPOSAL_STATE_INVALID`, a wrong token 403, an unknown proposal 404. This is stricter than the contract text and consistent with its intent.
- **D8. Re-dispatch.** The parent must be `failed` (P1; P2 of the contract is the same rule). The child is a dry-run built by `DryRunService` from the request (`action`, `target_refs`, `query_text`) with `supersedes_proposal_id = parent` and a new token; the parent's persisted selector is never reused as the child's, so the set is fresh. The parent is set `superseded` by `UPDATE ... WHERE state = 'failed'` in the child's transaction unless it was already partly applied (`applied_count > 0`), in which case it stays `failed`. Zero rows updated is `PROPOSAL_STATE_INVALID`. A parent whose snapshot had nothing actionable is `DRY_RUN_EMPTY_SET`. The child needs its own confirmation.
- **D9. The executor audit row (needs the user for the label).** One row per proposal: `actor = executor`, `tool_call_id = null`, `proposal_id`, `session_id` and `operator_role` of the proposal's session, `result_summary = {tool_name: "executor.dispatch", status, applied_count}` and the timestamp of the executor's own clock read. The contract lists `executor.dispatch` as an audit event after `toolcall.confirm_and_dispatch`; the row **is** that event, so the audit order of a confirm is `toolcall.confirm_and_dispatch`, `toolcall.jobs_port.select`, `executor.dispatch`. A timed-out or down executor writes no executor row (it did not answer); the failure shows in the copilot row of the confirm.
- **D10. Replays.** A replay of an identical `(proposal_id, token)` of a proposal in `dispatched`, `executed`, `failed` or `superseded` answers 200 with the persisted `Proposal` (also for a `failed` one whose first answer was 503), never a second dispatch.
- **D11. Executor idempotency.** The adapter keeps its own record per `proposal_id`: an identical request returns the stored result, a differing one is `EXECUTOR_DUPLICATE_APPLY` 409 with nothing applied. The dispatcher's single claim makes the duplicate unreachable through the confirm; it is reachable through the executor route and through the unique audit index.
- **D12. Ids and clock.** The dispatcher reads the clock before the call (`dispatched_at`) and after it (`returned_at`); the executor reads its own clock for the result `timestamp`. Audit and proposal ids are minted before each transaction.
- **D13. The deferred window of 2.3.** The executor applies exactly the keys of the snapshot and skips an item that is no longer in the state its `actionable` flag promised (a running job that is no longer running); the skip lowers `applied_count` and the result is `partial`. It never re-enumerates scope.
- **D14. What stays out.** The delegation card labels, the `alertdialog` and `Esc` (UX-DR8) belong to the console stories 1-7 and 1-8 and are recorded as a coverage gap in the traceability matrix, as the test design says.

### ATDD cases (`tests/atdd/test_story_2_4.py`, real app, file DB)

Helpers as in 2.3 plus the sim executor controls (`container.port(ExecutorPort)`: `down`, `delay_seconds`, `apply_only`, `calls`) and the real `SimClock`. The 2.3 cases that now read `executed` are adapted under D1, not here.

| AC | Case |
|---|---|
| 1, 4 | the Annex to `executed`: the body, the row, the three jobs `cancelled` through `GET /state/jobs/...`, nothing else changed, the audit order and the executor row |
| 2 | the estate is identical after the dry-run and after a confirm that does not dispatch (stale), and after the executor-down failure |
| 3 | 2 and 50 simultaneous confirms: `executor.calls == 1`, one executor audit row, one transition, all 200 `executed`; a sequential replay adds no call |
| 5 | executor POST with a mismatched `dry_run_ref`, an extra field, a missing field: 400, nothing applied; the dispatcher's request holds exactly the frozen fields and the stored token |
| 6 | a job that is no longer running when the executor applies it is skipped: `partial`, 502 |
| 7 | executor down: 503, `failed`, snapshot and confirmation kept, no executor row, estate unchanged, +10 min on the clock changes nothing, calls stay 1 |
| 8 | delay 4.999 s `executed`; 5.000 s `executed`; 5.001 s 503 `failed`; the late result only in `GET /executor/v1/proposals/{pid}`, no second apply |
| 9 | `apply_only = 2` of 3: 502 with a `Proposal` body, `failed`, `partial`, the real records and count; an executor that reports more than the scope is never `executed` |
| 10 | executor POST for a `dry_run` proposal with its real token 409, wrong token 403, unknown 404, nothing applied |
| 11 | executor POST twice identically: the same stored result, one apply; a differing second: 409 `EXECUTOR_DUPLICATE_APPLY` |
| 12 | `GET /destructive/proposals/{pid}` for every state, `GET /executor/v1/proposals/{pid}` with and without a result, 404s |
| 13 | re-dispatch of a `failed` parent: a new `dry_run` proposal, `supersedes_proposal_id`, a new token, the parent `superseded`; the parent's token 403 on the child; the other parent states 409; unknown 404; empty-set parent 409; a partly applied parent stays `failed` |
| 14 | a failing audit write while recording the result leaves `dispatched`, never `executed` without its row |
| 15 | `SERVED_IN_THIS_STORY` equals the contract minus `GET /runbooks/{id}`; no mutating route outside the two prefixes |
| 16 | regression guards (pass today and must not be edited): the dry-run and chat reply shapes, `/copilot/query` refusal-only, a stale confirm still 409 and the proposal still `dry_run` |

### Guardrails (docs/impl2-rules.md)

- Use `src/` paths (the epics' `service/app/proposal_dispatcher.py`, `service/ports/out/executor_port.py` and `service/adapters/sim/executor.py` become `src/application/proposal_dispatcher.py`, `src/ports/outbound/executor_port.py` and `src/adapters/outbound/sim/executor_adapter.py`).
- Pure rules in `src/domain`; the domain, ports and application rings import no adapter or framework. Time only from the Clock port (the executor adapter takes its own read, E44); ids only from `idgen_port`.
- The Copilot performs **zero** writes to simulated state (AD-1, AD-3): the dispatcher only calls the executor port; the executor adapter alone mutates the stores; the only Module-12 writes are the proposal transitions and the audit rows through the one `SqliteWriter`.
- The selector is persisted and forwarded, never derived from text (AD-6, AD-15). The LLM never states a fact; nothing here reaches the prose writer.
- No `sleep`, `asyncio.sleep` or `waitForTimeout`; the executor's latency is **simulated on the fake clock**; concurrency is ordered with `threading.Barrier`.
- Never mock the unit under test; fakes only at outbound ports. Never weaken an assertion; a committed ATDD case changes only with a log entry and the user's decision (guide E.6, D1).
- `src/dto.py` and `planning/detailed-design/schemas/dto.py` change together or not at all (this story should not change them). Do not run `ruff format` over `src/`: list the files you touched.
- Keep both `epics.md` copies and both `sprint-status.yaml` copies identical.
- Do not edit `migrations/001_*.sql`. Do not touch `console/` or `tests/e2e/`.

### Files

- New: `src/ports/outbound/executor_port.py`, `src/domain/execution.py`, `src/adapters/outbound/sim/executor_adapter.py`, `src/application/proposal_dispatcher.py`, `src/ports/inbound/proposal_use_cases.py` (get and re-dispatch), the executor and re-dispatch services, `src/adapters/inbound/executor.py`, `tests/atdd/test_story_2_4.py`, unit, integration and API tests for each, the evidence logs, the ATDD checklist.
- Changed: `src/adapters/outbound/sim/record_store.py` (guarded write for the executor only), `src/adapters/outbound/sim/fixtures_adapter.py` (the executor receives the stores), `src/ports/outbound/proposal_store.py` and `src/adapters/outbound/db/proposal_store.py`, `src/application/confirmation_service.py`, `src/application/dry_run_service.py` (`supersedes`), `src/adapters/inbound/destructive.py`, `src/application/unavailable.py`, `src/bootstrap.py`, `src/ports/outbound/__init__.py`, `src/ports/inbound/__init__.py`, `tests/unit/test_ports_query_only.py`, `tests/api/test_contract_routes.py`, `tests/atdd/test_story_2_3.py` and the 2.3 unit and API tests (D1 only), `planning/detailed-design/schemas/openapi.yaml` and `contracts.md` (text), `docs/ai-decision-log.md`, `deferred-work.md` (close D-1 of 2-3).
- Do not touch: `migrations/001_*.sql`, `src/dto.py`, `planning/detailed-design/schemas/dto.py` (unless a contract change is approved), `fixtures/`, `console/`.

### Testing standards

- Red phase honesty: a failing case fails on the assertion that states the missing behaviour (`404 != 200` for the executor routes, `executed` expected, `502` expected), not on an import or fixture error. Run `ruff` on the file before the official run so the log matches the committed file; make every case able to fail (no case that passes on a 404).
- Mutation check after green, one at a time (restore in a `finally`, confirm `git status` of `src` and `tests` is clean): (1) remove the exactly-once guard of the dispatcher (the claim to `dispatched`); (2) call the executor before the claim commits; (3) dispatch from `confirmed` without the state guard; (4) forward a re-derived selector; (5) skip the token check of the executor route; (6) accept an executor POST for a `dry_run` proposal; (7) the 5 s with `<` instead of `<=`; (8) record a late result on the proposal; (9) retry the executor after a failure; (10) treat more applied records than the scope as `executed`; (11) treat `applied_count < n` as `executed`; (12) write the executor audit row with a `tool_call_id`; (13) reuse the copilot's clock read as the executor timestamp; (14) record the result outside the transaction of the audit row; (15) re-dispatch without the `failed` guard; (16) supersede a parent that was partly applied; (17) reuse the parent's token for the child; (18) the executor skips the "no longer actionable" check. Report any survivor and wait for a decision before editing a test.
- Concurrency: the hammer runs three times in a row; assert the **set** of outcomes, the executor call count, and the row and audit counts, never which request won.
- Pin exact values: the codes, the statuses, the applied records, the counts, the instants, the audit order, the frozen field set.

### Previous-story intelligence

- **2.3 / I2-25 .. I2-27:** `ConfirmationService` is the model (P1-P5, the claim with the audit rows in one transaction, a lost claim re-reads and lets P5 answer, a rejected attempt logs with `%r`). The frozen 2.3 tests assert the end state `confirmed`: see D1. The review deferred the window between the revalidation and the claim to this story (D13). The expiry is derived, not stored.
- **2.2 / I2-21 .. I2-24:** `DryRunService` takes refs and a session, builds the selector, enumerates through the audited ports and writes the proposal with its audit rows; the re-dispatch reuses it. Requests are bounded (50 refs) and deduplicated.
- **2.1 / I2-18 .. I2-22:** a committed ATDD case changes only with a log entry and the user's decision.
- **1.5 / I2-16:** audit rows commit in the same writer transaction as the write; mint ids before the transaction; a test that survives the mutant "feature off" is blind, so reach the real path.
- **4.2 / I2-17:** inject a fault by patching the Sim adapter class **before** `create_app`; here the executor adapter has its own switches (`down`, `delay_seconds`, `apply_only`) because it is the sim.

### Git intelligence

Recent commits: story 2.3 (`f98a941` red, `1c95b8c` .. `2c15e7f` green, `9a54b2d` evidence, `6d70e5d` review fix, `f279ed5` and `3054c0a` records), all pushed. Commit style: `test(story-2.4): ATDD red phase, recorded before production code`, then `feat(story-2.4): ...` per task, no `Co-Authored-By` line.

### Latest tech notes

No new library, so no version research. SQLite conditional `UPDATE ... WHERE state = 'dispatched'` is atomic under the single writer and its row count says who won; the unique partial index `ux_audit_executor_apply` is the database-level guard of "one executor row per proposal".

### Project Structure Notes

Pure rules in `src/domain`, use cases in `src/application`, ports in `src/ports`, adapters in `src/adapters/{inbound,outbound}`, ATDD in `tests/atdd`, evidence in `docs/evidence/impl2/`. The old `test/` tree is only a source of contract cases (`test/atdd/module12_contracts.test.py::test_confirm_and_dispatch_*`, `::test_executor_*`, `::test_post_re_dispatch_*`).

### References

- [Source: planning/epics.md#Story 2.4; docs/impl2-rules.md Annex-to-specification decisions; task statement PDF pages 30-31; docs/impl2-continuation/03-plan-implementacion.md T-09, T-10]
- [Source: planning/detailed-design/contracts.md `confirm_and_dispatch` P5, P6, Q1-Q3, Q-fail, L1-L3 and the claim; `post_confirm`; `get_proposal`; `post_re_dispatch`; `executor_post_proposal`; `executor_get_proposal`; OP-15; section 5 I9, I10, I18, I21; planning/detailed-design/schemas/openapi.yaml `/executor/v1/proposals`, `ExecutorRequest`, `ExecutorResult`, `Proposal`]
- [Source: test/test-design.md sections 6.1 (IR-02, IR-04), 6.3.4; test/atdd/module12_contracts.test.py `test_confirm_and_dispatch_*`, `test_executor_*`, `test_post_re_dispatch_*`; docs/ai-decision-log.md I2-01, I2-07, I2-22, I2-25, I2-26, I2-27]
- [Source: migrations/001_module12_copilot_schema.sql `proposals`, `audit_records`, `ux_audit_executor_apply`, `trg_proposals_state_machine`, contended writes C5-C8; src/dto.py `ExecutorRequestDTO`, `ExecutorResultDTO`; src/adapters/outbound/sim/record_store.py; src/adapters/outbound/sim/clock_adapter.py; src/application/confirmation_service.py; src/application/dry_run_service.py]
- [Source: _bmad-output/implementation-artifacts/2-3-procedural-confirmation-gate-and-snapshot-re-validation.md; deferred-work.md "story-2-3"]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5.5 (`claude-sonnet-5-5`), Claude Code, `bmad-create-story`.

### Debug Log References

- Baseline at `3054c0a`: `pytest` 1933 passed, branch coverage of `src` 97.66%. CI of the pushed history: the run of `3054c0a` is checked before the red phase.
- Audit probes (2026-11-08, real code): declared and not served are `GET /destructive/proposals/{pid}`, `POST /destructive/proposals/{pid}/re-dispatches`, `POST /executor/v1/proposals`, `GET /executor/v1/proposals/{pid}` and `GET /runbooks/{id}`; there is no executor port, adapter or dispatcher; `RecordStore` is immutable and no provider port has a write method; the 2.3 ATDD asserts `confirmed` in 14 places.

### Completion Notes List

- Story context created 2026-11-08, scoped against `src/`, `tests/`, `planning/` and `migrations/` at `3054c0a`. Ultimate context engine analysis completed - comprehensive developer guide created.

### File List

### Change Log

- 2026-11-08: Story created (`bmad-create-story`). Status -> ready-for-dev. D1, D2, D5, D7 and D9 wait for the user before the red phase.
