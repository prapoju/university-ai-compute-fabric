---
baseline_commit: 01f74d5
---

# Story 2.2: Dry-run snapshot with selector predicate and affected items

Status: in-progress

<!-- Impl-2 Flow A (ATDD-first), Annex 12.4, second of four stories (2-1 .. 2-4). The red phase is
     recorded BEFORE any production code. This story builds the dry-run: the selector, the affected
     items, the snapshot, a per-proposal gate token, the proposals row, `POST /destructive/dry-runs`,
     and the Annex reply of `POST /copilot/chat` (refusal + dry-run summary + token in ONE reply).
     It does NOT confirm, expire or dispatch anything (2-3, 2-4).
     Decisions D1-D12 were applied by the story author following the task statement and the rubric.
     D1 (a new reply schema) and D4 (a select vocabulary) touch the contract: the user confirms them
     before the red phase is committed. -->

## Story

As Nadia,
I want to see every item the action would touch before anything is proposed,
so that the full scope is visible before I decide.

## Acceptance Criteria

Source: `planning/epics.md` Story 2.2 (amended, see D10), `test/test-design.md` section 6.3.2, `docs/impl2-rules.md`, task statement Annex 12.4 (pages 30-31 of the PDF). Requirements: FR-09, NFR-8, AD-4, AD-6, Annex invariant AD-30. Contracts: `propose_destructive_action` P1-P4, Q1-Q4, Q-fail, L1-L2; `post_dry_run`; section 5 I9, I12, I21; OP-6 and D55. Catalog: `ACTION_REFUSED`, `ENTITY_NOT_FOUND`, `CLARIFICATION_REQUIRED`, `VALIDATION_BAD_ACTION`, `SESSION_NOT_FOUND`, `PROVIDER_UNAVAILABLE`, `CLOCK_UNAVAILABLE`.

1. **The Annex scenario answers in one reply (D1, I2-07).** `POST /api/v1/copilot/chat` with `Terminate all active jobs for CS-101` answers HTTP 200 with the `ChatRefusalResponse`: `refusal` is the canonical `ErrorBody` `ACTION_REFUSED` / `Action refused.`; `impact_summary` is exactly `3 active jobs will be terminated across nodes ws-gpu-02, ws-gpu-05, ws-gpu-08` (the Annex ids adapted to the fixtures, `docs/impl2-rules.md`); `proposal` has `state = dry_run`, `action = cancel_jobs` and a `gate_token`; `token_expires_at` is the snapshot instant plus 60 s; `confirmation_enabled` is true. The cluster state is unchanged and exactly one `proposals` row exists, in `dry_run`.
2. **`CS-101` resolves exactly, `CS101` does not (AD-7, F-2).** `CS-101` (any case, `cs-101`) resolves to `group#CS-101`. `Terminate all active jobs for CS101` answers `Entity Not Found in State: group#cs101.` (the reference is named in the normalised, case-folded text, as in story 2.1) with 0 proposal rows and no token.
3. **The selector is the exact provider query and it re-executes (AD-6, L1).** For the Annex case the persisted selector is `{"method": "jobs_port.select", "params": {"group_id": "group#CS-101", "status": "running"}}`. Re-running it through the real `jobs_port` returns the same three keys. The selector is built from the resolved target and the action, never from the query text, and the query text is stored nowhere in the proposal.
4. **Every affected item is enumerated, with its own status (D55).** Each item is `{key, actionable, actionable_field, actionable_value}`. The CS-101 items are `job#job-8901`, `job#job-8902`, `job#job-8903`, all `actionable = true`, `actionable_field = "status"`, `actionable_value = "running"`. `delete all pending jobs for group 2` lists exactly the pending jobs of `group#group-2` (`job#job-8824`), and a job with no node is listed, never given a fabricated one.
5. **The status comes from the action, not from the text (D3).** `cancel_jobs` selects `running` jobs; `delete_jobs` selects `pending` jobs; for a single `job` target the selector is that job's `id`, whatever its status, and a job already in a terminal status is enumerated with `actionable = false` (D55).
6. **An empty or non-actionable set disables confirmation (Q-fail, D6).** `cancel all running jobs for group 2` (no running job) answers a proposal with `affected_items = []`, `confirmation_enabled = false` and `impact_summary = "0 affected items"`; the `proposals` row exists in `dry_run` and `confirmation` is null. The `DRY_RUN_EMPTY_SET` 409 is raised at confirm time by story 2-3, not here.
7. **An unresolved target is `Entity Not Found in State` before any dry-run (AD-4).** No proposal row, no token. A verb on the wrong kind of target is the 400 `VALIDATION_BAD_ACTION` of story 2.1.
8. **Node actions and fleet scopes get a selector too (D2, D4).** `cordon ws-gpu-02` persists `{"method": "nodes_port.select", "params": {"node_ids": ["node#ws-gpu-02"]}}`. `cordon entire lab` persists `{"method": "nodes_port.select", "params": {}}` and enumerates all 32 nodes, the one in `fault` (`ws-gpu-11`) with `actionable = false`. `Delete all pending jobs` persists `{"method": "jobs_port.select", "params": {"status": "pending"}}`.
9. **`POST /api/v1/destructive/dry-runs` is served (contracts `post_dry_run`).** Body `{query_text, action, target_refs, session_id}`; it answers the contract `Proposal` (valid `ProposalDTO`), or the canonical 200 `ENTITY_NOT_FOUND` / `CLARIFICATION_REQUIRED`, 404 `SESSION_NOT_FOUND`, 400 `VALIDATION_BAD_ACTION` / `VALIDATION_MALFORMED_BODY`. A `query_text` that holds more than one destructive intent is the compound clarification of story 2.1.
10. **One proposal and one token per dry-run, under concurrency (IR-03, IR-06).** Two simultaneous dry-runs on one session give 2 distinct `proposal_id`s and 2 distinct tokens, both persisted, with no `IntegrityError`. 50 concurrent dry-runs over 50 sessions give 50 rows, 50 unique `gate_token`s and 0 HTTP 500s. The ids are checked as a set (D9). Every token matches `^gt-[0-9a-f]{32}$`.
11. **The real app never binds the deterministic token source (IR-06, D7).** Two fresh apps issue different first tokens. Unit tests keep the deterministic adapter.
12. **The clock fixes the snapshot and the token lifetime (D7).** `snapshot_timestamp` is the fake-clock instant of the dry-run. The lifetime is `Settings.gate_token_ttl_seconds` (env `M12_GATE_TOKEN_TTL_SECONDS`, default 60, minimum 1): with 5 the reply says `token_expires_at` = snapshot + 5 s.
13. **A provider failure leaves no partial snapshot (AD-12).** With the jobs provider failing during the enumeration, the dry-run answers 503 `PROVIDER_UNAVAILABLE`, persists 0 proposal rows and issues no token. Through `/copilot/chat` the refusal turn **is** recorded and the reply is that 503 (D8).
14. **`/copilot/query` stays refusal-only (I2-07).** The same destructive query through `/copilot/query` answers the story 2.1 `ACTION_REFUSED` envelope: 0 proposal rows, no token.
15. **Nothing that already works changes (IR-12).** `group-2`, `group-4`, `group-7`, `job-8823`, `job-8830` and the S1, S2 and `ghost_user_99` answers are unchanged; the refusal, clarification and `Entity Not Found` behaviour of story 2.1 is unchanged.
16. **The dry-run is audited.** After a chat reply the session audit lists, in call order, `toolcall.answer_query`, `toolcall.groups_port.get`, `toolcall.propose_destructive_action`, `toolcall.groups_port.get`, `toolcall.jobs_port.select`, every row with the session's `operator_role` and one clock instant per use case (D12).
17. **Gate.** `ruff check .` is clean, `test/ci/schema_check.py` passes, `src/dto.py` equals `planning/detailed-design/schemas/dto.py` byte for byte after both change together, both `epics.md` and both `sprint-status.yaml` copies are identical, branch coverage of `src` stays at 90% or above, and the full `pytest` passes.

## Tasks / Subtasks

Flow A. Task 1 is the **red phase** and it ends at a hard stop: nothing in `src/`, `fixtures/`, `planning/detailed-design/` or `migrations/` changes until the red log is committed.

- [x] **Task 1: ATDD red phase** (AC: 1-17) -> `test(story-2.2): ATDD red phase, recorded before production code`
  - [x] 1.1 Run `/bmad-testarch-atdd` (Murat) with the prompt of guide D.2. Write `tests/atdd/test_story_2_2.py` against the real app (file DB under `tmp_path`, `TestClient(create_app(...), raise_server_exceptions=False)`), covering the "ATDD cases" below. No `skip`, no `xfail`.
  - [x] 1.2 Run `pytest tests/atdd/test_story_2_2.py -q --tb=short 2>&1 | tee docs/evidence/impl2/red-2-2.log`. Every failure must be an assertion on missing behaviour, never an import, fixture or syntax error. A case that already passes is kept unchanged and labelled `regression guard`.
  - [x] 1.3 Run `ruff check` on the new file **before** the official run (story 2.1: the log must match the committed file). Show the user the full log and **stop**. Commit only `tests/atdd/test_story_2_2.py`, the log and the ATDD checklist, after the user confirms.
- [x] **Task 2: Fixtures, the `node` field and the select vocabulary** (AC: 2, 4, 8, 15) -> `feat(story-2.2): group CS-101, the job node field and the select vocabulary`
  - [x] 2.1 `fixtures/estate/groups.json`: add `group#CS-101` (name `CS-101`, no members). `fixtures/estate/jobs.json`: add `job#job-8901`, `job#job-8902`, `job#job-8903` (`group_id` `group#CS-101`, `course` `CS101`, `status` `running`, `node` `node#ws-gpu-02`, `node#ws-gpu-05`, `node#ws-gpu-08`). Do not touch any existing record.
  - [x] 2.2 `JobRecordDTO` gains `node: Optional[str] = None`. Change **both** `src/dto.py` and `planning/detailed-design/schemas/dto.py` in the same commit (they must stay byte-identical), `contracts.md` section 0.3 (`JobRecord`) and the `JobRecord` schema of `openapi.yaml`.
  - [x] 2.3 The simulated `NodesPort.select` understands `node_ids` (D4) and a list value in any `select` parameter means "one of" (exact type per element); scalar parameters keep the exact-equality rule. Amend `contracts.md` OP-6 / D55 and the `jobs_port`/`nodes_port` vocabulary note accordingly.
  - [x] 2.4 `tests/api/test_state_api.py::test_every_record_is_rendered_field_for_field` compares each state record with the fixture JSON, and the API will render `node: null` for the six existing jobs that have no `node` key. Decide in the development step between spelling `"node": null` in the existing job records (no semantic change) and making the test apply the DTO defaults; either way say so in the log (plan T-06). Update the tests that pin the old record counts (`tests/unit/test_fixture_estate.py`, `tests/unit/test_story_1_1_estate_ports.py`, the `/state` totals) **deliberately**, and say so in the Debug Log and the decision log (plan T-06).
- [x] **Task 3: Pure dry-run rules** (AC: 3, 4, 5, 6, 8, 12) -> `feat(story-2.2): dry-run selector, items and summary rules`
  - [x] 3.1 `src/domain/dry_run.py` (new, pure): `build_selector(action, target)` (D2, D3), `enumerate_items(action, records)` with the actionable rules of D5, `impact_summary(action, records)` (exact wording below) and `token_expiry(snapshot, ttl_seconds)` over the existing instant helpers. No I/O, no clock, no adapter import.
  - [x] 3.2 Unit tests for each rule, including: group, job and node targets, fleet scopes, the three statuses, a terminal job, a `fault` node, an empty set, a job without a node, the pluralisation and the node list order.
- [x] **Task 4: Proposal store, token source and settings** (AC: 3, 10, 11, 12) -> `feat(story-2.2): proposal store, secure gate tokens and the token lifetime`
  - [x] 4.1 `src/ports/outbound/proposal_store.py` (`ProposalStorePort`: `add`, `get`, `highest_counters`) and `src/adapters/outbound/db/proposal_store.py` over the one `SqliteWriter` (insert in one writer transaction, selector as JSON with the allowlisted method, `gate_token` unique). Export through `src/ports/outbound/__init__.py`. Add the `proposal` counter to the seeding of `SimIdGen` in `bootstrap._wire_sessions`.
  - [x] 4.2 `SecureTokenIdGen` (an `IdGenPort` that delegates every kind to the deterministic generator except `gate_token`, which is `gt-` plus `secrets.token_hex(16)`), wired in `bootstrap.py`. A bootstrap unit test asserts that the container never binds a plain `SimIdGen` for tokens.
  - [x] 4.3 `Settings.gate_token_ttl_seconds` (`Field(60, ge=1)`, env `M12_GATE_TOKEN_TTL_SECONDS`) with its test in `tests/unit/test_config.py`.
- [x] **Task 5: The dry-run use case and its route** (AC: 3, 7, 9, 10, 13, 16) -> `feat(story-2.2): POST /destructive/dry-runs`
  - [x] 5.1 `src/ports/inbound/destructive_use_cases.py` (`DestructiveUseCases.post_dry_run`) and `src/application/dry_run_service.py`: P1-P4 of the contract in order (action enum, active session, resolve and fit every `target_ref`, compound check of `query_text`), one clock read, the enumeration through the audited ports inside `recorder.turn()`, ids minted before the transaction, then one writer transaction that inserts the proposal and its audit rows (`toolcall.propose_destructive_action` head first). A failure before the insert writes nothing.
  - [x] 5.2 `src/adapters/inbound/destructive.py` (`POST /api/v1/destructive/dry-runs`), registered in `app.py`; `UnavailableDestructiveUseCases` for the broken-database case. Add the operation to `SERVED_IN_THIS_STORY` in `tests/api/test_contract_routes.py` (it is already in `ALLOWED_MUTATING`) in the same commit.
- [x] **Task 6: The Annex reply of `/copilot/chat`** (AC: 1, 6, 13, 14, 16) -> `feat(story-2.2): chat answers refusal, dry-run summary and token in one reply`
  - [x] 6.1 `ChatRefusalResponse` in both `dto.py` copies and `openapi.yaml` (`/copilot/chat` 200 becomes `oneOf` AnswerEnvelope, ErrorBody, ChatRefusalResponse), D1.
  - [x] 6.2 `src/ports/inbound/chat_use_cases.py` and `src/application/chat_service.py`: open the session, submit the query (the story 2.1 refusal turn), and when the outcome is `ACTION_REFUSED` call `post_dry_run` with the verb and target the domain parser read (the same `parse_destructive` the handler used). Every other outcome is returned untouched. `copilot_chat` calls it; `copilot_query` does not change.
- [ ] **Task 7: Gate, mutation check and evidence** (AC: 17) -> `test(story-2.2): green phase evidence`
  - [ ] 7.1 The tests of Task 1 pass **without having been edited** (`git diff <red commit> -- tests/atdd/test_story_2_2.py docs/evidence/impl2/red-2-2.log` is empty). If one must change, stop and ask.
  - [ ] 7.2 Mutation check (see Testing standards), then the full `pytest`, branch coverage, `ruff check .`, `schema_check`, the three `diff` checks. Save the coverage run to `docs/evidence/impl2/flow-a-2-2-coverage.log`.

## Dev Notes

### What exists today (verified at baseline `01f74d5`)

- Story 2.1: a destructive query resolves its target (`group`, `job`, `node`) through `EntityResolver.resolve_target`, is refused as a stored, audited turn with `Action refused.`, and creates no proposal row and no token. `domain.safety.parse_destructive` returns `DestructiveRequest(verb, Target | Fleet)`, `Compound` or `Unnamed`. `POST /api/v1/copilot/chat` is a thin route that answers exactly what `/copilot/query` answers.
- `POST /api/v1/destructive/dry-runs` exists in `openapi.yaml` (request `PostDryRunRequest`, response `Proposal` or a canonical 200) and in `ALLOWED_MUTATING`, but it is **not served**: it is not in `SERVED_IN_THIS_STORY` and answers 404. `dto.py` already has `PostDryRunRequest`, `PostDryRunResponse`, `ProposalDTO`, `DryRunSnapshotDTO`, `AffectedItemDTO`, `SelectorDTO` and `GateToken`. There is no DTO for the chat reply.
- `migrations/001_module12_copilot_schema.sql` already has `proposals` (`proposal_id` `prop-` + 16 hex, `state`, `action`, `selector` JSON whose `method` is **allowlisted to `jobs_port.select` or `nodes_port.select`**, `affected_items` JSON array, `snapshot_timestamp`, `gate_token` UNIQUE `gt-` + 32 hex, `created_at`, `updated_at`). It must not be edited (its SHA-256 is checked).
- The simulated providers' `select` takes `SelectorDTO(method="filter", params=...)` and is an exact-type equality filter over record fields (an unknown field is `VALIDATION_MALFORMED_BODY`). So the persisted `method` (`jobs_port.select`) names the port operation, and re-execution rebuilds `SelectorDTO("filter", params)` from the persisted params (D2).
- `SimIdGen` knows the kinds `proposal` (`prop-`, 16) and `gate_token` (`gt-`, 32) and is deterministic. The real app builds only `SimIdGen`; there is no secure token source yet.
- `Settings` has `audit_retention_cap` but no token lifetime. `docs/impl2-rules.md` fixes the lifetime at 60 s, configurable.
- Fixtures: groups `group-2`, `group-4`, `group-7` (no CS-101); 6 jobs (one pending per group plus `job-8801` cancelled, `job-8812` succeeded, `job-8830` running in group-4), none with a `node`; 32 nodes (`ws-gpu-11` is `fault`; `ws-gpu-02` and `-08` are `available`, `-05` is `reserved`). `JobRecordDTO` has no `node`.
- The audit and recorder machinery of story 1.5 (`ToolCallRecorder.turn()`, `AuditWriter.entries_for`, `uow.atomic()`) is what a use case outside `SessionService` reuses to audit its port reads and write its rows atomically.

### Decisions (applied by the story author; the user confirms D1 and D4 before the red phase)

- **D1. The reply of `/copilot/chat` for a refused destructive request is a new schema, `ChatRefusalResponse`** `{refusal: ErrorBody, impact_summary: str, proposal: Proposal, token_expires_at: Instant, confirmation_enabled: bool}`. The task statement defines no schema; `ErrorBody` is `extra="forbid"` and is the canonical envelope for every other route, so it is not widened. This adds a DTO to both `dto.py` copies and a schema to `openapi.yaml`, a contract change the plan did not spell out: **confirm before the red phase**.
- **D2. Persisted selector form.** `{"method": "jobs_port.select" | "nodes_port.select", "params": {...}}`; the method names the port operation (the table allowlists exactly those two values) and `params` is the equality filter. Re-execution calls the port with `SelectorDTO("filter", params)`.
- **D3. The status filter comes from the action.** `cancel_jobs` -> `status: running` ("active", `docs/impl2-rules.md`); `delete_jobs` -> `status: pending`. For a group target: `{group_id, status}`; for a fleet scope: `{status}`; for a `job` target: `{id}` with no status filter. The query text decides none of it. This refines the contract's blanket `status: running` for group targets, which cannot express "delete all pending jobs".
- **D4. Select vocabulary (backlog item B-03 of story 1-1).** Job selectors: `group_id`, `status`, `id`. Node selectors: `node_ids` (a list of node keys, D55) and `id`; an empty `params` means every record. A list value in any parameter means "one of". Amend `contracts.md` OP-6 / D55 and the port docs in the same commit as the sim change: **confirm before the red phase**.
- **D5. Actionable rules.** Job item: `actionable_field = "status"`, `actionable_value = <the job's status>`, `actionable = status in {pending, running}`. Node item: `actionable_field = "status"`, `actionable_value = <the node's status>`, `actionable = status != "fault"`. Items are ordered by key.
- **D6. An empty or fully non-actionable set** still creates the proposal row in `dry_run` (contracts Q-fail) with `confirmation_enabled = false` and the summary `0 affected items`; the `DRY_RUN_EMPTY_SET` rejection is story 2-3's P4.
- **D7. Token and lifetime.** The real app issues tokens with `secrets.token_hex(16)` through a wrapper `IdGenPort` (`SecureTokenIdGen`); every other id stays deterministic, so FR-14 determinism of answers is untouched. `token_expires_at = snapshot_timestamp + gate_token_ttl_seconds`, derived from the snapshot and never from a confirm time. Enforcement of the lifetime is story 2-3.
- **D8. Chat is two steps, not one transaction.** The refusal turn (story 2.1) is stored first; the dry-run then runs. If the dry-run fails the refusal turn stays recorded and the reply is the typed failure (test design 6.3.1). Both steps are individually atomic.
- **D9. Ids.** `proposal_id` and the token are minted before the writer transaction, in a fixed order. Concurrency tests assert the **set** of ids, not which request got which (test design 6.3.2). Seed the `proposal` counter from the table on start (`highest_counters`).
- **D10. `cs201` is not enumerated.** It answers `Entity Not Found` since story 2.1 (log I2-18). Both `epics.md` copies now use the Annex scenario and `group 2` for the examples of Story 2.2 (commit `01f74d5`). `test/test-design.md` 6.3.2 still has a `cs201` row; it is not edited and this story's ATDD is the reference. Logged in I2-21.
- **D11. `POST /destructive/dry-runs` takes explicit `target_refs`.** Each ref is a typed key (`group#...`, `job#...`, `node#...`) or a bare token resolved for the action (job verbs: group first, then job; node verbs: node). All refs must be of one kind, otherwise the compound clarification; a single ref gives a scalar filter, several give a list. Fleet scopes exist only through chat (they have no `target_refs`).
- **D12. Audit order.** The use case records its port reads inside `recorder.turn()` and writes `toolcall.propose_destructive_action` first, then the reads, in the same transaction as the proposal row. Chat therefore shows five rows in the order of AC 16.

### The impact summary (exact wording, pure function)

`{n} {noun} will be {verb}` with `across nodes {n1}, {n2}, ...` appended when at least one affected job has a node, the nodes distinct and sorted. Only actionable items count. Nouns: `active jobs` (cancel_jobs on running), `pending jobs` (delete_jobs on pending), `jobs` (a job target), `nodes` (node verbs); singular for 1 (`1 pending job will be deleted`). Verbs: `terminated` (cancel_jobs), `deleted` (delete_jobs), `cordoned`, `drained`. Nodes have no `across nodes` clause. An empty set is exactly `0 affected items`. The Annex string is `3 active jobs will be terminated across nodes ws-gpu-02, ws-gpu-05, ws-gpu-08` (bare node ids, without the `node#` prefix).

### ATDD cases (`tests/atdd/test_story_2_2.py`, real app, file DB)

Each case asserts the state **and** what did not happen (no estate change, no extra proposal row, no token on a refusal-only route, no executor call because none exists).

1. The Annex scenario through `/copilot/chat` (AC 1, 3, 4, 12, 16): the whole reply, the persisted row read from the real table, the re-executed selector, the audit order, the snapshot instant.
2. `CS101` and `cs-101` (AC 2); an unresolved target (`delete all pending jobs for cs201`, `... group 99`) answers `Entity Not Found` with 0 rows (AC 7).
3. Status by action and the four target kinds (AC 4, 5, 8): `delete all pending jobs for group 2`, `cancel job 8823`, `cancel job 8801` (terminal, `actionable = false`), `cordon ws-gpu-02`, `cordon ws-gpu-11` (fault), `cordon entire lab`, `Delete all pending jobs`.
4. Empty set (AC 6): `cancel all running jobs for group 2`.
5. `POST /destructive/dry-runs` directly (AC 9): the valid `Proposal`, 404, 400s, the compound clarification, `ENTITY_NOT_FOUND`.
6. Concurrency (AC 10): `Barrier(2)` on one session, and 50 sessions through 50 threads, asserting the id sets and 0 HTTP 500s.
7. Time and settings (AC 12): `M12_GATE_TOKEN_TTL_SECONDS=5` and the default.
8. Failure (AC 13): the jobs provider failing mid-enumeration (use `tests/support/faults.py`, patching the Sim class before `create_app`): 503, 0 rows, no token; through chat the refusal turn is recorded.
9. Token source (AC 11): two fresh apps give different first tokens; the format.
10. `/copilot/query` stays refusal-only (AC 14).
11. Regression guards, labelled and not edited (AC 15): group-4 and the S1/S2 answers, the story 2.1 refusal.
12. Red proofs recorded in the log: persisting the dry-run without the selector fails case 1; removing the group-target branch fails the Annex case; widening the selector to `course = CS101` changes the count.

### Guardrails (docs/impl2-rules.md)

- Use `src/` paths (the epics' `service/core/dry_run.py` and `api/routes/destructive.py` become `src/domain/dry_run.py`, `src/application/dry_run_service.py` and `src/adapters/inbound/destructive.py`).
- Pure rules in `src/domain`; the domain, ports and application rings import no adapter or framework. Time only from the Clock port; ids only from `idgen_port`.
- The Copilot performs **zero** writes to simulated state (AD-1, AD-3); the only write is the Module-12-owned `proposals` row (+ audit rows) through the one `SqliteWriter`.
- The selector is persisted and re-executed, never derived from query text (AD-6, L1). The LLM never states a fact; nothing here reaches the prose writer.
- No `sleep`, `asyncio.sleep` or `waitForTimeout`; order concurrent calls with `threading.Barrier`.
- Never mock the unit under test; fakes only at outbound ports. Never weaken an assertion; a committed ATDD case changes only with a log entry and the user's decision.
- `src/dto.py` and `planning/detailed-design/schemas/dto.py` change together or not at all. Do not run `ruff format` over `src/`: list the files you touched (it rewrites `dto.py`).
- Keep both `epics.md` copies and both `sprint-status.yaml` copies identical.
- Do not edit `migrations/001_*.sql`. Do not touch `console/` or `tests/e2e/`.

### Files

| File | Change |
|---|---|
| `tests/atdd/test_story_2_2.py`, `docs/evidence/impl2/red-2-2.log` | new (red phase, first commit) |
| `fixtures/estate/groups.json`, `fixtures/estate/jobs.json` | add `group#CS-101` and 3 running jobs |
| `src/dto.py`, `planning/detailed-design/schemas/dto.py` | `JobRecordDTO.node`, `ChatRefusalResponse` (together) |
| `planning/detailed-design/contracts.md`, `schemas/openapi.yaml` | `JobRecord.node`, OP-6 / D55 vocabulary, `ChatRefusalResponse`, chat 200 `oneOf` |
| `src/adapters/outbound/sim/fixtures_adapter.py` | `node_ids` and list membership in `select` |
| `src/domain/dry_run.py` | new |
| `src/ports/outbound/proposal_store.py`, `src/adapters/outbound/db/proposal_store.py` | new |
| `src/adapters/outbound/sim/idgen_adapter.py` | `SecureTokenIdGen` |
| `src/config.py` | `gate_token_ttl_seconds` |
| `src/ports/inbound/destructive_use_cases.py`, `chat_use_cases.py`, `src/application/dry_run_service.py`, `chat_service.py` | new |
| `src/adapters/inbound/destructive.py`, `copilot.py`, `app.py`, `src/application/unavailable.py`, `src/bootstrap.py` | route, wiring |
| `tests/api/test_contract_routes.py` | `SERVED_IN_THIS_STORY` |
| `tests/unit/` (domain, store, idgen, config, bootstrap, services) and the fixture-count tests | new / updated |
| `docs/evidence/impl2/flow-a-2-2-coverage.log` | new |
| `docs/ai-decision-log.md`, `deferred-work.md` | closing entries |

### Testing standards

- Red phase honesty: a failing case fails on the **assertion that states the missing behaviour** (`404 != 200` for the dry-run route, `ACTION_REFUSED` without a proposal, `Entity Not Found` for `group#CS-101`). Run `ruff` on the file before the official run so the log matches the committed file.
- Mutation check after green, one at a time (restore with `git checkout -- <file>`, confirm `git status` of `src` and `tests` is clean): (1) persist the proposal without its selector; (2) remove the group-target branch of the selector builder; (3) widen the group selector to `course`; (4) take the status from the query text; (5) mint the token with the deterministic generator; (6) enumerate a partial snapshot when the provider fails; (7) drop the `actionable` rule for a fault node; (8) compute `token_expires_at` from the wrong instant; (9) make `/copilot/query` build a proposal; (10) lose the proposal counter on restart. Report any survivor and wait for a decision before editing a test.
- Pin exact values: the code, the literals, the selector JSON, the key list, the summary string, the row counts, the regex of the token.

### Previous-story intelligence

- **2.1 / I2-18, I2-19, I2-20:** the classifier already yields the verb and the target; the review made an unnamed referent a clarification. Fleet scopes reach this story as `Fleet(any | nodes | jobs)` and **need a selector here** (deferred item). `cs201` answers `Entity Not Found`. The 2.1 ATDD file is frozen; do not edit it.
- **4.2 / I2-17:** inject a provider fault by patching the Sim adapter class **before** `create_app` (the `audited()` wrapper binds the method at build time); `tests/support/faults.py` exists.
- **1.5 / I2-16:** audit rows commit in the same writer transaction as the write; mint ids before the transaction; a test that survives the mutant "feature off" is blind, so reach the real path.
- **1.4:** `src/dto.py` must stay a verbatim copy; `ruff format` rewrites it.
- **Deferred items that land here:** `jobs_port.select` vocabulary (story 1-1, B-03); the `JobRecord.node` contract and port-schema test (B-02); the `S_CAP`, confirmation and expiry belong to 2-3.

### Git intelligence

Recent commits: story 2.1 red, green and review (`fe2df33` .. `fd87eb4`), the 2.2 epics amendment (`01f74d5`). The CI of the pushed history passed (run `42420632700`). Commit style: `test(story-2.2): ATDD red phase, recorded before production code`, then `feat(story-2.2): ...` per task, no `Co-Authored-By`. No new dependency: `secrets` is stdlib.

### Latest tech notes

No new library, so no version research. `secrets.token_hex(16)` gives 32 lowercase hex characters, which is exactly the `GateToken` pattern, and SQLite `UNIQUE` plus a single writer makes a duplicate token a typed failure rather than a silent overwrite.

### Project Structure Notes

Pure rules in `src/domain`, use cases in `src/application`, ports in `src/ports`, adapters in `src/adapters/{inbound,outbound}`, ATDD in `tests/atdd`, evidence in `docs/evidence/impl2/`. The old `test/` tree is only a source of contract cases.

### References

- [Source: planning/epics.md#Story 2.2; docs/impl2-rules.md Annex-to-specification decisions; task statement PDF pages 30-31]
- [Source: planning/detailed-design/contracts.md `propose_destructive_action` P1-P4, Q1-Q4, Q-fail, L1-L2, OP-6, D55; planning/detailed-design/schemas/openapi.yaml `/destructive/dry-runs`, `Proposal`, `PostDryRunRequest`]
- [Source: test/test-design.md sections 6.1 (IR-03, IR-06, IR-12), 6.3.1, 6.3.2; reviews/review-impl2-shift-left.md F-2, D-1, Q1, Q2; docs/ai-decision-log.md I2-01, I2-07, I2-08, I2-18, I2-20]
- [Source: migrations/001_module12_copilot_schema.sql `proposals`; src/dto.py; src/adapters/outbound/sim/fixtures_adapter.py `_select`; src/adapters/outbound/sim/idgen_adapter.py; src/domain/safety.py; src/application/destructive_handler.py; src/application/session_service.py; src/application/audit_writer.py]
- [Source: _bmad-output/implementation-artifacts/2-1-destructive-intent-classification-and-refusal.md; deferred-work.md "story-2-1" and "story-1-1"]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5.5 (`claude-sonnet-5-5`), Claude Code, `bmad-create-story`.

### Debug Log References

- Baseline at `01f74d5`: `pytest` 1666 passed, branch coverage of `src` 97.24%. CI of the pushed history: success.
- Audit probes (2026-11-07, real app and code): `POST /api/v1/destructive/dry-runs` answers 404 though it is declared; the `proposals` table allowlists the selector method to `jobs_port.select` / `nodes_port.select` while the sim providers accept only `filter`; `NodesPort.select` rejects `node_ids` as an unknown field; there is no `group#CS-101`; `JobRecordDTO` has no `node`.

### Completion Notes List

- Story context created 2026-11-07, scoped against `src/`, `tests/`, `fixtures/` and `planning/` at `01f74d5`. Ultimate context engine analysis completed - comprehensive developer guide created.

### File List

### Change Log

- 2026-11-07: Story created (`bmad-create-story`). Status -> ready-for-dev.
- 2026-11-07: The user confirmed D1 (the `ChatRefusalResponse` schema) and D4 (the select vocabulary) and left the other decisions as written. The red phase may start.
