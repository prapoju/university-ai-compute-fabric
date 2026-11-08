---
baseline_commit: 4e8f902
---

# Story 2.3: Procedural confirmation gate and snapshot re-validation

Status: review

<!-- Impl-2 Flow A (ATDD-first), Annex 12.4, third of four stories (2-1 .. 2-4). The red phase is
     recorded BEFORE any production code. This story builds the confirmation gate: a distinct
     `POST /destructive/proposals` carrying only {proposal_id, gate_token}, the 60 s token lifetime on
     the Clock port, the single use of the token, the re-validation of the stored selector and the
     claim `dry_run -> confirmed`. It stops at `confirmed`: there is no executor yet, so nothing is
     dispatched (story 2-4 adds `confirmed -> dispatched -> executed | failed`, plan D-P1).
     Decisions D1-D13 were applied by the story author following the contract, the task statement and
     the rubric. D1 and D6 touch the contract text: the user confirms them before the red phase is
     committed. D2 (how the expiry is derived) was already decided by the user on 2026-11-08. -->

## Story

As Nadia,
I want an explicit, distinct confirmation that re-checks the state before anything leaves the Copilot,
so that the safety boundary is honest and stale scope can't slip through.

## Acceptance Criteria

Source: `planning/epics.md` Story 2.3, `test/test-design.md` section 6.3.3, `docs/impl2-rules.md`, task statement Annex 12.4 (pages 30-31 of the PDF). Requirements: FR-09, NFR-8, AD-4, AD-5, AD-6, D9, C-8, Annex invariant AD-30. Contracts: `confirm_and_dispatch` P1-P5, Q1-Q4, Q-fail, L1, L3 (the executor part, P6 and L2, is story 2-4); `post_confirm`; section 5 I9, I12, I13; catalog `PROPOSAL_NOT_FOUND`, `GATE_TOKEN_INVALID`, `CONFIRMATION_STALE`, `DRY_RUN_EMPTY_SET`, `CONFIRMATION_CONFLICT`, `PROPOSAL_STATE_INVALID`, `VALIDATION_MALFORMED_BODY`, `PROVIDER_UNAVAILABLE`, `CLOCK_UNAVAILABLE`.

1. **Confirmation is a distinct request and ends in `confirmed` (D1, AD-5).** `POST /api/v1/destructive/proposals` with exactly `{proposal_id, gate_token}` of a fresh `dry_run` proposal answers HTTP 200 with the contract `Proposal` (valid `ProposalDTO`): `state = confirmed`, the same `proposal_id`, `gate_token`, `action` and `dry_run_snapshot` as the dry-run, `confirmation.confirmed_at` equal to the fake-clock instant of the request and `confirmation.caption` equal, byte for byte, to `S_CAP` (`This confirms a proposal for delegation. It does not grant or assert authorization.`), `executor_result = null`. The cluster state is unchanged and the `proposals` row is `confirmed` with `confirmed_at` set.
2. **No identity, no role, no session context (AD-5, Q4).** A body with any extra field (`role`, `user`, `session_id`, ...) is `VALIDATION_MALFORMED_BODY` (400) and changes nothing. The confirmation reads the session store only for the `operator_role` the audit row needs, never for its context: a session that was **reset** between the dry-run and the confirm gives the same outcome as one that was not. Nothing the request says about who confirms is stored.
3. **The token lives 60 s on the Clock port, derived from the snapshot (D2, P2).** The expiry is not stored: it is `snapshot_timestamp + gate_token_ttl_seconds`, the setting in force. A confirm at `t0 + 59.999 s` and at `t0 + 60.000 s` is accepted (`<=`); at `t0 + 60.001 s` it is `CONFIRMATION_STALE` (409) with the proposal still `dry_run` and no confirmation. With `M12_GATE_TOKEN_TTL_SECONDS=5` the boundary is `t0 + 5 s`. The clock is the simulated one, advanced with `SimClock.advance`; no wall-clock read, no sleep.
4. **The token is single use and a replay is harmless (P5, D4).** An identical `(proposal_id, gate_token)` after a successful confirm answers 200 with the **persisted** proposal (same state, same `confirmed_at`, same caption), makes no second `dry_run -> confirmed` transition and writes no audit row. It does so also after the token's lifetime has passed (`t0 + 120 s`), because P5 is evaluated before P2.
5. **A wrong token, a conflicting confirm and a bad request are told apart (P1, P2, P5, D4).** Unknown `proposal_id` is `PROPOSAL_NOT_FOUND` (404). A different token on a `dry_run` proposal (also another proposal's token) is `GATE_TOKEN_INVALID` (403). A different token on a proposal already `confirmed` is `CONFIRMATION_CONFLICT` (409). A token that is not `gt-` + 32 hex is `VALIDATION_MALFORMED_BODY` (400). A proposal in `refused` is `PROPOSAL_STATE_INVALID`. None of them changes the state or writes an audit row.
6. **An empty or non-actionable set is refused before any provider read (P4, D5).** A proposal whose `affected_items` is empty, or in which no item is `actionable`, answers `DRY_RUN_EMPTY_SET` (409) and the provider port is called 0 times.
7. **The stored selector is re-executed and the set must still match (P3, AD-6, D6).** The persisted selector is re-run through the real `jobs_port` or `nodes_port` and compared on `(key, actionable, actionable value)` with `dry_run_snapshot.affected_items`. Any difference (an item that is no longer there, a new one that matches, one whose status changed) answers `CONFIRMATION_STALE` (409): the message is `Snapshot stale: <delta>.`, the delta names every added, removed and changed item, the body also says that confirmation is disabled, the proposal stays `dry_run`, nothing is confirmed. An unchanged set is confirmed.
8. **A provider failure during re-validation is a safe failure (AD-12, L3).** With the provider failing, the confirm answers 503 `PROVIDER_UNAVAILABLE` with the proposal still `dry_run`, no `confirmed_at`, and no audit row; after recovery the same confirm succeeds.
9. **Concurrent confirms make one transition (IR-02, D7).** Two identical confirms released by `Barrier(2)`, and 50 released by `Barrier(50)`, give exactly one `dry_run -> confirmed` transition, one set of audit rows and one `confirmed_at`; every response is 200 with a `Proposal` in `confirmed`, 0 HTTP 500, 0 `database is locked`. An identical confirm raced with a confirm that carries another token ends with the allowed set {200, 403, 409} and never two transitions. A confirm raced with a state change, ordered both ways with gates, is `confirmed` when it goes first and `CONFIRMATION_STALE` when the change goes first.
10. **The claim and its audit commit together (AD-10).** The `dry_run -> confirmed` update and the audit rows are one writer transaction: when the audit write fails the proposal stays `dry_run` and the answer is the typed failure.
11. **The confirmation is audited once (D7, D12).** After a successful confirm the session's audit lists, after the dry-run rows, `toolcall.confirm_and_dispatch` and then `toolcall.jobs_port.select` (the re-validation read), every row with the session's `operator_role` and one clock instant per request. Replays and rejections add no row. The audit never holds the token.
12. **The Annex scenario reaches `confirmed` (Annex 12.4).** `POST /copilot/chat` with `Terminate all active jobs for CS-101` answers refusal, summary and token; a separate `POST /destructive/proposals` with that token answers `confirmed`; the cluster state is identical before and after the whole scenario (zero writes to simulated state). The dispatch is story 2-4.
13. **Nothing that already works changes (IR-12).** The refusal, the dry-run, the chat reply and `/copilot/query` of stories 2.1 and 2.2 are unchanged; `migrations/001_*.sql` and the state-machine trigger are not touched; the dry-run response still carries `gate_token`.
14. **Gate.** `ruff check .` is clean, `test/ci/schema_check.py` passes, `src/dto.py` equals `planning/detailed-design/schemas/dto.py` byte for byte, both `epics.md` and both `sprint-status.yaml` copies are identical, branch coverage of `src` stays at 90% or above, the full `pytest` passes, and the ATDD of this story passes three times in a row (zero flaky).

## Tasks / Subtasks

- [ ] **Task 1: ATDD red phase** (AC: 1-12) -> `test(story-2.3): ATDD red phase, recorded before production code`
  - [ ] 1.1 Write `tests/atdd/test_story_2_3.py` against the real app on a file database, one case per row of "ATDD cases" below. No `skip`, no `xfail`; ruff before the official run.
  - [ ] 1.2 Run `pytest tests/atdd/test_story_2_3.py -q --tb=short 2>&1 | tee docs/evidence/impl2/red-2-3.log`, check that every failure is missing behaviour (not an import, fixture or syntax error), label the cases that already pass as regression guards, show the log and **wait for the user** before committing. No production code before that commit.
  - [ ] 1.3 Write the ATDD checklist `_bmad-output/test-artifacts/atdd-checklist-2-3-procedural-confirmation-gate-and-snapshot-re-validation.md`.
- [x] **Task 2: Proposal store reads and the claim** (AC: 1, 4, 9, 10) -> `feat(story-2.3): proposal store get and the conditional claim`
  - [x] 2.1 `ProposalStorePort.get(proposal_id)` (a miss is `Ok(None)`) rebuilding the `ProposalDTO` (confirmation from `confirmed_at` + `S_CAP`, executor result from its columns) and `claim(proposal_id, gate_token, confirmed_at)` as the single statement `UPDATE ... SET state='confirmed', confirmed_at, updated_at WHERE proposal_id = ? AND state = 'dry_run' AND gate_token = ?`, answering whether a row changed. `SqliteProposalStore` joins the caller's transaction. Update the owned-port method set in `tests/unit/test_ports_query_only.py`.
  - [x] 2.2 Integration tests on the real schema: round trip of a `dry_run` and a `confirmed` row, the claim wins once and loses afterwards, the claim with another token or on another state changes nothing, a closed connection is a typed failure, the state-machine trigger still blocks an illegal jump.
- [x] **Task 3: Pure confirmation rules** (AC: 3, 5, 6, 7) -> `feat(story-2.3): token lifetime, set comparison and delta rules`
  - [x] 3.1 `src/domain/confirmation.py`: `token_is_fresh(snapshot_timestamp, now, ttl)` (`<=`), `tokens_match` (constant time), `has_actionable(items)`, `diff(stored_items, current_items)` returning added, removed and changed, and `delta_text(...)` (deterministic, ordered by key).
  - [x] 3.2 Unit tests: the three boundary instants, a token one millisecond late, ttl 5, equal and different tokens, the delta of every kind (one of each, several, none), the order of the delta, the text.
- [x] **Task 4: The confirmation use case** (AC: 1-11) -> `feat(story-2.3): confirmation use case with re-validation and an atomic claim`
  - [x] 4.1 `src/ports/inbound/confirm_use_cases.py` (`ConfirmUseCases.post_confirm(proposal_id, gate_token)`) and `src/application/confirmation_service.py`: P1 -> P5 -> P2 -> P4 -> P3 -> claim (D3), one clock read, the re-execution of the stored selector through the audited ports inside `recorder.turn()`, ids minted before the transaction, one writer transaction with the claim and the audit rows (`toolcall.confirm_and_dispatch` first), and on zero rows updated a re-read that re-enters P5 (never a direct error). `UnavailableConfirmUseCases` for the broken-database case.
  - [x] 4.2 Unit tests with a failing double for each collaborator (session store, clock, jobs and nodes ports, proposal store, id generator, audit write, unit of work) against a healthy control, and a test for each branch of P1-P5.
- [x] **Task 5: The route and the contract text** (AC: 1, 2, 5, 12, 13) -> `feat(story-2.3): POST /destructive/proposals`
  - [x] 5.1 `src/adapters/inbound/destructive.py` gains `POST /api/v1/destructive/proposals` (body `extra=forbid`, `proposal_id` a plain string, `gate_token` validated against `GateToken`), registered through the container; add the operation to `SERVED_IN_THIS_STORY` in `tests/api/test_contract_routes.py` (it is already in `ALLOWED_MUTATING`) in the same commit.
  - [x] 5.2 Amend the text of `openapi.yaml` (`post_confirm` 200 description) and `contracts.md` (`confirm_and_dispatch` Q1 and `post_confirm`) so they say that until the executor exists the route answers `confirmed`, and which delta lines `CONFIRMATION_STALE` carries (D1, D6). No schema, no DTO.
- [x] **Task 6: Gate, hammer, mutation check and evidence** (AC: 14) -> `test(story-2.3): green phase evidence`
  - [x] 6.1 The tests of Task 1 pass **without having been edited** (`git diff <red commit> -- tests/atdd/test_story_2_3.py docs/evidence/impl2/red-2-3.log` is empty), three times in a row. If one must change, stop and ask.
  - [x] 6.2 Mutation check (see Testing standards), then the full `pytest`, branch coverage, `ruff check .`, `schema_check`, the three `diff` checks. Save the coverage run to `docs/evidence/impl2/flow-a-2-3-coverage.log` and the three ATDD runs to `docs/evidence/impl2/flow-a-2-3-atdd-x3.log`.

## Dev Notes

### What exists today (verified at baseline `4e8f902`)

- Story 2.2: `POST /destructive/dry-runs` and `/copilot/chat` create a `proposals` row in `dry_run` with its selector (`{method: jobs_port.select | nodes_port.select, params}`), the affected items (`{key, actionable, actionable_field, actionable_value}`), `snapshot_timestamp` and a random `gate_token`. Nothing reads a proposal back: `ProposalStorePort` has only `add` and `highest_counters`.
- `proposals` already has `confirmed_at`, the state enum, a CHECK that every state after `dry_run` has a `confirmed_at`, the executor-result columns, and `trg_proposals_state_machine` (`dry_run -> confirmed -> dispatched -> executed | failed`, no jump). It must not be edited (its SHA-256 is checked).
- `domain.dry_run.reexecution_query(stored)` rebuilds `SelectorDTO("filter", params)`; `enumerate_items(records)` produces the items with their `actionable` rule. The same functions give the current set to compare with the stored one.
- `S_CAP` exists in `domain/canonical_strings.py`; `ConfirmationDTO(confirmed_at, caption)`, `PostConfirmRequest`, `PostConfirmResponse` and `GateToken` exist in `dto.py`; the catalog has `PROPOSAL_NOT_FOUND` 404, `GATE_TOKEN_INVALID` 403, `CONFIRMATION_STALE` 409 (`Snapshot stale: {delta}.`), `DRY_RUN_EMPTY_SET` 409, `CONFIRMATION_CONFLICT` 409 (`Proposal {pid} already {state}; confirmation rejected.`) and `PROPOSAL_STATE_INVALID`.
- `POST /api/v1/destructive/proposals` is declared in `openapi.yaml` (`post_confirm`, 200 `Proposal`, 400/403/404/409/502/503) and in `ALLOWED_MUTATING`, and is **not served** (404). `failure_response` shows `failure.observed` as `explanation.observed_values` on a 4xx and hides it on a 5xx.
- `SimClock.advance(seconds=...)` moves the simulated clock forward (never back); the clock is frozen otherwise. The estate has **no write path** (AD-1), so a "state change" in a test is a double on `SimJobs.select` installed before `create_app` (as `tests/support/faults.py` does for outages), never a mutation of the fixtures.
- `DryRunService` is the model for the use case: one clock read, reads inside `recorder.turn()`, ids minted before one `uow.atomic()` that holds the write and the audit rows, and a typed failure that writes nothing.

### Decisions (applied by the story author; override before the red phase is committed)

- **D1. The route ends at `confirmed` (needs the user's confirmation).** The contract says `post_confirm` answers `dispatched | executed | failed`. With no executor, the honest end state of this story is `confirmed`, and the plan (D-P1) assigns the dispatch to 2-4. Story 2-4 will extend the same use case after the claim; until then the 200 body is a `Proposal` in `confirmed`. Only the text of `openapi.yaml` and `contracts.md` changes (Task 5.2); the schema already allows `confirmed`.
- **D2. The token expiry is derived, not stored (decided by the user on 2026-11-08, deferred-work item D-1 of 2-2).** `expires = snapshot_timestamp + gate_token_ttl_seconds` with the setting in force, accepted while `now <= expires`. `proposals` has no column for it and 001 cannot be edited. **Known limitation, accepted:** if `M12_GATE_TOKEN_TTL_SECONDS` changes and the service restarts, tokens issued earlier change their lifetime; the TTL does not change between a dry-run and its confirm in the assignment, so the risk is theoretical and is recorded in the decision log.
- **D3. Evaluation order (normative, contracts):** P1 (the proposal exists) -> P5 (a state other than `dry_run`: an identical token returns the persisted proposal, another is `CONFIRMATION_CONFLICT`) -> P2 (token equals, then fresh) -> P4 (something actionable) -> P3 (re-validation) -> claim. A replay is therefore answered after the TTL and an empty set is refused without a provider call. `refused` has no confirmation to replay: `PROPOSAL_STATE_INVALID`.
- **D4. Token and state outcomes.** On `dry_run`, a token that differs is `GATE_TOKEN_INVALID` 403 (also another proposal's token); the comparison is constant time (`hmac.compare_digest`). On `confirmed`, `dispatched`, `executed`, `failed` or `superseded`, the identical token answers the persisted proposal and a different one is `CONFIRMATION_CONFLICT` 409. A malformed token never reaches the use case: the schema answers `VALIDATION_MALFORMED_BODY` 400.
- **D5. "Nothing to confirm" includes non-actionable items.** The contract's P4 is `len(affected_items) >= 1`; a set made only of non-actionable items (a terminal job, a node in `fault`) would confirm an action that touches nothing, and story 2.2 already disables confirmation for it (`confirmation_enabled = false`, D6 of 2.2). P4 is therefore "at least one item is `actionable`" and answers `DRY_RUN_EMPTY_SET`. Stricter than the text, consistent with it.
- **D6. The stale answer (needs the user's confirmation).** `CONFIRMATION_STALE` for a changed set is the catalog's 409 `ErrorBody` with `message = Snapshot stale: <delta>.`; `<delta>` is deterministic and ordered by key: `added job#job-8904; removed job#job-8901; job#job-8902 running -> succeeded`. The same lines are in `explanation.observed_values`, followed by a last line `confirmation disabled: run a new dry-run`. The proposal is **not modified**: the epics' "re-renders the dry-run with the delta surfaced and confirmation disabled" is met by the body, with no new schema. If the user prefers a typed body with the re-rendered snapshot, that is a contract change and waits for a decision. An **expired token** uses the same code and status with the delta `token expired: <elapsed> s after the snapshot, lifetime <ttl> s` and no other lines, so a client can tell the two apart by the text and never by the code.
- **D7. Claim, audit and replays.** The claim is the single conditional `UPDATE` of Task 2 inside one writer transaction together with the audit rows (head `toolcall.confirm_and_dispatch`, then the re-validation reads). Zero rows means another request won: re-read and re-enter P5; never map the row count to an error. Only the winner writes audit rows; replays and rejections write none (the same rule as 2.2). The losers of a race mint audit ids they do not use (a gap in the sequence, harmless).
- **D8. No identity, no context.** The request model forbids extra fields. The use case reads the session row only for `operator_role` (the audit schema requires it) and ignores the session status and its context, so a reset or expired session confirms like any other. The audit records the role of the session that holds the proposal, never a claim of the request.
- **D9. Ports.** `ProposalStorePort` grows `get` and `claim`; no DTO changes. `confirmation` is rebuilt from `confirmed_at` and `S_CAP`; `executor_result` from its columns when present (story 2-4 fills them).
- **D10. Test controls.** The clock is advanced with `SimClock.advance`; a changing estate is a switchable double on `SimJobs.select`; ordering uses `threading.Barrier` and `threading.Event` gates, never `sleep`. The "Exec = 1" counts of the test design belong to 2-4 (there is no executor here): in this story the equivalent is **one `dry_run -> confirmed` transition and one set of audit rows**.
- **D11. Clock.** One read per request, taken after the proposal is found, so an unknown proposal reads no clock. `CLOCK_UNAVAILABLE` is the typed failure of the clock.
- **D12. Audit order** after a confirm: `toolcall.confirm_and_dispatch`, `toolcall.jobs_port.select` (or `nodes_port.select`), in the same transaction as the claim.
- **D13. Request model.** `proposal_id` is a plain string (an unknown or malformed id is `PROPOSAL_NOT_FOUND`, not a schema error); `gate_token` uses the `GateToken` pattern.

### ATDD cases (`tests/atdd/test_story_2_3.py`, real app, file DB)

Helpers as in 2.2: `app_on(tmp_path)`, `chat`, `open_session`, `proposal_rows`, `estate`, a dry-run helper that returns the proposal, and a switchable `SimJobs.select` double. The fake clock is the container's `SimClock`.

| AC | Case |
|---|---|
| 1 | the Annex dry-run then confirm: 200, valid `ProposalDTO`, `confirmed`, `confirmed_at` = clock, caption byte-exact, `executor_result` null, row `confirmed`, estate unchanged |
| 2 | extra `role` / `user` / `session_id` field: 400, nothing stored; a reset session confirms like a live one; the stored row and the audit carry no identity from the request |
| 3 | boundary at +59.999 s, +60.000 s (accepted) and +60.001 s (409, row still `dry_run`); TTL setting 5 |
| 4 | sequential identical replay equals the first body, no second transition, no new audit row; replay at +120 s |
| 5 | unknown id 404; wrong token and another proposal's token 403; a different token on a confirmed proposal 409; malformed token 400; `refused` row `PROPOSAL_STATE_INVALID`; state and audit unchanged |
| 6 | an empty set and an all-non-actionable set: 409 `DRY_RUN_EMPTY_SET`, jobs port called 0 times |
| 7 | one job no longer actionable plus one new job: 409, both named, row `dry_run`; a changed status; a removed item; an unchanged set confirms |
| 8 | jobs outage during re-validation: 503, row `dry_run`, no audit row; recovery then success |
| 9 | 2 and 50 identical confirms on `Barrier`: one transition, one audit set, all 200 `confirmed`, 0 500; identical vs different token raced: allowed {200, 403, 409}; confirm vs state change in both orders |
| 10 | a failing audit write leaves the proposal `dry_run` (fault on the audit store) |
| 11 | the audit order after a confirm, the session's `operator_role`, no token in the rows |
| 12 | chat -> token -> confirm -> `confirmed`, estate identical |
| 13 | regression guards (pass today and must not be edited): the 2.2 dry-run reply shape, `/copilot/query` stays refusal-only, the dry-run route's 404 for an unknown session |

### Guardrails (docs/impl2-rules.md)

- Use `src/` paths (the epics' `service/core/confirmation.py` and `api/routes/destructive.py` become `src/domain/confirmation.py`, `src/application/confirmation_service.py` and `src/adapters/inbound/destructive.py`).
- Pure rules in `src/domain`; the domain, ports and application rings import no adapter or framework. Time only from the Clock port; the TTL check uses the instant of that single read, never `datetime.now`.
- The Copilot performs **zero** writes to simulated state (AD-1, AD-3); the only writes are the `proposals` row transition and the audit rows, through the one `SqliteWriter`. No executor, no dispatch, no `executor_result` is written here.
- The selector is persisted and re-executed, never derived from text (AD-6). The LLM never states a fact; nothing here reaches the prose writer.
- No `sleep`, `asyncio.sleep` or `waitForTimeout`; order concurrent calls with `threading.Barrier` and `Event`.
- Never mock the unit under test; fakes only at outbound ports. Never weaken an assertion; a committed ATDD case changes only with a log entry and the user's decision (guide E.6).
- `src/dto.py` and `planning/detailed-design/schemas/dto.py` change together or not at all (this story should not change them). Do not run `ruff format` over `src/`: list the files you touched.
- Keep both `epics.md` copies and both `sprint-status.yaml` copies identical.
- Do not edit `migrations/001_*.sql`. Do not touch `console/` or `tests/e2e/`.

### Files

- New: `src/domain/confirmation.py`, `src/ports/inbound/confirm_use_cases.py`, `src/application/confirmation_service.py`, `tests/atdd/test_story_2_3.py`, `tests/unit/test_confirmation.py`, `tests/unit/test_confirmation_service.py`, `docs/evidence/impl2/red-2-3.log`, `docs/evidence/impl2/flow-a-2-3-coverage.log`, `docs/evidence/impl2/flow-a-2-3-atdd-x3.log`, the ATDD checklist.
- Changed: `src/ports/outbound/proposal_store.py`, `src/adapters/outbound/db/proposal_store.py`, `src/adapters/inbound/destructive.py`, `src/application/unavailable.py`, `src/bootstrap.py`, `src/ports/inbound/__init__.py`, `tests/unit/test_ports_query_only.py`, `tests/integration/test_proposal_store.py`, `tests/api/test_contract_routes.py`, `planning/detailed-design/schemas/openapi.yaml` and `contracts.md` (text only), `docs/ai-decision-log.md`, `_bmad-output/implementation-artifacts/deferred-work.md` (close D-1 of 2-2).
- Do not touch: `migrations/001_*.sql`, `src/dto.py`, `planning/detailed-design/schemas/dto.py` (unless a contract change is approved), `fixtures/`, `console/`.

### Testing standards

- Red phase honesty: a failing case fails on the assertion that states the missing behaviour (`404 != 200` for the confirm route, `confirmed` expected, `409` expected), not on an import or fixture error. Run `ruff` on the file before the official run so the log matches the committed file.
- Mutation check after green, one at a time (restore in a `finally`, confirm `git status` of `src` and `tests` is clean): (1) remove the P5 replay check; (2) remove the P3 re-validation; (3) remove the P2 TTL check; (4) make the TTL `<` instead of `<=`; (5) compare the token with the proposal id; (6) claim without `AND state = 'dry_run'`; (7) claim without `AND gate_token`; (8) map zero rows updated to an error; (9) confirm an all-non-actionable set; (10) write the audit rows outside the claim's transaction; (11) read the session context or status; (12) leave out the caption; (13) re-validate with the stored items instead of the re-executed set; (14) a delta that omits the added items. Report any survivor and wait for a decision before editing a test.
- Concurrency: the hammer runs three times in a row; assert the **set** of outcomes and the row and audit counts, never which request won.
- Pin exact values: the caption, the codes, the statuses, the delta text, the instants, the row counts.

### Previous-story intelligence

- **2.2 / I2-21 .. I2-24:** `DryRunService` shows the shape (clock once, `recorder.turn()`, ids before `uow.atomic()`, audit rows with the write). Provider faults are injected by patching the Sim adapter class **before** `create_app`. The refs cap and dedupe of the review are request rules of the dry-run, not of this story. A new `ProposalStorePort` method needs an entry in `OWNED_PORT_METHODS`.
- **2.1 / I2-18 .. I2-20:** a committed ATDD case changes only with a log entry and the user's decision; the 2.1 chat case already changed once (I2-22).
- **1.5 / I2-16:** audit rows commit in the same writer transaction as the write; a test that survives the mutant "feature off" is blind, so reach the real path.
- **Deferred items that land here:** item D-1 of the 2.2 review (the expiry is not stored): decided, see D2; the dispatch part of `confirm_and_dispatch` and the rest of the destructive routes belong to 2-4.

### Git intelligence

Recent commits: story 2.2 (`0407109` red, `57a062b` .. `bcc1b1a` green tasks, `1adb60b` chat reply, `568d756` evidence, `c502192` review fix, `242de21` review records, `4e8f902` closure), all pushed; CI run `42433922694` passed. Commit style: `test(story-2.3): ATDD red phase, recorded before production code`, then `feat(story-2.3): ...` per task, no `Co-Authored-By` line.

### Latest tech notes

No new library, so no version research. `hmac.compare_digest` gives the constant-time token comparison. SQLite `UPDATE ... WHERE state = 'dry_run' AND gate_token = ?` is atomic under the single writer; the row count says who won. `RETURNING` is available but a re-read after zero rows is the contract's rule.

### Project Structure Notes

Pure rules in `src/domain`, use cases in `src/application`, ports in `src/ports`, adapters in `src/adapters/{inbound,outbound}`, ATDD in `tests/atdd`, evidence in `docs/evidence/impl2/`. The old `test/` tree is only a source of contract cases (`test/atdd/module12_contracts.test.py::test_post_confirm_*`, `::test_confirm_and_dispatch_*`).

### References

- [Source: planning/epics.md#Story 2.3; docs/impl2-rules.md Annex-to-specification decisions; task statement PDF pages 30-31; docs/impl2-continuation/03-plan-implementacion.md T-07, T-08 and D-P1]
- [Source: planning/detailed-design/contracts.md `confirm_and_dispatch` P1-P6, Q1-Q4, Q-fail, L1-L3, evaluation order and claim; `post_confirm`; section 5 I9, I10, I13; planning/detailed-design/schemas/openapi.yaml `/destructive/proposals`, `Proposal`, `PostConfirmRequest`]
- [Source: test/test-design.md sections 6.1 (IR-02, IR-03), 6.3.3, OP-I2-1; test/atdd/module12_contracts.test.py `test_confirm_and_dispatch_*`, `test_post_confirm_*`; docs/ai-decision-log.md I2-01, I2-07, I2-21, I2-22, I2-23, I2-24]
- [Source: migrations/001_module12_copilot_schema.sql `proposals` and `trg_proposals_state_machine`; src/dto.py `ConfirmationDTO`, `PostConfirmRequest`, `PostConfirmResponse`; src/domain/dry_run.py; src/application/dry_run_service.py; src/adapters/outbound/db/proposal_store.py; src/adapters/outbound/sim/clock_adapter.py; src/adapters/inbound/errors.py]
- [Source: _bmad-output/implementation-artifacts/2-2-dry-run-snapshot-with-selector-predicate-and-affected-items.md; deferred-work.md "story-2-2"]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5.5 (`claude-sonnet-5-5`), Claude Code, `bmad-create-story`, `bmad-testarch-atdd`, `bmad-dev-story`.

### Debug Log References

- Baseline at `4e8f902`: `pytest` 1824 passed, branch coverage of `src` 97.52%. CI of the pushed history: success (run `42433922694`).
- Audit probes (2026-11-08, real code): `POST /api/v1/destructive/proposals` is declared in `openapi.yaml` and not served; `ProposalStorePort` has no read; the `proposals` table has `confirmed_at`, the CHECK that ties it to the states after `dry_run` and the state-machine trigger; `SimClock.advance` exists; the estate has no write path.

- Green phase (2026-11-08): `tests/atdd/test_story_2_3.py` (45 cases) passes without having been edited, three runs in a row (`docs/evidence/impl2/flow-a-2-3-atdd-x3.log`); `git diff f98a941 -- tests/atdd/test_story_2_3.py docs/evidence/impl2/red-2-3.log` is empty. Full run: `pytest` 1928 passed, branch coverage of `src` 97.65% (`docs/evidence/impl2/flow-a-2-3-coverage.log`), `ruff check .` clean, `schema_check` PASS, both `dto.py` copies and both `sprint-status.yaml` copies identical.
- Mutation check, restored with a `finally` after each: the 14 mutants of the Testing standards list, all killed on the first run: no P5 replay check; no P3 re-validation; no P2 lifetime check; the lifetime with `<` instead of `<=`; the token compared with the proposal id; the claim without its state guard; the claim without its token guard; zero rows mapped to an error; a set with nothing actionable confirming; an audit failure that does not roll the claim back; the session status consulted; the caption left out; re-validation against the stored set itself; the delta omitting the added items.
- Commits: `f98a941` red, `1c95b8c` store get and claim, `ab62a43` pure rules, `019ecdf` the use case, `2c15e7f` the route and the contract text.
- Two slips caught before commit, both in my own tests: the red replay-and-rejection case passed on a 404 (a 404 also writes no audit row), so it now asserts the 200, the head and re-validation rows, the replay and the 409 first; and in the unit rig the service used a recorder different from the one its audited ports record into, and the fake id generator did not reach the audit writer, so the rig now wires both.
- Contract text (D1, D6, confirmed by the user): `openapi.yaml` and `contracts.md` say that the route answers `confirmed` until the executor exists and describe the delta lines; no schema and no DTO changed.
- The contracts' `Exec = 1` is read as one `dry_run -> confirmed` transition and one set of audit rows; the executor and the real exactly-once count are story 2-4.

- Story context created 2026-11-08, scoped against `src/`, `tests/`, `planning/` and `migrations/` at `4e8f902`. Ultimate context engine analysis completed - comprehensive developer guide created.

### File List

- New: `src/domain/confirmation.py`, `src/ports/inbound/confirm_use_cases.py`, `src/application/confirmation_service.py`.
- Changed: `src/ports/outbound/proposal_store.py`, `src/adapters/outbound/db/proposal_store.py` (`get`, `claim`), `src/adapters/inbound/destructive.py`, `src/application/unavailable.py`, `src/bootstrap.py`, `src/ports/inbound/__init__.py`, `planning/detailed-design/schemas/openapi.yaml` and `contracts.md` (text only).
- Tests: `tests/atdd/test_story_2_3.py` (frozen), `tests/unit/test_confirmation.py`, `tests/unit/test_confirmation_service.py`, `tests/api/test_confirm_route.py`; extended `tests/integration/test_proposal_store.py`; adjusted `tests/unit/test_ports_query_only.py` and `tests/api/test_contract_routes.py`.
- Evidence: `docs/evidence/impl2/red-2-3.log`, `flow-a-2-3-atdd-x3.log`, `flow-a-2-3-coverage.log`; the ATDD checklist.

### Change Log

- 2026-11-08: Dev story complete. Tasks 1-6 done, Status -> review.
- 2026-11-08: D1 and D6 confirmed by the user; the red phase was recorded and confirmed.

- 2026-11-08: Story created (`bmad-create-story`). Status -> ready-for-dev. D2 (the derived expiry) was decided by the user; D1 and D6 wait for the user before the red phase.

### Review Findings

Code review of `4e8f902..9a54b2d` (2026-11-08): Blind Hunter, Edge Case Hunter and Acceptance Auditor run in sequence by the reviewer (no subagents, none authorised), over 11 files of production and contract and 480 added lines. All 14 acceptance criteria hold, each with an ATDD case or a unit or API case of its own, and the 14 mutants of the story confirm it. No wall-clock read in the new code (the only `datetime` import is `timedelta`). One probe was run against the real app before reporting.

- [x] [Review][Patch] P-1 (low): a rejected confirmation left no trace. 20 wrong-token attempts left the audit at 5 rows and the application log empty, so a client could probe tokens unseen. A rejection still writes no audit row (D7, as in 2.2), but the six rejection codes now log one warning with the proposal id (escaped with `%r`, cut at 64 characters) and the code, never the token; a success, a replay and a provider failure log nothing [src/application/confirmation_service.py] - fixed in `6d70e5d`
- [x] [Review][Defer] D-1 (low): there is a window between the re-validation and the claim; story 2-4 must make the executor apply only the referenced snapshot's items and re-validate at dispatch [`deferred-work.md`]
- [x] [Review][Defer] D-2 (low): the delta text of `CONFIRMATION_STALE` has no upper bound; not reachable with 32 nodes and 9 jobs [`deferred-work.md`]

Dismissed (3): the audit ids minted and unused by the losers of a race leave gaps in the sequence (described in D7, harmless); the wording `Snapshot stale: token expired: ...` comes from the fixed catalog template; the "confirm first or change first" cases are sequential, not gated, as D10 says.

Mutation check of the patch: no log line, no escaping, the token logged and a success logged - four mutants, all killed (`pytest` 1933 passed, branch coverage of `src` 97.66%).
