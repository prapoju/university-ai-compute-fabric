---
baseline_commit: d468b55
---

# Story 4.2: Safe failure on retrieval dependencies

Status: in-progress

<!-- Impl-2 foundations story, Flow B (test-along): code and its tests ship in the same commit.
     Audit on 2026-11-07 (see "What already holds"): every behaviour this story asks for already works
     through the real app. The deliverable is the proof (an API-level fault matrix through the real
     composition root) plus whatever defect that matrix turns up. Do not rewrite code that works. -->

## Story

As Nadia,
I want an explicit degradation when state, policy or the clock is unavailable,
so that I get "cannot answer" instead of a confidently invented reason.

## Acceptance Criteria

Source: `planning/epics.md` Story 4.2 (three ACs), refined below into checkable assertions. Requirements: FR-16, AD-12, NFR-7. Contracts: §5 I17, `assemble_evidence` Q-fail, `diagnose_schedule_window` Q-fail, L3. Error catalog: `PROVIDER_UNAVAILABLE` and `CLOCK_UNAVAILABLE` (both 503, retryable, literal `Provider unavailable — cannot answer.` = `cs.S_PUA`).

1. **One retrieval port down aborts the turn before prose (FR-16, AD-12).** For each of the 8 read points of the two diagnoses (S1: `users.get`, `catalog.get`, `policy.for_model`, `event_store.query`, and `policy.get` when the query names a `policy#...`; S2: `groups.get`, `jobs.select`, `windows.list`), a typed `Failure("PROVIDER_UNAVAILABLE")` makes `POST /api/v1/sessions/{sid}/queries` answer HTTP 503, `code = PROVIDER_UNAVAILABLE`, `message = cs.S_PUA`, `retryable = true`, and `explanation.observed_values = []` (a 5xx never exposes the adapter's reason). The body carries no `answers`, `claims`, `evidence`, `recommendation` or `diagnosis_class`. The LLM prose port is called 0 times (`SimProse.call_count` unchanged).
2. **An unexpected exception from a port degrades the same way (NFR-7, 0 hard crashes).** The same 8 read points raising `RuntimeError` (not a typed failure) answer the same 503 with the same literal. No 500, no stack trace in the body, and the next request on the same app and session works.
3. **The clock failing aborts the turn.** `SimClock.fail()` answers 503 `CLOCK_UNAVAILABLE` with `cs.S_PUA` for S1 and for S2, and changes nothing. A clock that raises answers 503 `PROVIDER_UNAVAILABLE` with the same literal. `POST /api/v1/sessions` behaves the same way with the clock down (already true, keep it).
4. **A failed turn persists nothing (AD-12, I17).** After every case in 1-3: `GET /sessions/{sid}` shows `turns == []` and an empty context; the tables `answers`, `tool_calls` and `audit_records` hold 0 rows. No partial evidence, window or runbook exists anywhere.
5. **Recovery is clean.** After the fault is lifted, the same query in the same session returns 200 with the same cited diagnosis a clean app gives (same `diagnosis_class`, same claim texts, same citation ids, apart from the clock read id). Claim ids start at `clm-…01` and audit ids at `aud-…01`: a failed turn burns neither. (The `answer_id` is minted before the pipeline and is burned by a failed turn. That is how it works today and this story does not assert or change it.)
6. **`POST /api/v1/copilot/query` degrades the same way (Annex 12.1 entry).** With the policy provider down it answers 503 `PROVIDER_UNAVAILABLE`, and with the clock down 503 `CLOCK_UNAVAILABLE`. With the clock down, 0 sessions are created. After recovery it answers 200.
7. **The session-less read routes never 500.** With a provider port raising, `GET /api/v1/state/users/alex`, `GET /api/v1/state/users`, `GET /api/v1/citations/user%23alex` and `GET /api/v1/citations/policy%23catalog.4.2` answer 503 `PROVIDER_UNAVAILABLE` with `cs.S_PUA`. (`GET /api/v1/answers/{aid}/evidence` reads the evidence already stored with the answer, not a provider, so a broken provider does not affect it, and it answers 200. Its failure case is a broken store, covered by `test_evidence_api.py::test_a_broken_database_answers_503_on_both_routes_and_never_crashes`.)
8. **The console banner is not part of this story.** The third AC of `epics.md` (provider-unavailable banner with a safe retry path, UX-DR7) belongs to story 1-7. Here the backend half is the proof: `retryable = true` and the literal. The walkthrough records that split.
9. **Gate.** Branch coverage of `src` stays at 90% or above, `ruff check .` is clean, `test/ci/schema_check.py` passes, the full `pytest` passes, and the coverage log goes in `docs/evidence/impl2/flow-b-4-2-coverage.log`. `S1`, `S2` and the `ghost_user_99` edge case answer exactly as before.

## Tasks / Subtasks

Flow B: each task's code and its tests are one commit. Do not commit code without its tests. A production change is allowed only when a matrix case is red against it (record that in the Debug Log); otherwise the story changes only `tests/`.

- [x] **Task 1: Fault-injection helper and the API fault matrix for the two turns** (AC: 1, 2, 4, 5) -> `test(story-4.2): API fault matrix for the retrieval ports`
  - [x] 1.1 `tests/support/faults.py` (new). A small `PortFault` switch with `down()` and `recover()` and a `mode` of `"failure"` (returns `Failure("PROVIDER_UNAVAILABLE", observed=("simulated outage",))`) or `"raises"` (raises `RuntimeError`). `install(monkeypatch, cls, method, fault)` replaces `cls.method` on the **Sim adapter class** with a wrapper that consults the switch and otherwise calls the original. See "Fault injection technique" for why the patch must happen before `create_app`. Export nothing from `tests/support/__init__.py` (import it as `from support.faults import ...`, like `support.clock` in `tests/unit/test_fake_clock.py`).
  - [x] 1.2 `tests/api/test_safe_failure.py` (new, marker `api`). Build the app with `create_app(Settings.from_env({"M12_DB_PATH": str(tmp_path / "m12.db")}))` and `TestClient(app, raise_server_exceptions=False)`. One parametrised test over the 8 read points x `("failure", "raises")` (16 cases) asserting AC 1, 2 and 4, then lifting the fault and asserting AC 5. Query per row: S1 for the four S1 ports, `Why was student Alex denied access to model deepseek-coder under policy#catalog.4.2?` for `policy.get`, S2 for the three S2 ports. The exact queries come from `docs/impl2-rules.md` and the existing API tests.
  - [x] 1.3 The "nothing persisted" check reads `app.state.container.writer` (`with writer.read() as db`), as `tests/api/test_audit_api.py::retained` does. The "context unchanged" check uses `GET /sessions/{sid}`. The "LLM not called" check reads `container.port(LlmProsePort).call_count`.
  - [x] 1.4 The recovery assertions compare the 200 body with a baseline taken from a clean second app (same fixtures), not with hard-coded text: same `diagnosis_class`, `[c.text for c in claims]`, citation ids except `clock#...`, plus `claim_id == clm-%016x` for 1..n and the audit page ids starting at `aud-…01`.
- [x] **Task 2: Clock failures, `/copilot/query` and the session-less routes** (AC: 3, 4, 6, 7) -> `test(story-4.2): clock, copilot/query and read-route failures`
  - [x] 2.1 Clock, S1 and S2, `fail()` and a raising `SimClock.now` (patched before `create_app`): 503 with `CLOCK_UNAVAILABLE` / `PROVIDER_UNAVAILABLE`, `cs.S_PUA`, 0 rows, `turns == []`. `POST /sessions` with the clock down stays 503. The existing `test_a_failed_clock_is_a_503_that_never_fabricates_a_window` (S2, `tests/api/test_window_diagnosis_api.py`) stays as it is.
  - [x] 2.2 `POST /copilot/query` (body field is `query`, not `query_text`): policy down gives 503 `PROVIDER_UNAVAILABLE`; clock down gives 503 `CLOCK_UNAVAILABLE` and `sessions` has 0 rows; after `recover()` it gives 200. With the policy down it leaves one empty session (observed 2026-11-07, see D5). Assert 0 `answers`, 0 `tool_calls`, 0 `audit_records` and do not assert the session count there.
  - [x] 2.3 Read routes with a raising port (AC 7): `users.get` raising on `/state/users/alex`; `users.browse` raising on `/state/users`; the citation route reads the provider named by the citation type, so raise `users.get` for `/citations/user%23alex` and `policy.get` for `/citations/policy%23catalog.4.2`. Use a switch (see the technique below) so the app can first serve a healthy turn and then go down. Do not add a provider-outage case for the evidence route (it reads stored rows); add one assertion that it still answers 200 while a provider is down.
- [ ] **Task 3: Close what the matrix finds, then the gate** (AC: 9) -> `fix(story-4.2): ...` only if a case is red, then `test(story-4.2): coverage evidence`
  - [ ] 3.1 If any matrix case is red, fix the production code (smallest change) in the same commit as the test that found it, and record the case and the fix in the Debug Log.
  - [ ] 3.2 Mutation check on the guards (see Testing standards): apply each mutant, run `tests/api/test_safe_failure.py`, show which case fails, restore the code and confirm `git diff` is clean.
  - [ ] 3.3 Gate: full `pytest`, `make cov` equivalent (`.venv/Scripts/python.exe -m pytest tests -q --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=90`), `ruff check .`, `schema_check`, `diff` of both `sprint-status.yaml` copies. Save the coverage run to `docs/evidence/impl2/flow-b-4-2-coverage.log`. Never edit an existing evidence file.

## Dev Notes

### What already holds (verified through the real app, 2026-11-07, baseline `d468b55`)

- All 14 single-port scenarios (the 7 S1/S2 read points x typed `Failure` or a raised `RuntimeError`) answer 503 `PROVIDER_UNAVAILABLE`, `message == cs.S_PUA`, `retryable = true`, `observed_values = []`. Each leaves `turns == []` and 0 rows in `answers`, `tool_calls` and `audit_records`, and the same query succeeds (200) once the fault is lifted.
- `POST /sessions` with the clock down is 503. `POST /copilot/query` with the clock down is 503 `CLOCK_UNAVAILABLE` with 0 sessions; with the policy down it is 503 and leaves 1 empty session.
- `GET /state/users/alex`, `GET /state/users` and `GET /citations/{user#alex | policy#catalog.4.2}` are 503 `PROVIDER_UNAVAILABLE` when the port they read raises; `GET /state/users/alex` is also 503 with `cs.S_PUA` when the port returns a `Failure`. `GET /answers/{aid}/evidence` stays 200 because it reads stored rows.
- The policy-named S1 query (`... under policy#catalog.4.2?`) is a healthy 200 `access_denial_not_in_allowlist`, and with `policy.get` down (typed or raised) it is a 503 `PROVIDER_UNAVAILABLE` with `cs.S_PUA`.
- After a failed turn and a recovery, claim ids start at `clm-…01` and audit ids at `aud-…01`; the `answer_id` is `ans-…02` (burned by the failed turn).
- The mechanism: `AnswerPipeline.respond` returns the handler's `Failure`; `SessionService.submit_query` returns it before any write (a failed turn is not audited, story 1.5); `failure_response` renders it through the catalog and hides `observed` for 5xx; the global `Exception` handler in `install_error_handlers` turns anything raised into the same 503.
- Unit coverage that already exists and stays: `test_access_denial_handler.py` (`test_a_failed_estate_aborts_the_turn_before_any_prose`, `test_an_event_store_failure_discards_everything_no_partial_evidence`, `test_a_failed_turn_does_not_burn_claim_ids`), `test_window_diagnosis_handler.py` (jobs and windows outages), `test_entity_resolver.py` (users, catalog and policy outages are never "not found"), `test_anti_fabrication.py` (policy store failure), `test_evidence_assembler.py`, `test_session_service.py` (clock failure, no partial state, audit atomicity), `test_access_denial_api.py` and `test_window_diagnosis_api.py` (whole-estate break, clock, LLM), `test_sessions.py`, `test_error_catalog.py`.

### What is missing (the gap this story closes)

- No test fails **one port at a time through the real composition root**. The API tests break the whole estate (a deleted fixture file) or the clock or the LLM. The per-port tests are unit tests with doubles, so they never run through the `audited()` wrappers, the recorder and the audit transaction of `SessionService`.
- No test makes a port **raise** at API level (AC 2, "0 hard crashes").
- No test asserts that a failed turn leaves **0 `tool_calls` and 0 `audit_records`** together with the 503 at API level for each port, nor that the **LLM is not called**.
- `POST /copilot/query` under failure and the session-less read routes under a raising port are untested.
- `test/test-design.md` section 6.3 has no section for 4-2, so the cases above come from the epics ACs and contracts I17, not from a shift-left table.

### Fault injection technique (read this before writing the helper)

- `bootstrap.build_container` wraps every provider port once with `audited(port_type, raw_port, ...)`, and `_delegate` does `target = getattr(adapter, method)` **at wrap time**. Patching a method **after** `create_app` has no effect (confirmed: the first attempt returned 200). Patch the Sim adapter **class** (`fixtures_adapter.SimPolicy.for_model`, ...) **before** `create_app`, with `monkeypatch.setattr`, and make the replacement consult a switch so one app can go down and recover.
- This is a double at an **outbound port**, which `docs/impl2-rules.md` allows ("fakes go only at outbound ports"). The unit under test (pipeline, handlers, service, routes, wrappers, audit) is real. Never patch `SessionService`, the pipeline, the error handlers or the wrappers.
- The clock has its own switch: `container.port(ClockPort).fail()` / `.recover()` (precedent: `test_window_diagnosis_api.py`). To make it **raise**, patch `SimClock.now` on the class before `create_app`.
- Use `TestClient(app, raise_server_exceptions=False)` (the other API tests do). Without it the test client re-raises the server-side exception instead of returning the 503 the real server sends.
- Ports to patch, with their SUT and the query that reaches them: `SimUsers.get`, `SimCatalog.get`, `SimPolicy.for_model`, `SimEventStore.query` (S1); `SimPolicy.get` (a `policy#...` named in the query, reached through `EntityResolver.missing_policies`); `SimGroups.get`, `SimJobs.select`, `SimWindows.list` (S2).

### Decisions (proposed by the story author, to confirm with Juan at review)

- **D1. This is a proof story.** Behaviour already works; the deliverable is the API-level fault matrix. Production code changes only if a case is red.
- **D2. Fault injection by class patch before `create_app`, behind a switch** (helper in `tests/support/faults.py`). No new production hook is added to the Sim adapters.
- **D3. "Times out" means the port returns a typed failure.** There is no provider timer in the sim adapters. The wall-time fan-out budget (`asyncio.timeout`) is the story 1-6 concern; a provider that times out is, for this story, an adapter returning `Failure("PROVIDER_UNAVAILABLE")`, which the matrix covers.
- **D4. The console banner (UX-DR7) belongs to 1-7**, as AC 8 says. Record it in the walkthrough.
- **D5. `POST /copilot/query` opens its session before the turn.** A failed turn therefore leaves one empty `active` session. It holds no evidence, answer or audit row, so it breaks no AC; it is not changed here. It matters for the 1-6 k6 run only as session churn.
- **D6. The `answer_id` burned by a failed turn is not asserted** (AC 5). Claim ids and audit ids are, because those guarantees exist today and a regression would be real.

### Guardrails (docs/impl2-rules.md)

- Use `src/` paths. The epics' `service/app/failures.py` does not exist; the failure rendering lives in `src/adapters/inbound/errors.py` (`failure_response`, `install_error_handlers`) and the typed results in `src/domain/result.py` and `src/domain/error_catalog.py`.
- `src/domain`, `src/ports` and `src/application` import no adapter, framework, `sqlite3`, `time`, `os`, `random` or `uuid`. Time comes only from the Clock port; ids only from `idgen_port`.
- Never use `sleep`, `asyncio.sleep` or `waitForTimeout`. A "timeout" is a returned or raised failure, never a wait.
- Never mock the unit under test; assert what did **not** happen (no prose call, no row, no claim, no evidence), and assert the exact literal through `cs.S_PUA`.
- Never weaken an assertion to get green. If a case is red, fix the code or stop and ask.
- `src/dto.py` stays byte-identical to `planning/detailed-design/schemas/dto.py`. No contract, `openapi.yaml` or `epics.md` change is expected; if one becomes necessary, stop and ask first.
- Keep both `sprint-status.yaml` copies (`_bmad-output/implementation-artifacts/` and `implementation-artifacts/`) identical.
- Story 1.7 owns the console. Do not touch `console/` or `tests/e2e/`.

### Files

| File | Change |
|---|---|
| `tests/support/faults.py` | new (`PortFault`, `install`) |
| `tests/api/test_safe_failure.py` | new (matrix, clock, `/copilot/query`, read routes) |
| `src/...` | only if a matrix case is red (record it in the Debug Log) |
| `docs/evidence/impl2/flow-b-4-2-coverage.log` | new (coverage run) |
| `_bmad-output/implementation-artifacts/sprint-status.yaml`, `implementation-artifacts/sprint-status.yaml` | status changes, identical |
| `docs/ai-decision-log.md` | next free `I2-NN` entry at closing (D1-D6 outcome and any correction) |

### Testing standards

- Markers: `api`, as in the existing API files. `--import-mode=importlib` means no `__init__.py` is needed. `tests/conftest.py` makes `support` importable.
- Run on a **file** DB under `tmp_path` so the persisted-row checks read the real SQLite schema.
- One parametrised test is not enough to prove a guard exists. After the matrix is green, run these mutants against `src/`, one at a time, and each must turn at least one matrix case red (restore with `git checkout -- <file>` and confirm `git diff` is clean):
  1. `EvidenceAssembler.gather`: an event-store failure is read as "no events" (`Ok([])`), so a partial evidence set is rendered.
  2. `WindowDiagnosisHandler`: a `jobs.select` failure is read as "no jobs".
  3. `WindowDiagnosisHandler`: a `windows.list` failure is read as "no windows" (the "no window on record" answer).
  4. `install_error_handlers`: the global `Exception` handler answers 500 instead of the 503 literal.
  5. `SessionService.submit_query`: a pipeline `Failure` is written as an answer instead of returned.
  Report any mutant that survives; do not edit a test without the user's decision.
- Pin exact values (code, literal, `retryable`, row counts, id strings). A test that only asserts `status_code != 200` passes for the wrong reason.

### Previous-story intelligence

- **1.5 / I2-16:** the audit rows of a turn commit in the same writer transaction as the `Answer`; a failed turn writes none. This story proves that at API level for every port. In I2-16 three real mutant gaps were closed in `test_audit_api.py` and `test_session_service.py` (do not duplicate them).
- **1.5 review:** a test that passes under the mutant "feature off" is blind. The first run of the matrix must be checked against at least one mutant above.
- **1.4 / I2-14:** routes whose store can fail must declare 503 in `openapi.yaml`. `/state`, `/audit` and `/answers/{aid}/evidence` already do; if a read route in AC 7 answers 503 without declaring it, that is a contract finding to report, not to fix silently.
- **4.1 / I2-11:** `bend`-style helpers that replace only an outbound dependency are the accepted pattern; replacing the diagnoser that feeds the guard is not.
- **Deferred (from reviews):** a typed reference of another type is named "not found" even when it exists (4-1), and clock read ids restart per process (1-4). Neither belongs here.

### Git intelligence

Recent commits: the story 1.5 review (`review(story-1.5): ...`, `docs(impl-2): ...`, `docs(evidence): ...`), then `feat(story-1.5)`, `feat(story-1.4)`, `test(flow-c)`. Commit style: one Conventional Commit per Flow B task, `test(story-4.2): ...` for tests, `fix(story-4.2): ...` for a production fix, no `Co-Authored-By` line (standing instruction). No new dependency is needed: the code uses `pytest`, `fastapi.testclient` and the stdlib.

### Latest tech notes

No new library, so no version research. Two behaviours the tests rely on: Starlette's `TestClient` re-raises server exceptions unless `raise_server_exceptions=False`, and `monkeypatch.setattr(cls, name, fn)` restores the class attribute at test teardown, so the patch cannot leak into other tests as long as it is installed through the `monkeypatch` fixture.

### Project Structure Notes

New tests go in `tests/api/` and the helper in `tests/support/`, next to the existing files of the same kind. The old `test/` tree (red historical stubs) is untouched. Evidence goes in `docs/evidence/impl2/`.

### References

- [Source: planning/epics.md#Story 4.2]
- [Source: planning/ARCHITECTURE.md AD-12 (safe failure on any dependency), NFR-7]
- [Source: planning/detailed-design/contracts.md section 5 I17, `assemble_evidence` Q-fail, `diagnose_schedule_window` Q-fail, L3]
- [Source: src/adapters/inbound/errors.py `failure_response`, `install_error_handlers`; src/application/session_service.py `submit_query`; src/application/tool_audit.py `_delegate`; src/bootstrap.py `build_container`]
- [Source: _bmad-output/implementation-artifacts/1-5-tool-call-audit-log-and-state-inspection-viewer.md Review Findings; docs/ai-decision-log.md I2-16]
- [Source: docs/impl2-rules.md Code rules, Test rules]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5.5 (`claude-sonnet-5-5`), Claude Code, `bmad-create-story`.

### Debug Log References

- Baseline at `d468b55`: `pytest` 1393 passed, branch coverage of `src` 97.07%.
- Task 1: the first run of the matrix failed 16/16 on my own setup error (`tmp_path / "clean"` did not exist, so SQLite could not open the file); fixed in the test with `mkdir`. No production code was involved. After that, 16 passed at once, as the story predicted (the behaviour already holds), so the matrix was checked against mutants before committing: events failure read as no events, policy failure read as no clauses, jobs failure read as no jobs, windows failure read as no windows, an ignored policy-existence check, and the global handler answering 500. Each one turns exactly the case of its read point red (the 500 mutant turns the 8 `raises` cases red); `git status` of `src` was clean after each restore.
- Task 2: the 9 new cases passed at once (the behaviour already holds), so they were checked against mutants before committing: `CLOCK_UNAVAILABLE` mapped to a 500 (4 cases red), `create_session` ignoring a clock failure (2 red), the turn ignoring a clock failure (2 red), `/copilot/query` ignoring a session-creation failure (1 red), the global handler answering 500 (12 red in total, 8 from Task 1 and 4 new read-route and clock cases) and a policy failure read as no clauses (2 red: the matrix row and the `/copilot/query` case). `git status` of `src` was clean after each restore. `ruff format` reformatted my test file once.
- Audit probes (2026-11-07, real app, file DB): 14 single-port cases and 5 clock and `/copilot/query` and `/state` cases, results in "What already holds". The first fault probe patched after `create_app` and had no effect, which is why the helper must patch before the app is built.

### Completion Notes List

- **Task 1:** `tests/support/faults.py` (`PortFault`, `install`, `SimulatedOutage`) and `tests/api/test_safe_failure.py`: 8 read points x `failure`/`raises` = 16 cases through the real app on a file DB. Each case asserts AC 1, 2, 4 and 5 (the 503 with `cs.S_PUA`, `retryable`, no leaked reason, nothing fabricated in the body, 0 LLM calls, `/healthz` still 200, 0 rows in `answers`/`tool_calls`/`audit_records`, empty context, then a clean recovery equal to a healthy baseline with claim and audit ids starting at 1). No production change was needed.
- Story context created 2026-11-07, scoped against `src/` and `tests/` at `d468b55`. Ultimate context engine analysis completed - comprehensive developer guide created.
- **Task 2:** in `tests/api/test_safe_failure.py`, the shared assertions (`assert_safe_failure`, `assert_nothing_persisted`, `healthy_baseline`, `assert_clean_recovery`) now serve every case, with these additions: the clock typed (`SimClock.fail()`, `CLOCK_UNAVAILABLE`) or raising (`PROVIDER_UNAVAILABLE`) for S1 and S2 with a clean recovery (4 cases); `POST /sessions` with the clock down (2); `POST /copilot/query` with the policy down (503, no answer, tool-call or audit row, recovers) and with the clock down (503 `CLOCK_UNAVAILABLE`, 0 sessions, recovers) (2); the read routes `/state/users/alex`, `/state/users`, `/citations/user%23alex` and `/citations/policy%23catalog.4.2` answering the safe failure while a provider raises, with `/answers/{aid}/evidence` still 200 (1). The Task 1 matrix keeps its 16 cases. No production change was needed.

### File List

Task 1:
- `tests/support/faults.py` (new)
- `tests/api/test_safe_failure.py` (new)
- `_bmad-output/implementation-artifacts/sprint-status.yaml`, `implementation-artifacts/sprint-status.yaml` (modified, `4-2` -> `in-progress`)
- `_bmad-output/implementation-artifacts/4-2-safe-failure-on-retrieval-dependencies.md` (modified)

Task 2:
- `tests/api/test_safe_failure.py` (modified)
- `_bmad-output/implementation-artifacts/4-2-safe-failure-on-retrieval-dependencies.md` (modified)
### Change Log

- 2026-11-07: Story created (`bmad-create-story`). Status -> ready-for-dev.
- 2026-11-07: Task 1 done (fault helper and the 16-case API fault matrix). Status -> in-progress.
- 2026-11-07: Task 2 done (clock, `/copilot/query` and read-route failures; 9 more cases).
