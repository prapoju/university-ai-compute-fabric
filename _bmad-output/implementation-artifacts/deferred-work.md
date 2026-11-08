## Deferred from: code review of story-1-1 (2026-10-24)

- Q-port-3 audit seam: story 1.5 introduces the audit writer; wrap the ports in the composition root, no adapter edits needed.
- `/readyz` 503 body exposes absolute paths and exception text: acceptable for an internal prototype; trim before any public exposure.
- Non-editable `pip install .` breaks `PROJECT_ROOT` (top-level package named `src`): consequence of the course layout; the README documents the editable install.
- `select` silently truncates at the 10,000-row cap and deep-copies the store per call: fine for 32 nodes; revisit if stores grow.
- Ids ending in a literal backslash before `#` cannot be expressed: no such id exists in the contract vocabulary.
- No dependency lock file: range pins only; packaging policy for the team to decide.
- `select()` selector vocabulary (`method="filter"`) is provisional and cannot take `Selector.params.node_ids` (contracts.md OP-6 / D55): decided with the user to define it in story 2.2, where dry-run selectors are used.

## Deferred from: code review of story-1-2 (2026-10-25)

- `append_turn` refuses answers with claims/evidence (retryable 503): story 1.3 must persist claims/evidence and remove this guard before registering a diagnosis handler.
- Session context (`prior_intents`, `active_answer_ids`) grows per turn: fine for 30-minute prototype sessions; revisit with the retention decision (OQ-13).
- Id counters are seeded once and only for `session`/`answer`, assuming a single process: extend `highest_counters` when other id kinds are first persisted.
- All `sqlite3.Error` become a retryable 503, including permanent faults: the catalog has no code for them; revisit with the audit stories.
- `isolation_level` of the shared connection is not pinned explicitly: the default is what the store relies on; covered by the atomicity tests.

## Deferred from: code review of story-1-3 (2026-10-25)

- A compound question (`why was alex denied X and why was mateo denied X`) is answered only for the first match: multi-intent detection belongs to the story-1.2 classifier.
- The `CANNOT_CONFIRM` audit evidence is unbounded and includes the user's denials for other models: cap/filter together with the retention decision (OQ-13).
- `CANNOT_CONFIRM` does not state that only the last 30 days were searched (`S_CNC` is a canonical literal): revisit with story 4.1's anti-fabrication wording.
- The prose guard is lexical (AD-8): inflections, homoglyphs, hyphen/space variants and unlisted facts or injected text can pass; a semantic check is out of scope while the writer is simulated.

## Deferred from: code review of story-3-1 (2026-11-06)

- contracts.md `diagnose_schedule_window` Q3 asks for the audit event `toolcall.diagnose_schedule_window` once per diagnosis; no diagnoser emits tool-call audit events yet (same gap in story 1.3). Add with the audit stories.

## Deferred from: code review of story-4-1 (2026-11-07)

- A typed reference of another type is named "not found in state" even when it exists (`why was alex denied policy#catalog.4.2`, follow-up `what about policy#catalog.4.2`): the story-1.3 resolver rule `_key` "typed as something else: unresolved, named as typed". A literal `S_ENF` about an entity that exists is false; decide a wrong-type wording (clarify) with the resolver owner.
- A real `policy#` named in the query is only checked for existence, not tied to the diagnosis: "denied under policy#X" when another clause denied is not corrected. Out of story 4.1 scope (D2).

## Deferred from: code review of story-1-4 (2026-11-07)

- `clock#` read ids restart at `clk-0000000000000001` in every process and `highest_counters` does not seed them. With a file-backed `db_path`, after a restart `GET /api/v1/citations/clock#...` can resolve to another run's clock read and snippet (the "most recent" ordering by `created_at` is also meaningless across restarts, because the sim clock restarts at `M12_CLOCK_START`). Extends the story-1.3 item on id counters: seed the clock counter (or namespace read ids per run) when multi-process or persistent operation is in scope.

## Deferred from: dev of story-1-5 (2026-11-07)

- `browse_state` counts `total` by paging the entity's port (up to 100 page reads at the 10,000 cap, story 1.5 D9). Add a query-only `count` to the read ports if the stores grow beyond the fixture sizes.
- Session-less reads (`get_state_record`, `browse_state`, `get_answer_evidence`, `get_citation`) write no audit rows (story 1.5 D2): auditing them needs a nullable `tool_calls.session_id` (a migration) and a clock read per request.
- Story 1-6 must reserve `ToolCallRecorder` slots in argument order before a parallel fan-out; the recorder appends in completion order (story 1.5 D4, review D-2.1/2.3).
- Per-diagnoser audit events (`toolcall.diagnose_schedule_window`, `toolcall.assemble_evidence`, ...) named in contracts.md are still not emitted: story 1.5 audits the `toolcall.answer_query` head and every provider-port read (D3), which covers the reads those events would describe. The story-3-1 item above stays open for the named events.

## Deferred from: code review of story-1-5 (2026-11-07)

- A secret pasted where an entity goes (`why was student sk-live-777 denied ...`) is stored as `user#sk-live-777` in `tool_calls.params_summary`. AC 4 covers `key=value` and `bearer` forms only, and the `answers` table stores the whole query anyway (`query`, `prose`): accepted as a documented limitation (decision D-1, option a). Revisit with the retention decision (OQ-13).
- `PAGINATION_INVALID` reads "page_size 20 exceeds cap 100" when `page` is the offender, because the catalog message only takes `v=page_size`. Changing the wording is a contracts section 4 amendment.
- `SqliteWriter._rollback` ignores a failed `ROLLBACK`, which would leave the connection in a transaction and fail every later `BEGIN IMMEDIATE`. Needs a real I/O error; add a self-heal (`ROLLBACK` before `BEGIN IMMEDIATE` when `in_transaction`) if it is ever observed.
- `audited` computes the bound params and `_dump` for every port call even when no turn is active, and `/state` browse pages the port up to 100 times for `total`. Measure under the story 1-6 k6 budget before optimizing (check the recorder is active first).

## Deferred from: code review of story-4-2 (2026-11-07)

- `failure_response` hides `observed` on a 5xx but renders `failure.message` as is: a `Failure` that carries its own `message` would show it in the 503 body. No adapter sets one today. Fix by rendering the catalog literal on every 5xx, but some 5xx templates take parameters (`AUDIT_WRITE_FAILED`), so decide how those render first. Touches `src/adapters/inbound/errors.py`, which story 4.2's plan does not authorize.
- `/readyz` answers 200 while the clock raises (503 for a typed `fail()`): the `clock` readiness check reads the `available` flag so probing consumes no clock read id. A real clock adapter needs a probe that reads nothing it must record.

## Deferred from: code review of story-2-1 (2026-11-07)

- The clarification reason of a compound destructive query reads "the query mixes a diagnosis with a destructive action" even when there is no diagnosis (`drain ws-gpu-11 and ws-gpu-12`, `cancel jobs for group 2 and group 4`). A second reason ("the query asks for more than one action or target") would be more accurate, but four cases of `tests/atdd/test_story_2_1.py` compare with the current constant, so it needs a decision on editing a committed ATDD file.
- `VALIDATION_BAD_ACTION` reuses the catalog template for an unknown verb ("Unknown action {value}; expected one of ...") when the verb is known but aimed at the wrong kind of target. The wording is fixed by contracts section 4.
- Story 2-2 must decide how "every pending CS201 job" is selected: `cs201` is a course value that answers `Entity Not Found` (log I2-18), and no group owns those jobs (they sit in `group-2`, `group-4` and `group-7`). The `Fleet` target of story 2.1 (`cordon entire lab`, `Delete all pending jobs`) is refused without a selector, so 2-2's dry-run must also define the selector for each fleet scope (`any`, `nodes`, `jobs`).

## Deferred from: code review of story-2-2 (2026-11-07)

- **Resolved in story 2-3 (D2, decided by the user 2026-11-08):** the expiry is derived as `snapshot_timestamp + gate_token_ttl_seconds`, accepted while `now <= expires`; the limitation below is accepted and recorded in the decision log (I2-25). Original item: the expiry of a gate token is not stored: `proposals` has no expiry column and the migration is SHA-256 protected, so `token_expires_at` is only in the dry-run reply. Story 2-3 must derive it as `snapshot_timestamp + gate_token_ttl_seconds`; if the setting changes between a restart and a confirm, the tokens already issued change their lifetime. Decide in 2-3 whether to accept that, to store the lifetime next to the snapshot (a new migration, not an edit of 001) or to compare against the lifetime in force at dry-run time.
- `select` truncates silently at `SELECT_CAP` (10,000 rows, D50): a dry-run over more records than that would under-report its snapshot with no signal. The estate has 32 nodes and 9 jobs, so it cannot happen today. A real provider adapter should return a typed failure above the cap, or the dry-run should refuse a result that reaches it.
- The cap of 50 `target_refs` per dry-run (review P-1) is a rule of `DryRunService`, not a field of `PostDryRunRequest`: `dto.py` and `openapi.yaml` still say only `min_length=1`. Add `maxItems: 50` to the contract if another consumer ever needs to know it; that is a contract change, so it needs its own decision.
