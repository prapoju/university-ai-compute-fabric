---
baseline_commit: ec4da8a8cc592d338aaf44fa43fdf77478c42c86
---

# Story 1.2: Console shell, session store and conversational intake

Status: review

<!-- Impl-1 scope note: the canonical story title says "console shell", but the course track is Python/FastAPI
     (no React console). This story delivers the server side of the console: the session REST API, the
     persistent session store and rule-based conversational intake. See Decision D1. -->

## Story

As Nadia,
I want to open an operations session, ask a question and have it routed to one registered intent (or to a clarification),
so that my complaint becomes a tracked conversational turn instead of a dead-end text box.

## Acceptance Criteria

Source: `planning/epics.md` → Story 1.2 (canonical). Requirements: FR-01, FR-02, AD-5, NFR-6 (UX-DR2/DR4 apply to the console, which is out of scope, see D1).

1. **Session lifecycle.** Given the FastAPI service, when I `POST /api/v1/sessions`, submit a query with `POST /api/v1/sessions/{sid}/queries`, read it with `GET /api/v1/sessions/{sid}` and clear it with `DELETE /api/v1/sessions/{sid}`, then a session is stored server-side with its `context` (`resolved_entities`, `prior_intents`, `active_answer_ids`) retained across turns; `DELETE` clears the context and marks the session `reset`; and a follow-up reference resolves from prior-turn context first (FR-02, scoped in D5).
2. **Exact routing.** 100% of the S1 query `why was alex denied deepseek-coder` (and its Annex variant `Why was student alex denied access to deepseek-coder?`) route to the `diagnose_access_denial` intent; 100% of out-of-domain queries (`what's the weather?`) return the clarification response and are **never** force-routed; a compound query containing a destructive verb routes to clarification (FR-01).
3. **Answer envelope.** Each turn returns an `AnswerEnvelope` whose `Answer` carries the fixed `answer_chain` starting with `observation` (a contiguous prefix of the six stages, never skipped); the diagnosis content is observation-only until story 1.3. Canonical outcomes (clarification) are HTTP 200 with an `ErrorBody` whose `message` is the canonical literal (D58).
4. **Input limits.** The query is trimmed once; empty → `VALIDATION_EMPTY_QUERY`, over 1,000 characters → `VALIDATION_QUERY_TOO_LONG` (both HTTP 400); exactly 1,000 is accepted. A rejected call creates no answer and leaves the session context unchanged (Q-fail).
5. **Session states.** Absent session → `SESSION_NOT_FOUND` (404); a `reset` or `expired` session, or one idle for more than 30 minutes, → `SESSION_EXPIRED` (410) and the expiry is persisted idempotently; exactly 30 minutes idle is still active.
6. **Concurrency (NFR-6).** The session store serves ≥ 5 concurrent operator sessions at ≥ 50 queries/hour with no cross-session context leakage and no degradation; queries within one session are serialized.

### BDD scenarios (drive the tests, Given/When/Then)

```gherkin
Scenario: Create a session
  Given the clock is frozen at 2026-10-16T15:00:00.000Z
  When I POST /api/v1/sessions with operator_role "role-operations"
  Then the response is 201 with status "active", an id matching ^sess-[0-9a-f]{16}$ and created_at equal to the clock instant
  And context is {resolved_entities: [], prior_intents: [], active_answer_ids: []}
  And a malformed role ("admin") returns 400 VALIDATION_MALFORMED_BODY and nothing is stored

Scenario: Route the S1 query to the access-denial intent
  Given an active session
  When I submit "why was alex denied deepseek-coder"
  Then I get 200 with one Answer whose intent is "diagnose_access_denial" and answer_chain ["observation"]
  And the session context lists that intent in prior_intents and the answer id in active_answer_ids
  And submitting the same text again creates a second answer with a new id (not idempotent)

Scenario: Out-of-domain and compound-destructive queries are clarified, never routed
  Given an active session
  When I submit "what's the weather?"
  Then I get 200 with ErrorBody code CLARIFICATION_REQUIRED and message "Clarification required: no registered intent matches this query."
  And when I submit "why was alex denied deepseek-coder and delete all his jobs" the response is a clarification about mixing a diagnosis with a destructive action

Scenario: Query validation
  When I submit "", "   ", or a 1001-character query
  Then I get 400 VALIDATION_EMPTY_QUERY / VALIDATION_EMPTY_QUERY / VALIDATION_QUERY_TOO_LONG and no answer is stored
  And a 1000-character query is accepted
  And a body containing an extra "session_id" field is 400 VALIDATION_MALFORMED_BODY

Scenario: Session states and idle expiry
  Given a session whose last activity was 31 minutes ago
  When I submit a query
  Then I get 410 SESSION_EXPIRED and GET shows status "expired"
  And a session idle for exactly 30 minutes still accepts the query
  And an unknown id is 404 SESSION_NOT_FOUND and a malformed id is 400

Scenario: Read and reset
  Given a session with two turns
  When I GET it then I see the context and both turns in order, and the read changes nothing
  And DELETE returns 204, empties the context, sets status "reset", and a second DELETE is also 204
  And submitting to the reset session is 410 SESSION_EXPIRED

Scenario: Follow-up resolves from session context
  Given a session whose last routed intent is diagnose_access_denial
  When I submit "and what about mateo?"
  Then it is routed to diagnose_access_denial using the session context
  And in a fresh session the same text is a clarification ("there is no earlier topic in this session to follow up on")

Scenario: Concurrent sessions do not leak
  Given 6 sessions each receiving 20 queries from parallel threads
  Then every session holds exactly its own 20 turns and ids, with unique ids across sessions

Scenario: Persistence survives a restart
  Given a file database with one session and two turns
  When the service container is rebuilt on the same file
  Then GET returns the same session and turns, and newly generated ids never collide with stored ones
```

## Tasks / Subtasks

Full Ceremony: test first, then code, per subtask. Commit per numbered task (conventional commits; **no co-author trailer**). Write files with the file-writing tool (not shell here-docs). Test every persistence path on a **file** database as well as `:memory:` (lesson from story 1.1, AD-12).

- [x] **Task 1: Domain building blocks (pure)** (AC: 2, 3, 4, 5) → `feat(story-1.2): domain rules for sessions, intents and errors`
  - [x] 1.1 `src/domain/canonical_strings.py`: single owner of every canonical literal (`S_ENF`, `S_CNC`, `S_PUA`, `S_ARF`, `S_RBX`, `S_CAP` byte-exact from `contracts.md` section 0 / ARCHITECTURE "Consistency Conventions", plus `Clarification required: {reason}.` and the three reason strings in this story). `src/adapters/inbound/errors.py` imports `S_PUA` from here (remove its local copy).
  - [x] 1.2 `src/domain/error_catalog.py`: the full section 4 catalog as data: `ErrorCode -> (http_status, retryable, message_template)`; `Failure` gains an optional `message` (backward compatible). A test asserts the catalog covers exactly the `ErrorCode` literal in `src/dto.py` and pins the statuses used here (400/404/410/503).
  - [x] 1.3 `src/domain/session_rules.py`: `MAX_QUERY_CHARS = 1000`, `IDLE_LIMIT = 30 min` (D51), `normalise_query(text) -> Result[str]` (strip once, empty/too-long failures with the contract messages `Query must contain between 1 and 1000 characters; received 0.` / `Query exceeds 1000 characters; received {n}.`), `is_idle_expired(last_activity, now)` (strictly `>` 30 min), `empty_context()`.
  - [x] 1.4 `src/domain/intent.py`: deterministic rule-based classifier (AD-11, no LLM): an `IntentRule` registry (data: `intent_code`, `matched_rule_id`, patterns) with one rule today (`diagnose_access_denial`), destructive-verb detection, and `classify(query, prior_intents) -> Routed | Clarify(reason)`. Compound destructive → `Clarify`; no match → `Clarify`; follow-up marker (`and what about …`, `how about …`) inherits the most recent **registered** intent from `prior_intents`, else clarifies. New intents (stories 3.1, 4.1, 3.4) are added by registering rules only.
- [x] **Task 2: Ports** (AC: 1, 5, 6) → `feat(story-1.2): session store, idgen and use-case ports`
  - [x] 2.1 `src/ports/outbound/idgen.py`: `IdGenPort.new_id(kind: IdKind) -> Result[IdString]` exactly as contracts OP-13 (bad kind → `VALIDATION_BAD_ID_KIND`).
  - [x] 2.2 `src/ports/outbound/session_store.py`: `SessionStorePort` for the **Module-12-owned** store (this is not an estate port, so AD-1's query-only rule does not apply; it is an internal port, see D6): `create`, `get -> StoredSession | None` (session DTO + `last_turn_at`), `list_turns`, `append_turn` (answer + new context + timestamps, atomic), `mark_expired` (idempotent), `reset` (idempotent), `highest_counters` (for id seeding). Every method returns `Result` (AD-12). Update `tests/unit/test_ports_query_only.py` so it distinguishes the 12 read-only provider ports from these two (owned-store/generator ports have their own expected method sets).
  - [x] 2.3 `src/ports/inbound/session_use_cases.py`: the use-case interface the routers call: `create_session`, `submit_query`, `get_session`, `reset_session`, returning `Result` of DTOs (`SessionDTO`, `AnswerEnvelopeDTO | ErrorBody`, `GetSessionResponse`).
- [x] **Task 3: Outbound adapters** (AC: 1, 6) → `feat(story-1.2): sqlite session store and seeded id generator`
  - [x] 3.1 `src/adapters/outbound/db/session_store.py`: SQLite implementation over the **existing** `sessions` and `answers` tables of the migrated schema (no new tables or columns: `turns` are `answers` rows ordered by `created_at, answer_id`; D7). One lock serializes all statements on the shared connection; `append_turn` is one transaction; every `sqlite3.Error` becomes `Failure("PROVIDER_UNAVAILABLE")`. Respect the CHECK constraints (id lengths, `Z` instants, JSON arrays).
  - [x] 3.2 `src/adapters/outbound/sim/idgen_adapter.py`: seeded, monotonic per-kind generator, thread-safe, formats exactly per `IdString` (`sess-`/`ans-` + 16 hex, ...); `from_counters(highest)` seeds it above every stored id so a restart never reissues one (E43). No `uuid`/`random` anywhere (R2).
  - [x] 3.3 Tests on both `:memory:` and a **file** database: round-trips, atomic turn append (a failure leaves no partial answer or context), idempotent `mark_expired`/`reset`, CHECK violations surface as `Failure`, restart persistence, id seeding after restart.
- [x] **Task 4: Application service** (AC: 1-5) → `feat(story-1.2): session service and intake pipeline`
  - [x] 4.1 `src/application/session_service.py` implements the use-case port: reads the clock **once per call**, enforces the contract preconditions in order (query validation, session exists, status/idle), writes through the store, appends exactly one `prior_intents` and one `active_answer_ids` entry **per returned Answer** (contracts `answer_query` Q2), never changes `resolved_entities` here (resolver is story 1.3), and serializes turns per `session_id` (per-session lock).
  - [x] 4.2 `src/application/pipeline.py`: the walking-skeleton seam: classify → look up an `IntentHandler` registered for the routed intent → if none, return the observation-only Answer (`answer_chain ["observation"]`, no claims/evidence). Story 1.3 registers `diagnose_access_denial`; 3.1 and 4.1 register theirs. Canonical outcomes (clarification) are persisted as an Answer with `canonical="CLARIFICATION"` and `intent="clarification"` and returned on the wire as the 200 `ErrorBody` (D3).
  - [x] 4.3 Tests for every BDD scenario above at service level with the real SQLite store (frozen `SimClock`, advanced for expiry).
- [x] **Task 5: Inbound adapter (REST)** (AC: 1-5) → `feat(story-1.2): session REST endpoints`
  - [x] 5.1 `src/adapters/inbound/sessions.py`: the four routes with the exact paths, parameters, bodies and status codes of `openapi.yaml` (201/200/200/204; 400/404/410/503). Path `{sid}` validated with the `SessionId` pattern (400 on violation). `CreateSessionRequest` is the DTO; the query body uses a local model `{query_text: str}` with `extra="forbid"` so the empty/too-long codes can be emitted (the DTO `QueryText` would reject them as generic 400, D4). `Failure` → `ErrorBody` via the error catalog; canonical clarification → 200 `ErrorBody`. No domain logic in the router.
  - [x] 5.2 `tests/api/test_contract_routes.py`: add the four operations to `SERVED_IN_THIS_STORY`; the exact-route and mutating-route audits must stay green (the session routes are already in the allow-list).
  - [x] 5.3 API tests: every response body validated against its DTO (`SessionDTO`, `GetSessionResponse`, `SubmitQueryResponse`, `ErrorBody`, all `extra="forbid"`), every status code of the scenarios, structured JSON on every error (no `{"detail"}`).
- [x] **Task 6: Composition root** (AC: 6) → `feat(story-1.2): wire sessions into the container`
  - [x] 6.1 `src/bootstrap.py`: register `SessionStorePort`, `IdGenPort` (seeded from the store) and the use-case service; if the database is unavailable the container still builds and readiness reports it (existing behaviour); add a `sessions` readiness check; routes return 503 `PROVIDER_UNAVAILABLE` when the store is down.
  - [x] 6.2 Tests: wiring, 503 behaviour with a closed/unavailable DB, readiness.
- [x] **Task 7: NFR-6, determinism and DoD** (AC: 6) → `test(story-1.2): concurrency and persistence`
  - [x] 7.1 Concurrency test (6 sessions x 20 queries in parallel threads against one container; no leakage, unique ids, per-operation latency far below the 50 ms/3 s budgets on fixtures) and the restart-persistence test on a file database.
  - [x] 7.2 Determinism: two fresh containers with the same clock produce identical ids and answers for the same script.
  - [x] 7.3 README: document the session API with a `curl` walkthrough; `ruff check src tests`, full `pytest` (0 skipped), Docker `up --build` smoke (`POST /api/v1/sessions`, query, GET, DELETE).
  - [x] 7.4 Update `docs/ai-decision-log.md`; promote the story status in both `sprint-status.yaml` copies.

### Review Findings

Code review 2026-10-25 (Blind Hunter + Edge Case Hunter + Acceptance Auditor; scope: `src/` without `dto.py`, `tests/`, `README.md`; ~3,500 diff lines). Severities were assigned after reading the code and reproducing the cases. The Acceptance Auditor found **no violation of AC 1-6**; the findings below are robustness and precision gaps.

**Decision needed** (1 raised, resolved by the user on 2026-10-25)

- [x] [Review][Decision] (medium, RESOLVED by the user: keep the contract-literal behaviour; recorded as assumption 6 in the decision log, no code change) A query sent to a *reset* session is answered 410 and persisted as `status = expired`, so `GET` afterwards shows `expired` (not `reset`), the message says "expired after 30 minutes idle" for a session that was deleted on purpose, and a later `DELETE` flips it back to `reset`. All three reviewers flagged it; contracts.md `answer_query` P2 literally says reset/expired/idle sessions are "persisted as `status == expired`", so the code follows the contract. Choose between keeping the contract-literal behaviour and preserving the explicit `reset` state. [src/application/session_service.py:106, src/adapters/outbound/db/session_store.py:184]

**Patch**

- [x] [Review][Patch] (medium) Intent rules force-route out-of-domain queries (reproduced): `why was job 8823 rejected?`, `why was job 8823 blocked?`, `why was my pull request rejected` and `why does the report not cover access logs` all route to `diagnose_access_denial` because pattern 1 needs only "why" + a verb and pattern 2 accepts a bare "not". Require an object after the verb, drop `rejected`/`forbidden`, restrict pattern 2 to can't/cannot/unable to/not allowed to, and extend the out-of-domain corpus [src/domain/intent.py:46, tests/unit/test_intent.py]
- [x] [Review][Patch] (medium) The destructive-verb guard misses causative/passive requests (reproduced): `why was alex denied deepseek-coder and have his jobs deleted` / `get his jobs cancelled` are routed as a pure diagnosis and the destructive request is silently dropped (AD-5). Detect causative markers (have/get/make/let/please/should/must) followed by a past participle while still letting plain reports ("cordoned", "cancelled") through [src/domain/intent.py:60]
- [x] [Review][Patch] (medium) The clock is read before the per-session lock (and before the session lookup): two concurrent turns can commit out of order (an earlier `now` written later, `last_turn_at` moving backwards, `GET` turns listed in a different order from `active_answer_ids`), and a clock failure on an unknown session returns 503 instead of 404. Take the guard first, look the session up, then read the clock once, for `submit_query` and `reset_session` [src/application/session_service.py:94, src/application/session_service.py:171]
- [x] [Review][Patch] (medium) A stored `created_at`/`last_turn_at` that passes the table GLOB but is not a real instant (`2026-13-45...`) makes `submit_query` raise a raw `ValueError` (reproduced) instead of a typed failure [src/application/session_service.py:106]
- [x] [Review][Patch] (medium) A query containing a NUL character (or a lone surrogate) passes `normalise_query` and then violates the table CHECK, so a client input error comes back as a retryable 503 (reproduced). Reject it in the domain as `VALIDATION_MALFORMED_BODY` [src/domain/session_rules.py:24]
- [x] [Review][Patch] (low) `/readyz` runs its `migrations` query on the shared connection outside the store lock; expose it as a locked store method and use that [src/bootstrap.py:107, src/adapters/outbound/db/session_store.py]
- [x] [Review][Patch] (low) `GET /sessions/{sid}` reads the session and its turns as two unsynchronised statements, so a concurrent turn can make `context` and `turns` disagree; read both under the session guard [src/application/session_service.py:149]
- [x] [Review][Patch] (low) A failed `mark_expired` write hides the 410 the service already knows applies; return `SESSION_EXPIRED` anyway and log the failed write-back [src/application/session_service.py:106]
- [x] [Review][Patch] (low) Duplicate entities returned by one handler are persisted twice in `resolved_entities`; de-duplicate (Q2 superset rule) [src/application/session_service.py:130]
- [x] [Review][Patch] (low) Incomplete apostrophe normalisation (only U+2019): treat the usual apostrophe lookalikes the same [src/domain/intent.py:70]
- [x] [Review][Patch] (low) README says sessions "survive restarts" while the default database is `:memory:`; say it holds for a file database (what Docker uses) and mark the sample ids as illustrative [README.md:56]

**Deferred**

- [x] [Review][Defer] `append_turn` refuses answers with claims/evidence as a retryable 503 [src/adapters/outbound/db/session_store.py:144] - deferred to story 1.3, which must persist claims/evidence (and replace this guard) before any diagnosis handler is registered; recorded in the story notes
- [x] [Review][Defer] The session context (`prior_intents`, `active_answer_ids`) grows with every turn [src/application/session_service.py:130] - deferred: prototype-scale sessions expire after 30 idle minutes; revisit with the retention decision (OQ-13)
- [x] [Review][Defer] Id counters are seeded once, only for `session` and `answer`, and assume one process [src/adapters/outbound/db/session_store.py:205] - deferred: other kinds appear with later stories (extend `highest_counters` then); a multi-process deployment is out of scope (C-5)
- [x] [Review][Defer] Every `sqlite3.Error` is a retryable 503, including permanent ones such as a duplicate id [src/adapters/outbound/db/session_store.py] - deferred: the error catalog has no code for permanent storage faults; revisit with the audit stories
- [x] [Review][Defer] The connection's `isolation_level` is not pinned explicitly [src/adapters/outbound/db/connection.py] - deferred: the default (implicit transactions) is what the store relies on and the atomicity tests cover it

**Dismissed (11):** `GET` on an idle-but-unmarked session reports `active` (contracts.md `get_session` has no time dependency; the next query returns 410 and persists it); the `SESSION_EXPIRED` template text for reset sessions (catalog literal; tied to the decision above); benign words such as `remove`/`kill` in a diagnosis query trigger a clarification (deliberate safe-over-precise trade-off for AD-5); path-parameter 400 vs 404 (contract P1 says a malformed parameter is 400); `operator_role` validated in both the DTO and the service (defence in depth); `failure_response` may echo `observed` for 4xx or hit an unknown code (every `Failure` code is validated against the catalog and a test pins full coverage); the route audit relies on FastAPI's private `original_router` (cross-checked against the generated schema, accepted); regex backtracking on 1000 characters (bounded); length measured after trimming (contract: trim once); the swallowed `PRAGMA foreign_keys` error (a dead connection fails on the first real call) and `highest_counters` loading every id (10k cap, corrupt rows make sessions safely unavailable); `R_MULTIPLE_INTENTS` is unreachable with one rule (unit-tested with custom rules).

## Dev Notes

### Decisions and discrepancies found while creating this story (read first)

- **D1 - No React console.** The canonical story files list `console/src/App.tsx`, `AnswerChain.tsx`, a skeleton and a 1,000-character composer (UX-DR2/DR4). The course track is Python/FastAPI and rubric items concern the API, so the console is out of scope; the 1,000-character cap is enforced server-side (AC 4) and the chain envelope is the `answer_chain` field (AC 3). Record this in the walkthrough.
- **D2 - No audit rows yet.** `contracts.md` section 2 Q3 asks for a `toolcall.*` audit row per call, but the Audit Writer and the audit log are story 1.5 (outside the Impl-1 scope). Do **not** write to `tool_calls`/`audit_records`; leave the composition root as the single place where ports are wired so wrapping them later needs no edits. NFR-8 "100% of tool calls audited" is therefore unmet until 1.5; say so in the walkthrough.
- **D3 - Canonical wire shape.** The route returns a clarification as HTTP 200 with an `ErrorBody` (`code="CLARIFICATION_REQUIRED"`, `message="Clarification required: {reason}."`) per openapi/D58, **and** the turn is stored as an `answers` row (`canonical="CLARIFICATION"`, `intent="clarification"`, `answer_chain=["observation"]`) so `GET` shows it among the turns. `CanonicalCode` (`CLARIFICATION`) and `ErrorCode` (`CLARIFICATION_REQUIRED`) differ by name; the contract text says the body has an `error_code` field but `dto.py`/openapi use `code` - follow the DTO.
- **D4 - Query validation vs DTO.** `SubmitQueryRequest.query_text` is a `QueryText` that would turn empty/over-long input into a generic validation error, but the contract demands `VALIDATION_EMPTY_QUERY` / `VALIDATION_QUERY_TOO_LONG` with specific messages. The router therefore accepts `query_text: str` and the domain validates. The trim happens once and the stored `Answer.query` is the trimmed text.
- **D5 - FR-02 follow-ups, scoped.** The entity resolver is story 1.3 and general follow-up entity references are story 3.4, so this story implements the session-context mechanism for the **intent** only: `and what about mateo?` inherits the last registered intent from `prior_intents`, otherwise it clarifies. `resolved_entities` is stored and returned but only 1.3 populates it.
- **D6 - Two new outbound ports.** `IdGenPort` is contract OP-13. `SessionStorePort` is an internal port for the Module-12-owned store (the contracts do not define one; ports-and-adapters.md places persistence under `adapters/db` behind an outbound port). Neither is a provider port, so the "exactly 12 query-only ports" test is split in two groups.
- **D7 - No `turns` table.** The epic mentions SQL `turns`, but the migrated schema has none; `turns` in `GET /sessions/{sid}` are the session's `answers` rows (`GetSessionResponse.turns: list[AnswerDTO]`). Do not invent tables or columns. `create_session` returns `SessionDTO` (no `turns`); only `GET` returns turns.
- **D8 - Sessions are created explicitly.** The epic says "a session is created on first query", but the contract and openapi create sessions only with `POST /sessions`; a query for an unknown session is 404. After `DELETE`, a query to that session is 410 (contract), so a client starts a new session.
- **D9 - ATDD.** `test/atdd/...::test_create_session_*`, `test_submit_query_*`, `test_get_session_*`, `test_reset_session_*` exercise the in-process `CopilotInboundPort` stub (and expect audit events); they stay red by design. This story's evidence is the new unit/API tests.
- **D10 - `reset` keeps the turns.** `reset_session` clears `context` and sets `status="reset"`; it does not delete answers (contracts Q2 says nothing else changes).

### Architecture compliance (binding)

- **AD-5:** session context never authorizes anything; no destructive path exists in this story and a destructive verb inside a compound query routes to clarification. **AD-11:** routing depends only on the rule registry; the query text is data, never control; no LLM. **AD-2/DP-5:** time only through `clock_port` (one read per request); ids only through `IdGenPort`; the pure layers import no `time`/`datetime.now`/`uuid`/`random`. **AD-1:** no estate access in this story, only Module-12 stores. **AD-12:** every store call returns a typed `Result`; a store failure is 503 `PROVIDER_UNAVAILABLE`, never a stack trace.
- **R1/R3:** `src/domain`, `src/ports`, `src/application` import no `fastapi`, `sqlite3`, adapters, randomness or wall clock (the AST audit and the ruff TID251 rule enforce it); only `src/bootstrap.py` wires adapters. **R4:** ports and use cases exchange DTOs from `src/dto.py` and primitives.
- **Contracts to match exactly:** contracts.md section 2 (`create_session`, `submit_query`, `get_session`, `reset_session`) and `answer_query` P1-P3/Q-fail; section 4 error catalog (statuses/messages); openapi.yaml `/api/v1/sessions*` (no extra endpoints, no extra status codes except the documented 400 for path/body validation).

### Previous story intelligence (story 1.1, reviewed and done)

- Write files with the file-writing tool; shell here-docs with apostrophes/backslashes failed or corrupted files twice.
- Tests on `:memory:` hid a real bug (WAL pragma on a file DB): run store tests on a file database too. SQLite schema files may have CRLF endings on Windows.
- Instants must be validated as real dates (`parse_instant`/`is_instant`), not by regex shape.
- Anything shared across threads (FastAPI thread pool) needs a lock; `SimClock` is already locked; readiness probes must not consume ids/reads.
- `Failure`/`Ok` typed results, `Container.register_port`, `SimProviders`, `tests/unit/conftest.py` fixtures (`providers`, `fixtures_copy`) and the architecture audit already exist: reuse them. The route audit (`tests/api/test_contract_routes.py`) lists the served operations explicitly and must be updated.
- Run `ruff format` only on files you create (it rewrites legacy harness files); legacy files are excluded in `pyproject.toml`.
- No co-author trailer in commits; commit per task.

### Files to create or touch

```
NEW  src/domain/{canonical_strings,error_catalog,session_rules,intent}.py
NEW  src/ports/outbound/{idgen,session_store}.py     src/ports/inbound/session_use_cases.py
NEW  src/application/{__init__,session_service,pipeline}.py
NEW  src/adapters/outbound/db/session_store.py       src/adapters/outbound/sim/idgen_adapter.py
NEW  src/adapters/inbound/sessions.py
EDIT src/domain/result.py (Failure.message)  src/adapters/inbound/{app,errors}.py  src/bootstrap.py
EDIT tests/unit/test_ports_query_only.py  tests/api/test_contract_routes.py  README.md
NEW  tests: unit (canonical_strings, error_catalog, session_rules, intent, idgen, session_service, pipeline),
     integration (session_store on memory + file), api (sessions), concurrency/persistence
```

Do **not** modify `planning/**`, `test/atdd/**`, `tests/support/**`, `src/dto.py` (verbatim contract copy), or the migrated schema.

### Testing standards

Pytest, 0 skipped, no network/wall clock/sleep, frozen `SimClock` (advance it for idle expiry). Every scenario asserts body semantics (codes, messages, ids, context), not only status codes. Boundary cases: 1000 vs 1001 chars, exactly 30 vs 31 idle minutes, whitespace-only query. Parametrized routing corpus: all S1 variants must route; out-of-domain corpus must clarify (target 100% on the stated sets, FR-01).

### Latest tech notes

No new dependency (FastAPI, Pydantic v2, stdlib `sqlite3`/`threading` only). FastAPI: `Path(pattern=...)` for `sid`, `status_code=201/204`, `Response(status_code=204)` with no body; request bodies as Pydantic models with `ConfigDict(extra="forbid")`. SQLite >= 3.35, WAL file databases need PRAGMAs outside transactions (already handled by the migration runner).

### References

- [Source: planning/epics.md#Story 1.2] - canonical story, ACs
- [Source: planning/detailed-design/contracts.md#2 Inbound Port Contracts; #1 answer_query; #4 Typed Error Catalog; #0.5 Session]
- [Source: planning/detailed-design/schemas/openapi.yaml] `/api/v1/sessions`, `/api/v1/sessions/{sid}/queries`, `/api/v1/sessions/{sid}`, components `Session`, `SessionWithTurns`, `SubmitQueryRequest`, `Response400/404/410/503`
- [Source: planning/detailed-design/schemas/dto.py] `SessionDTO`, `GetSessionResponse`, `AnswerDTO`, `AnswerEnvelopeDTO`, `ErrorBody`; [schemas/001_module12_copilot_schema.sql] `sessions`, `answers`
- [Source: planning/ARCHITECTURE.md#AD-4, #AD-5, #AD-11, #1.3 Intent, #1.7 Session; planning/prd.md FR-01, FR-02, NFR-6]
- [Source: planning/detailed-design/ports-and-adapters.md#1 Component Table, #2 R1-R4]
- [Source: story 1-1 file, Review Findings and Dev Agent Record] - lessons above

## Dev Agent Record

### Agent Model Used

claude-sonnet-5-5 (Claude Code, BMad `bmad-dev-story` ceremony)

### Debug Log References

- Baseline before any change: `pytest` -> 332 passed. Final: **593 passed, 0 skipped**, `ruff check src tests` clean, `test/ci/schema_check.py` -> GATE PASS.
- Task 5: the story-1.1 route audit stopped seeing routes after `include_router` (FastAPI 0.162 `_IncludedRouter`); the audit now flattens included routers and cross-checks `app.openapi()` (AD-15).
- Task 6: the extensibility test still asserted "exactly 12 ports"; it now asserts the twelve provider ports are present (the session ring adds ports).
- Scripted edits corrupted the README (here-doc line continuations) and left a junk line in a test; both fixed and logged (AD-16).
- Task 7: a throw-away mutation (per-session lock disabled) made the parallel-queries test fail on memory and file databases, proving it can fail (AD-17).
- Docker smoke (`docker compose up --build`): create -> S1 query (observation-only answer) -> out-of-domain clarification (200 ErrorBody) -> GET -> DELETE 204 -> query 410; after `docker compose restart` session 1 and its turns are still there and the next session gets id 2 (no collision); `/readyz` shows the new `sessions` check.

### Completion Notes List

- **AC1 (lifecycle):** four routes exactly as `openapi.yaml` declares them (`POST /api/v1/sessions` 201, `POST .../{sid}/queries` 200, `GET .../{sid}` 200, `DELETE .../{sid}` 204; 400/404/410/503). Sessions and turns persist in the existing `sessions`/`answers` tables; the context retains `prior_intents` and `active_answer_ids` (one entry per returned Answer) and `DELETE` clears it. Follow-ups resolve the *intent* from the session context (D5).
- **AC2 (routing):** deterministic rule registry (`src/domain/intent.py`, no LLM): 9 S1 variants route 100% to `diagnose_access_denial`; 8 out-of-domain queries are clarified, never force-routed; compound queries with a destructive verb (4 variants) and follow-ups mixing a destructive verb are clarified. New intents are added by registering a rule.
- **AC3 (envelope):** every turn carries `answer_chain = ["observation"]` (a contiguous prefix); clarifications are HTTP 200 `ErrorBody` with the literal `Clarification required: {reason}.` and are also stored as turns. `AnswerPipeline.register` is the seam where stories 1.3, 3.1 and 4.1 plug their diagnosers in.
- **AC4 (limits):** query trimmed once; empty -> `VALIDATION_EMPTY_QUERY`, > 1000 -> `VALIDATION_QUERY_TOO_LONG` with the contract messages; exactly 1000 accepted; a rejected call reads no clock, mints no id and leaves the session untouched; a body with `session_id` is 400.
- **AC5 (states):** absent 404, malformed id 400, reset/expired/idle > 30 min 410 with the expiry persisted idempotently; exactly 30 min idle still works and the timer counts from the last turn.
- **AC6 (NFR-6):** 6 parallel operator sessions x 20 queries on memory and file databases: no cross-session leakage, unique ids, p95 far below the contract budgets; one lock per session plus one store lock serialize writes.
- **Contract fidelity:** no endpoint or status beyond openapi/contracts (the documented 400 for path/body validation); the route audit lists the served operations explicitly and still passes.
- **Known scope limits (logged AD-14):** no React console (D1); no audit rows until story 1.5 (D2), so NFR-8 "every tool call audited" stays unmet in Impl-1; entity follow-ups come with 1.3/3.4; the ATDD stub tests for sessions stay red by design (D9).
- Commits: `feat(story-1.2)` x6, `docs(story-1.2)`; no co-author trailers.

### File List

New: `src/domain/{canonical_strings,error_catalog,session_rules,intent}.py`, `src/ports/outbound/{idgen,session_store}.py`, `src/ports/inbound/session_use_cases.py`,
`src/application/{__init__,pipeline,session_service,unavailable}.py`, `src/adapters/outbound/db/session_store.py`, `src/adapters/outbound/sim/idgen_adapter.py`,
`src/adapters/inbound/sessions.py`, `tests/api/{conftest,test_sessions,test_sessions_wiring}.py`, `tests/integration/{test_session_store,test_sessions_concurrency}.py`,
`tests/unit/{test_canonical_strings,test_error_catalog,test_idgen_adapter,test_intent,test_session_ports,test_session_rules,test_session_service}.py`.

Modified: `src/domain/result.py` (Failure.message), `src/adapters/inbound/{app,errors}.py`, `src/bootstrap.py`, `src/ports/inbound/__init__.py`, `src/ports/outbound/__init__.py`,
`tests/api/{test_contract_routes,test_health}.py`, `tests/unit/{test_bootstrap,test_ports_query_only,test_story_1_1_extensibility}.py`, `README.md`, `docs/ai-decision-log.md`,
`_bmad-output/implementation-artifacts/sprint-status.yaml` and its mirror `implementation-artifacts/sprint-status.yaml`.

### Change Log

| Date | Change |
|---|---|
| 2026-10-25 | Story created (`ready-for-dev`) with spec-conflict analysis (D1-D10). |
| 2026-10-25 | Domain rules: canonical strings, error catalog, session rules, intent classifier. |
| 2026-10-25 | Ports: id generator, session store, session use cases. |
| 2026-10-25 | SQLite session store and seeded id generator; session service and pipeline; REST routes; container wiring. |
| 2026-10-25 | NFR-6 concurrency and restart tests, README, decision log; DoD verified (593 passed, 0 skipped, ruff clean, Docker smoke); status -> `review`. |
