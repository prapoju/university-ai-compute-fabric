---
title: Impl-2 shift-left review — rules file and test design vs architecture and contracts
status: final (Q1..Q3 decided 2026-11-06; E-1..E-5, E-8, E-9, E-11..E-13 applied; E-6, E-7, E-10 deferred, see decision log I2-01..I2-09)
created: 2026-11-06
reviewers: Winston (architect), Murat (test architect) — party-mode session
reviewed: [docs/impl2-rules.md, test/test-design.md §6]
against: [planning/ARCHITECTURE.md AD-1..AD-15, planning/detailed-design/contracts.md, migrations/001_module12_copilot_schema.sql]
code_observed: [src/adapters/outbound/db/connection.py, src/adapters/outbound/db/session_store.py, src/application/session_service.py, src/application/evidence_assembler.py, src/adapters/outbound/sim/clock_adapter.py, src/adapters/outbound/sim/idgen_adapter.py, src/adapters/inbound/copilot.py, fixtures/estate/*.json]
---

# Impl-2 shift-left review

We reviewed this before any Impl-2 code exists. Each finding names the document and the line it applies to. **Decisions** are binding for Impl-2 once recorded in `docs/ai-decision-log.md` as I2-NN entries. **Questions** (§7) need the product owner.

## 0. Verdict

| Question | Answer |
|---|---|
| 1. Does a rules decision break AD-1..AD-15? | **No decision breaks an invariant as written.** Two decisions are under-specified in ways that *would* break one if built naively: `/copilot/chat` (AD-4 ordering and the refused-row schema, F-1) and the CS-101 target (AD-7 exact match, F-2). |
| 2. Can `asyncio.gather` keep position order and one clock read? | **Yes**, with four conditions (§2): result order is argument order; positions are assigned after the gather; no task reads the clock, mints ids or writes audit rows; and tool timeouts are wall-time infrastructure, not domain time. The test-design rows that measure tool budgets on the fake clock contradict the single-read rule and must be rewritten. |
| 3. Exactly-once dispatch with one writer? | **The compare-and-set UPDATE guarantees it. The writer lock does not.** The lock only stops transactions interleaving on the shared connection. Design in §3. |
| 4. Seam for concurrency tests? | **Outbound ports, injected through the composition root.** Use the real application, domain and file-backed SQLite. Time comes from `SimClock`, ordering from a scripted completion sequencer plus a tool-completion observer, request concurrency from `threading.Barrier`. k6 is the only real-time lane. Details in §4. |
| 5. TG-I2-1, OP-I2-1..3 | TG-I2-1 and OP-I2-1 are resolved (§5). OP-I2-2 is resolved (record it in the walkthrough). OP-I2-3 is a PM decision → §7 Q3. |

---

## 1. Rules decisions vs invariants (question 1)

| Rules decision | Invariants touched | Finding |
|---|---|---|
| `/copilot/chat` as a thin route | AD-4, AD-13, AD-5, R2 | Allowed: it is conversational, not a mutating route outside `/destructive/*` (AD-13). **But see F-1**: the Annex response contains refusal + dry-run + token in one reply, while the repo spec splits refusal (`/copilot/query`) from dry-run (`POST /destructive/dry-runs`). The rules file does not say which shape `/copilot/chat` returns. |
| Token TTL 60 s, configurable | AD-3, AD-15 | Compliant. Neither AD fixes the TTL. `contracts.md` P2 already reads 60 s (verified). |
| Replay returns persisted proposal | AD-3 ("a second dispatch attempt … is rejected") | Compliant. The *dispatch* is rejected; the HTTP reply is the persisted state. The evaluation order still needs stating (OP-I2-1, resolved in §5). |
| `secrets.token_hex(16)` in the production adapter | R2, AD-2/FR-14 | Compliant. Randomness enters through `idgen_port`, as R2 requires. FR-14 compares evidence, citations, class and steps, not tokens. Production needs a **composite** idgen: counters for every kind except `gate_token`. |
| `terminate` → `cancel_jobs` | AD-11, closed `ActionVerb` | Compliant: rule-based mapping, the enum stays closed. |
| 3 running CS101 jobs + nullable `node` | AD-7, AD-1, `contracts.md` §0.3 | **F-2.** `nodes`/`node` is a new `JobRecord` field. §0.3 field sets are exact, so `contracts.md` §0.3 and the port-schema test must change in the same commit. Bigger issue: the Annex prompt says `CS-101`, the fixtures say course `CS101`, and `course` is not an entity type. Under AD-7 (exact, case-folded, no fuzzy), `CS-101` resolves to nothing. `propose_destructive_action` P3 also requires a `job` target for `cancel_jobs`, not a course or group. |
| Real ids in the load query | AD-7, AD-8 | Compliant. |
| Badge `Verified via Policy Engine [RULE-CAT-04]` | AD-8, UX-DR4 | Compliant only if `RULE-CAT-04` comes from a field of the response (a claim or evidence entry), never a console constant (IR-10). Name the field in the 1-7 story. |
| No SSE | §3 synchronous HTTP | Compliant. |
| Access-denial runbook as registry config | AD-9, AD-2 | Compliant if the registry code is chosen **deterministically from `diagnosis_class`** through a config mapping (AD-2: runbook steps are a pure function of the EvidenceSet) and rendered verbatim. The LLM never picks the code. |
| "Annex AD-30", I2-NN ids | — | No conflict. |

### F-1 — `/copilot/chat` response shape vs the refused-row schema (blocking for 2-1)

- `test-design.md` §6.3.1 expects *"2 distinct `proposal_id`s with `state = refused` and **no gate token minted**"*.
- `migrations/001…sql:161` makes `proposals.gate_token NOT NULL UNIQUE`, and `selector`, `snapshot_timestamp` are `NOT NULL` too. **A refused row without a token cannot be inserted.**
- `contracts.md` `propose_destructive_action` Q1 creates the row directly in `dry_run`.
- Annex 12.4 wants refusal + dry-run summary + token **in the same reply**.

**Decision D-1 (architecture side, independent of Q1):** a refusal is a session turn (`ACTION_REFUSED` answer), not a proposal row. A proposal row is born in `dry_run` by `propose_destructive_action`. The `refused` enum value stays in the schema, unused in Impl-2. Fix §6.3.1: replace "2 `proposal_id`s with `state = refused`" with "0 proposal rows, 0 tokens" for the refusal-only path.
**Decided by the product owner (Q1, 2026-11-06):** `POST /api/v1/copilot/chat` returns the refusal, the dry-run impact summary and a single-use gate token valid for 60 s **in one reply**, as Annex 12.4 requires. It executes nothing: dispatch happens only through the separate confirm request (`POST /destructive/proposals`, AD-5). Consequences:
- Chat composes the refusal turn and `propose_destructive_action` in one request. Both use the turn's single `ClockRead`, so `snapshot_timestamp == turn.now.instant` and the token's 60 s starts there (R2).
- AD-4 order holds: the refusal turn is persisted first, then the `dry_run` row. A target that does not resolve stops at `Entity Not Found in State`, and no row or token is created. A compound query routes to clarification, and no row or token is created.
- If the dry-run fails (provider down, IR-07), the reply carries the refusal plus the typed safe failure. No row and no token are created, and the refusal turn is still recorded.
- `/copilot/query` stays refusal-only. The two routes share the refusal use case, and chat adds the dry-run.

### F-2 — The CS-101 target cannot resolve under AD-7 (blocking for 2-2)

Fixture fact: `jobs.json` has `course: "CS101"` jobs in `group#group-2` (cancelled/pending) and no `course` entity type. "Terminate all active jobs for CS-101" therefore yields `Entity Not Found in State` today, and it would be correct to do so. Making it resolve needs a contract change.

**Decided by the product owner (Q2, 2026-11-06), recorded as an Annex adaptation in `docs/impl2-rules.md`:**
- The new fixture group's id is `group#CS-101`. "CS-101" then resolves by AD-7 exact, case-folded match, with no fuzzy rule and no new entity type (AD-13 untouched).
- `contracts.md` `propose_destructive_action` P3 changes: `delete_jobs`/`cancel_jobs` accept a `job` **or a `group`** target. For a group target the selector is `jobs_port.select({group_id, status: running})`. "Active" means `running`.
- The new group holds exactly 3 running jobs on `node#ws-gpu-02`, `node#ws-gpu-05` and `node#ws-gpu-08`. The dry-run gives exactly those 3 items, all `actionable = true`.
- `group-2`, `group-4` and the S1/S2 answers stay byte-identical (IR-12 regression case).
- Red tests: (a) remove the group-target branch of P3 → the Annex scenario returns `VALIDATION_BAD_ACTION`; (b) widen the selector to `course = CS101` → the count is no longer 3. Neither selector shape is fuzzy, so `cs-101` matches by case-fold and `CS101` does **not** match.

---

## 2. `asyncio.gather` vs evidence order and the single clock read (question 2)

**Observed today.** `SessionService.submit_query` takes **one** `ClockRead` inside the per-session guard, mints `answer_id`, and passes both in `TurnInput`. `EvidenceAssembler.gather` reads policy and then events sequentially. Positions are assigned by the pure `diagnose_access_denial` over the returned tuples. Claim ids are minted after prose (`mint_claims`). Request handlers are **sync** and run on FastAPI's thread pool.

**Decision D-2 — conditions for the parallel dispatcher (1-6):**
1. **Order.** `gather` returns results in argument order regardless of completion order. Positions keep being assigned after the gather by the pure domain over that tuple. Never use `as_completed`, never append inside a task.
2. **Clock.** Tasks receive `turn.now` and never call `clock_port`. One read per turn stays true (contracts `answer_query` P3, R2).
3. **Ids and audit.** No task mints an id or writes an audit row. Tool-call ids (story 1-5) are minted **before** the gather in fixed tool order. Audit rows are written **after** it, in the same order. Otherwise IR-04 leaks through `idgen_port` counters even though positions are correct.
4. **Failure (AD-12).** Ports return `Result`, and each thunk converts an unexpected exception to `Failure`. After the gather, the **first failure in argument order** is the one reported. Taking the first by completion order would make the error body nondeterministic. No evidence is emitted on any failure.
5. **Timeout.** The fan-out budget is `asyncio.timeout(budget)` around the gather. Cancellation reaches every child, and the dispatcher awaits them, so no orphan tasks. This is wall-time **infrastructure**. It stamps nothing and is not a domain time rule, so it is not a clock read. → `test-design.md` §6.3.5 rows *"One tool's fake advances the fake clock past its budget"* and *"A tool finishes exactly at its budget"* contradict the single-read rule, because measuring a tool on the fake clock needs two extra reads per turn. **Rewrite them** as: (a) a gate that never opens + `budget = 0` → `TimeoutError` → `PROVIDER_UNAVAILABLE` 503, deterministically and without sleeping; (b) cancellation check: every child is done and `-W error` shows no "Task was destroyed". Drop the exact-budget boundary row.
6. **Where the loop lives.** Keep the request path sync and the ports sync (OP-1..OP-15 unchanged). The application-ring `ParallelReads` helper runs `asyncio.run(gather(*(asyncio.to_thread(call) for call in calls)))` inside the worker thread. It imports only stdlib, so R3 holds. Constraint: a route that calls it must stay `def`, never `async def` (`asyncio.run` inside a running loop raises). Add a route-audit assertion for that. Rejected alternative: going async end to end means rewriting the per-session `threading` guard and the store and blocking the loop on sqlite3, for no latency gain on in-process fakes.

Branch reads that depend on each other stay sequential. Only independent reads fan out: policy-for-model, events-in-window, and catalog. `missing_policies` runs before the fan-out because it can end the turn.

---

## 3. Exactly-once dispatch with one SQLite writer (question 3)

**Principle (Winston):** *the guarantee is the conditional UPDATE's row count, not the lock.* The lock prevents connection-level interleaving (TG-I2-1). The compare-and-set makes exactly one confirm the winner. The unique indexes make a duplicate apply impossible to record as success.

**Decision D-3 — `confirm_and_dispatch` phases:**

| Phase | Holds writer? | Work |
|---|---|---|
| 1. Read and check | no | One `ClockRead`. Load the proposal. Evaluate in the order fixed by D-5 (§5): P1 → P5 → P2 → P4 → P3 (re-execute the stored selector through the provider). |
| 2. Claim | **yes**, one `BEGIN IMMEDIATE` | `UPDATE … SET state='confirmed' … WHERE proposal_id=? AND state='dry_run' AND gate_token=?`, then `UPDATE … SET state='dispatched' WHERE … AND state='confirmed'`, plus the dispatch audit row. Commit. `rowcount == 0` on the first UPDATE means another confirm won: **re-read and re-enter P5** (identical → persisted state; differing → 409). Do not map 0 rows straight to an error code; the `C5` comment in the migration says it does, and that conflicts with P5. Correct the comment. |
| 3. Execute | **no** | Call the executor port with the frozen `ExecutorRequest`. Never hold the writer across this call: a 5 s executor would stall all 50 operators. |
| 4. Record | **yes** | `UPDATE … WHERE state='dispatched'` to `executed`/`failed` plus the `actor = executor` audit row. `ux_audit_executor_apply` rejects a second apply, which surfaces as `EXECUTOR_DUPLICATE_APPLY`, never a second success (AD-15). |

- `confirmed` and `dispatched` commit in **one** transaction, so no other request can observe a durable `confirmed`. P5's "a prior dispatch exists" is defined as `state ∈ {confirmed, dispatched, executed, failed, superseded}` to cover crash leftovers. Add this wording to contracts P5.
- Timeout without sleeping: the dispatcher compares the executor result's `timestamp` (the executor's own clock read, E16) against the phase-1 read. A difference above 5 s means `failed` + `EXECUTOR_UNAVAILABLE`, and the late result is recorded without a state change (P6). In production the HTTP client's wall timeout does the same.
- Defense in depth, already in the schema: the `trg_proposals_state_machine` trigger, `gate_token UNIQUE`, `ux_audit_executor_apply`. Each one gets its own red test.
- **Test-design fix (§6.3.3):** in the 50-way replay, the 49 losers may observe `dispatched` *or* `executed`, depending on whether they read before or after phase 4. Assert `state ∈ {dispatched, executed}` and Exec = 1. Do not assert byte-equality with the winner's body.

---

## 4. The concurrency test seam (question 4)

**Decision D-4:** concurrency tests run the **real composition root** (`build_container`) on a **file** database. The only substitutes are outbound adapters, registered through `Container.register_port` (or an `overrides=` argument added to `build_container`). Nothing above the ports is faked. There are four controls:

| Control | What it pins | Tool |
|---|---|---|
| Time | TTL, idle expiry, executor timeout | `SimClock.advance/set` (exists). The fake executor stamps its result from the clock it is given and can be told to stamp `t + 6 s`. |
| Tool completion order (IR-04) | which read finishes first | **`CompletionScript`**: gated fakes at the policy/events/catalog ports, released in a scripted permutation. To make the order deterministic at the loop level (not just at the thread level), `ParallelReads` reports each completion to a `ToolObserver` outbound port (no-op by default; it doubles as the metrics sink of T-6/P0-G5). The script opens the next gate only from that callback. No sleeps, no "probably ordered". |
| Request concurrency (IR-02, IR-05) | N callers in the same instant | `threading.Barrier(N)` over the real use cases (`SessionUseCases`, the destructive use cases), as `tests/integration/test_sessions_concurrency.py` already does. HTTP adds nothing to exactly-once, so one API test covers the status mapping and the hammer stays at the use-case seam. |
| Failure injection | provider down, mid-transaction failure | `SimClock.fail()`, fake ports returning `Failure`, and for the IR-05 cross-store case a store-level fault hook that raises between two statements of one transaction. |

- **Real time appears only in k6**, as a measurement. It runs against **one** uvicorn worker: with `--workers > 1` each process has its own `SimIdGen` counters, `SimClock` and connection, which produces duplicate ids and real `database is locked`. Bootstrap logs the worker assumption, and the k6 README pins `--workers 1`.
- **Test-design fix (§6.3.5 k6 row):** `/copilot/query` creates a session per request (`src/adapters/inbound/copilot.py`). Remove "one session per VU from `setup()`": 1 000 requests produce 1 000 sessions, each with 1 turn, and that is what the IR-05 hammer asserts.

---

## 5. TG-I2-1 and the open points (question 5)

### TG-I2-1 — shared SQLite connection (IR-05) → resolved, D-6

**Observed:** `connection.py:14` opens one `check_same_thread=False` connection. `SqliteSessionStore` serializes on its **own** `RLock` and commits whenever `in_transaction` is true. Python's default isolation level opens an implicit `BEGIN` before DML. Once a second store with a second lock exists, store B's `commit()` commits store A's half-written turn. This is exactly the IR-05 interleaving.

**Decision D-6:**
1. Add a `SqliteWriter` (in `src/adapters/outbound/db/`) that owns the **one** connection and the **one** lock. It is AD-10's "single writer for all Module-12 persistence". Every store (session, proposal, audit, tool-call) receives it and never the raw connection. No store has its own lock.
2. Open with `isolation_level=None` and use explicit `writer.transaction()` = `BEGIN IMMEDIATE … COMMIT | ROLLBACK`, so no implicit transaction spans two stores. Reads go through `writer.read()` under the same lock, because one connection cannot serve two threads at once.
3. Set `PRAGMA foreign_keys = ON` and `PRAGMA busy_timeout = 5000` once at open. WAL is already applied by the migration. With one in-process connection, `busy_timeout` only protects against external readers (sqlite3 CLI, evidence scripts). It is cheap, so keep it.
4. Migrate `SqliteSessionStore` first, with no behaviour change: its existing tests are the safety net. This happens **before 1-5/2-2**, not inside 1-6.
5. Red tests: (a) the §6.3.5 cross-store interleaving case; (b) a static test that no module other than `SqliteWriter` calls `.commit()`, `.rollback()` or `sqlite3.connect`.

### OP-I2-1 — order of P5 vs P2 → resolved, D-5

Evaluation order for `confirm_and_dispatch`, to be written into contracts §1:
**P1** (exists, 404) → **P5** (if state ≠ `dry_run`: identical pair → persisted state; differing → 409 `CONFIRMATION_CONFLICT`) → **P2** (token mismatch 403, then TTL `<=` → 409 `CONFIRMATION_STALE`) → **P4** (empty set 409) → **P3** (re-validate: delta 409 / provider down 503) → claim → **P6**.
Consequences: an identical replay of a dispatched proposal after TTL returns the persisted state (the §6.3.3 row at `t0 + 120 s` stands). P4 runs before P3 so an empty proposal never needs the provider. The response to a replay holds only what the token holder already received, so returning it after expiry discloses nothing new.

### OP-I2-2 — `ws-02/05/08` vs `ws-gpu-02/05/08` → resolved

Assert the real ids. The dry-run summary string uses node ids from the records (AD-7, AD-8). Record the deviation in `walkthrough-impl2.md` next to the other "assert the real ids" adaptations. No contract change.

### OP-I2-3 — NFR-6 at ≥ 5 vs Annex 50 → decided (Q3, 2026-11-06)

**NFR-6 stays unchanged.** The budget of 50 operators at p95 < 800 ms, measured with the fake prose adapter, goes into story 1-6's acceptance criteria (both copies of `epics.md`). 50 satisfies "≥ 5", so there is no contradiction. The real gap is the **latency** budget. contracts `answer_query` holds p95 ≤ 3000 ms at 5 sessions with the real LLM. Annex 12.5 wants p95 < 800 ms at 50 VUs with the deterministic prose fake. These are two lanes, and the walkthrough must keep them apart (§6.3.5 measurement note).

---

## 6. Required edits (no code; all before the first Impl-2 commit)

| # | File | Edit | From |
|---|---|---|---|
| E-1 | `test/test-design.md` §6.3.1 | Refusal-only path (`/copilot/query`): 0 proposal rows, 0 tokens (replaces "`state = refused`"). `/copilot/chat`: exactly 1 `dry_run` row + 1 token per request, `snapshot_timestamp` = turn instant, Exec = 0, Δsim = 0. The "same body through both routes" row becomes "same refusal turn; chat adds the dry-run". The 2-way chat race gives 2 rows and 2 distinct tokens. | D-1, Q1 |
| E-2 | `test/test-design.md` §6.3.5 | Replace the two fake-clock tool-budget rows (D-2.5). Remove "one session per VU from `setup()`". Add "first failure in argument order" and "tool-call ids minted before the gather" cases. | D-2, D-4 |
| E-3 | `test/test-design.md` §6.3.3 | 50-way losers: assert `state ∈ {dispatched, executed}`, not body equality. | D-3 |
| E-4 | `test/test-design.md` §6.6 | Close TG-I2-1, OP-I2-1 and OP-I2-2 with links to this review. TG-I2-2 becomes `CompletionScript` + `ToolObserver`. | §4, §5 |
| E-5 | `contracts.md` §1 `confirm_and_dispatch` | State the evaluation order (D-5) and the P5 definition of "prior dispatch exists" (D-3). | D-3, D-5 |
| E-6 | `contracts.md` §0.3 | `JobRecord.node: EntityKey \| null` (with the fixture commit). | F-2 |
| E-7 | `migrations/001…sql` C5 comment | 0 rows → re-read and re-enter P5. Comment only, so no schema migration is needed. | D-3 |
| E-8 | `docs/ai-decision-log.md` | I2-01..I2-06 for D-1..D-6, plus I2-07..I2-09 for Q1..Q3. | — |
| E-9 | `contracts.md` §1 `propose_destructive_action` P3/Q1 | Job actions accept a `group` target. Selector `jobs_port.select({group_id, status: running})`. | Q2 |
| E-10 | `fixtures/estate/groups.json`, `jobs.json` | `group#CS-101` + 3 running jobs on ws-gpu-02/05/08 (nullable `node`, E-6). | Q2 |
| E-11 | `planning/epics.md` + `_bmad-output/planning-artifacts/epics.md` story 1-6 | AC: 50 operators, p95 < 800 ms on `/copilot/query`, fake prose adapter. NFR-6 unchanged. Keep both copies identical. | Q3 |
| E-12 | `test/test-design.md` §6.3.2, §6.6 | The Annex dry-run case targets `group#CS-101` (3 items). Add the two Q2 red tests. Close OP-I2-3. | Q2, Q3 |
| E-13 | `walkthrough-impl2.md` | List the CS-101 group target and the separate 800 ms lane as Annex adaptations. | Q2, Q3 |

## 7. Questions for the product owner

- **Q1 (F-1) — DECIDED 2026-11-06:** one reply. Refusal + dry-run impact summary + single-use 60 s gate token. Nothing executes, and dispatch happens only through the separate confirm request. See F-1.
- **Q2 (F-2) — DECIDED 2026-11-06:** `group#CS-101`, P3 accepts a group target for job actions, "active" means `running`. Exactly 3 jobs on ws-gpu-02/05/08. group-2, group-4 and S1/S2 untouched. Recorded as an Annex adaptation. See F-2.
- **Q3 (OP-I2-3) — DECIDED 2026-11-06:** NFR-6 unchanged. 50 operators at p95 < 800 ms (fake prose adapter) goes in story 1-6's ACs.

No decision is pending.
