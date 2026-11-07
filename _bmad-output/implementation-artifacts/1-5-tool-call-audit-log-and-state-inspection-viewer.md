---
baseline_commit: a3f9161aabfc540cf386363f23cb43b98ef9e6d9
---

# Story 1.5: Tool-call audit log and state inspection viewer

Status: review

<!-- Impl-2 foundations story, Flow B (test-along): code and its tests ship in the same commit.
     Backend only. The Inspector (S-B) and Audit (S-C) console surfaces, including the `read-only`
     marker, belong to optional story 1.8. This story also lands review D-6 / log I2-06 (TG-I2-1):
     one SqliteWriter, one connection, one lock for every store. It must land before 1-6 and 2-2. -->

## Story

As Nadia,
I want an append-only record of every Copilot tool call and the ability to inspect raw state myself,
so that the answer is auditable and I can verify the evidence without trusting the prose.

## Acceptance Criteria

Source: `planning/epics.md` Story 1.5, backend part. Requirements: FR-11, FR-12, AD-10, AD-1, NFR-11. Contracts: `answer_query` Q3, `submit_query` Q3, `reset_session` Q3, `get_state_record`, `browse_state`, `get_audit_page`, §3 Q-port-3, §5 I14, I15, I18, I20, I22. Review: `reviews/review-impl2-shift-left.md` D-6 (log I2-06), D-2.3.

1. **One writer (TG-I2-1, IR-05).** `SqliteWriter` (`src/adapters/outbound/db/sqlite_writer.py`) owns the only `sqlite3` connection and the only lock. It opens with `isolation_level=None`, sets `PRAGMA foreign_keys = ON` and `PRAGMA busy_timeout = 5000` once, and runs every write in an explicit `BEGIN IMMEDIATE … COMMIT | ROLLBACK`. The session store and the audit store receive the writer and never the raw connection, and neither has its own lock. A static test proves that no module in `src/` other than `sqlite_writer.py` calls `.commit(`, `.rollback(` or `sqlite3.connect`. A cross-store test proves that when store A's transaction fails partway while store B commits, A's rows are absent and B's rows are present. Every existing session-store, evidence and session-service test passes unchanged in behaviour.
2. **Exactly one audit row per tool call (FR-11, I14).** For each `submit_query` turn that stores an `Answer` (diagnosis or canonical), the audit store holds exactly one `tool_calls` row and one `audit_records` row (`actor = copilot`) for `toolcall.answer_query`, plus one pair per provider-port read the turn performed, named `toolcall.<port>.<method>` (Q-port-3). Every row carries the session id, the session's `operator_role` and the turn's clock instant. The ids are minted from `idgen_port` in call order, with `toolcall.answer_query` first. The rows commit in the **same writer transaction** as the `Answer`. A turn that ends in a typed failure (503, 400, 404, 410) writes no audit row. `reset_session` writes one `toolcall.reset_session` pair in the same transaction as the reset.
3. **Append-only (AD-10, I14).** An `UPDATE` on `audit_records` and a `DELETE` with the rotation gate closed both fail through the existing triggers. The code exposes no update or delete path for audit rows, and no route edits or deletes them (route audit, AD-13).
4. **Write-time redaction (NFR-11, I15, D45).** Before a row is stored, `params_summary` and `result_summary` pass through the pure `src/domain/redaction.py` filter. It replaces the value of every key whose name contains `api_key`, `apikey`, `token`, `secret`, `password`, `authorization` or `credential` (case-insensitive) with `[REDACTED]`, and rewrites `bearer <token>` and `<key>=<value>` / `<key>: <value>` patterns inside string values. The query text itself is never stored in an audit row. An S1-shaped query that carries `Authorization: Bearer sk-live-123`, `api_key=abc123` and `token: t0ps3cret` leaves 0 occurrences of `sk-live-123`, `abc123` or `t0ps3cret` anywhere in `tool_calls` or `audit_records`.
5. **Retention cap (I20, D42, D50).** `Settings.audit_retention_cap` (env `M12_AUDIT_RETENTION_CAP`, default `10000`, minimum `1`) bounds `audit_records` across all sessions. When an append takes the count above the cap, the same transaction opens the rotation gate, deletes the oldest excess rows by `(timestamp, audit_id)` ascending together with their `tool_calls` rows, and closes the gate (C9). The gate is closed again after every commit and after every rollback. The rotation is logged once at INFO with the number of rows removed. With cap = 5 and two S1 turns, exactly the 5 newest rows remain and every remaining row is newer than every removed one.
6. **`GET /api/v1/sessions/{sid}/audit`.** It returns HTTP 200 `{entries, page, page_size, total, has_more}` (`GetAuditPageResponse`). `entries` are that session's rows, ordered by `(timestamp, audit_id)` ascending, with `len(entries) <= page_size`. `total` is the session's retained row count and `has_more` is `page * page_size < total`. A page beyond the retained rows (with `(page - 1) * page_size < cap`) returns `entries: []` and the same `total` (E14). `page < 1`, `page_size` outside `1..100`, or `(page - 1) * page_size >= cap` returns HTTP 400 `PAGINATION_INVALID`. An unknown session returns HTTP 404 `SESSION_NOT_FOUND`. A store failure returns HTTP 503 `PROVIDER_UNAVAILABLE`. Reading the audit writes no audit row (contracts Q3). After the S1 investigation, the page lists every tool call of the turn exactly once, in call order.
7. **`GET /api/v1/state/{entity_type}/{id}` (FR-12).** `{entity_type}` is one of the nine route names (§0.2), otherwise HTTP 400 `VALIDATION_BAD_ENTITY_TYPE`. `{id}` is the bare id segment matching `^[A-Za-z0-9._-]{1,200}$`, otherwise HTTP 400 `VALIDATION_MALFORMED_BODY`. The key `{type}#{id}` is read through that type's provider port. HTTP 200 returns the bare record (openapi `Record`, D7), equal field-for-field to the fixture record for every record of every type (100% of the sampled records). An absent record returns HTTP 404 with the message `Entity Not Found in State: {type}#{id}.`. A provider failure returns HTTP 503. The estate is unchanged afterwards (AD-1).
8. **`GET /api/v1/state/{entity_type}?q=&page=&page_size=` (I22).** It returns HTTP 200 `{items, page, page_size, total}` (`BrowseStateResponse`) with `len(items) <= page_size`. `q` matches case-folded and exactly, on the full key or the bare id, and an empty `q` lists everything. `total` is the matched count clamped to 10,000 (E49). A page beyond `total` returns `items: []` with the same `total` (E13). `page < 1`, `page_size` outside `1..100`, or `page > 10_000 / page_size` returns HTTP 400 `PAGINATION_INVALID`. An unknown `{entity_type}` returns HTTP 400 `VALIDATION_BAD_ENTITY_TYPE`. All nine types browse, `windows` and `events` included (D8).
9. **Contract kept in sync.** The three routes are added to `SERVED_IN_THIS_STORY` in the route audit. `openapi.yaml` and `contracts.md` change in the same commit as each shape change (D6–D9). `src/dto.py` stays byte-identical to `planning/detailed-design/schemas/dto.py`. Branch coverage of `src` stays at 90% or above, `ruff check .` is clean, `test/ci/schema_check.py` passes and the full `pytest` passes. The coverage log goes in `docs/evidence/impl2/flow-b-1-5-coverage.log`.

## Tasks / Subtasks

Flow B: each task's code and its tests are one commit. Do not commit code without its tests.

- [x] **Task 1: SqliteWriter, with the session store migrated and no behaviour change** (AC: 1) -> `refactor(story-1.5): one SqliteWriter for every store (I2-06)`
  - [x] 1.1 `src/adapters/outbound/db/sqlite_writer.py` (new). `class SqliteWriter(UnitOfWorkPort)`:
        - `open(path) -> SqliteWriter` (classmethod): `sqlite3.connect(path, check_same_thread=False, isolation_level=None)`, then `PRAGMA foreign_keys = ON` and `PRAGMA busy_timeout = 5000`.
        - `transaction() -> ContextManager[sqlite3.Connection]`: takes the `threading.RLock`. On the outermost entry it runs `BEGIN IMMEDIATE`. It is re-entrant on the same thread, and an inner block joins the outer transaction. If any block raises, the transaction is marked rollback-only; the outermost exit then runs `ROLLBACK`, otherwise `COMMIT`. Once the transaction is rollback-only, a later inner `transaction()` raises `RollbackOnly` (a subclass of `sqlite3.Error`, so the stores' existing `except sqlite3.Error` turns it into a typed `Failure`).
        - `atomic() -> ContextManager[Transaction]`: the `UnitOfWorkPort` form of `transaction()`, used by the application. It yields a handle whose `abort()` marks the transaction rollback-only.
        - `read() -> ContextManager[sqlite3.Connection]`: the same lock, no `BEGIN`. One connection cannot serve two threads at once (D-6.2).
        - `run_script(script: str) -> None`: for the migration runner. It calls `executescript` and, on `sqlite3.Error`, rolls back if `in_transaction` and re-raises.
        - `close() -> None`.
  - [x] 1.2 `src/ports/outbound/unit_of_work.py` (new): `UnitOfWorkPort.atomic()` plus a `Transaction` protocol with `abort()`. It imports no `sqlite3` (the ruff ban and `test_architecture_imports.py` both enforce this). Export it from `src/ports/outbound/__init__.py`.
  - [x] 1.3 `migrate.py`: `apply_migrations(writer: SqliteWriter, directory)`. Bookkeeping reads go through `writer.read()`, scripts through `writer.run_script(...)`, and the `connection.rollback()` call moves into the writer. The checksum and one-transaction-per-file behaviour stay the same, so all of `tests/integration/test_migrations.py` must pass (update its construction to `SqliteWriter.open(":memory:")`).
  - [x] 1.4 `session_store.py`: `SqliteSessionStore(writer)`. Delete `self._lock`, the `PRAGMA foreign_keys` line in `__init__`, and the hand-written commit and rollback. `_run(work)` becomes "writes use `writer.transaction()`, reads use `writer.read()`, and `sqlite3.Error` / `ValueError` become `Failure("PROVIDER_UNAVAILABLE")`". `BaseException` still propagates. The SQL and the return values do not change.
  - [x] 1.5 Delete `src/adapters/outbound/db/connection.py`. `bootstrap.py` opens `SqliteWriter.open(settings.db_path)`, and `Container.connection` becomes `Container.writer` (`close()` closes it). Update `tests/unit/test_bootstrap.py`, which monkeypatches `open_database` and touches `container.connection`, and the helpers in `test_session_service.py`, `test_evidence_service.py`, `test_citation_binding_handlers.py` and `tests/integration/test_session_store.py`.
  - [x] 1.6 Tests:
        - `tests/unit/test_single_writer.py`: AST/grep over `src/` shows that only `sqlite_writer.py` contains `.commit(`, `.rollback(` or `sqlite3.connect` (D-6.5b). Feed the checker a bad snippet once, so it cannot pass vacuously.
        - `tests/integration/test_sqlite_writer.py`:
          - nested commit and nested rollback;
          - a `RollbackOnly` re-entry;
          - `abort()`;
          - the pragmas (`foreign_keys = 1`, `busy_timeout = 5000`; on a file DB, `journal_mode = wal`);
          - a script failure rolls back.
        - The cross-store case (§6.3.5 IR-05 row), on a **file** DB: thread A opens `transaction()`, inserts a session row, signals a `threading.Event` and then raises. Thread B, started on that event, commits its own session row through the store. Assert that A's row is absent, B's row is present and B's call returned `Ok`. Use `Event`/`Barrier` only, never a sleep. The case must be red against the old per-store-lock design (record that in the Debug Log).
- [x] **Task 2: Redaction, audit store and retention** (AC: 3, 4, 5) -> `feat(story-1.5): append-only audit store with write-time redaction and retention`
  - [x] 2.1 `src/domain/redaction.py` (new, pure): `redact(value: object) -> object`. It recurses into dicts, lists and tuples and returns a new structure without mutating the input, using the key and value patterns of AC 4. Tests in `tests/unit/test_redaction.py` cover each key pattern, case-insensitivity, nesting, the bearer, `=` and `:` value patterns, and benign values left untouched (`user#alex`, `deepseek-coder`, `policy#catalog.4.2`).
  - [x] 2.2 `src/ports/outbound/audit_store.py` (new): `AuditStorePort` with these methods:
        - `append(entries: Sequence[AuditEntry]) -> Result[None]`. `AuditEntry` is a frozen dataclass pairing a `ToolCallDTO` (or `None`) with its `AuditRecordDTO`.
        - `page(session_id, offset, limit) -> Result[tuple[list[AuditRecordDTO], int]]`, returning the rows and the session's total.
        - `highest_counters() -> Result[dict[str, int]]` for `tool_call` and `audit`.
  - [x] 2.3 `src/adapters/outbound/db/audit_store.py` (new): `SqliteAuditStore(writer, retention_cap)`. `append` runs in one `writer.transaction()`, so it joins the turn's transaction when one is open. It inserts each `tool_calls` row and then its `audit_records` row (C8 SQL), counts `audit_records`, and when the count is above the cap rotates with C9 inside the same transaction. The rotation deletes the excess `audit_records` rows first, then the `tool_calls` rows they referenced, and closes the gate. `page` runs under `writer.read()`, `ORDER BY timestamp, audit_id LIMIT ? OFFSET ?`, with `json.loads(result_summary)`. JSON goes through `json.dumps(..., sort_keys=True)`, so stored bytes are deterministic. `highest_counters` uses the `highest` helper idea from the session store (`tc-` from `tool_calls`, `aud-` from `audit_records`).
  - [x] 2.4 `config.py`: `audit_retention_cap: int = Field(10_000, ge=1)`. Test it in `test_config.py`: the default, the env override, and `0` rejected.
  - [x] 2.5 Tests in `tests/integration/test_audit_store.py`, on the real migrated schema:
        - an append round-trip;
        - `UPDATE` and `DELETE` raise `sqlite3.IntegrityError` / `DatabaseError` with the trigger text (AD-10);
        - a duplicate `tool_call_id` fails through `ux_audit_tool_call`, and the whole batch rolls back;
        - rotation at cap 5 keeps the 5 newest, the removed `tool_calls` are gone, `gate_open = 0` after commit, and also after a failure injected mid-rotation (rollback);
        - INFO log via `caplog`;
        - `page` ordering with a timestamp tie broken by `audit_id`;
        - `highest_counters`.
- [x] **Task 3: Tool-call recording in the composition root, atomic with the turn** (AC: 2, 4) -> `feat(story-1.5): audit every tool call of a turn`
  - [x] 3.1 `src/application/tool_audit.py` (new, stdlib + ports only, R3):
        - `ToolCallRecorder`. A `contextvars.ContextVar` holds the active turn's list of `RecordedCall(tool_name, params, status, error_code, result_count)`. `turn()` is a context manager that installs a fresh list and resets the token on exit. `record(...)` is a no-op when no turn is active, so the evidence and state routes, which share the same wrapped ports, record nothing (D4).
        - `audited(port_type, adapter, *, name, recorder) -> port_type`. It builds a subclass of `port_type` (`type(f"Audited{port_type.__name__}", (port_type,), methods)`) whose every abstract method delegates to `adapter`, then records `toolcall.{name}.{method}`. The params are the bound arguments by parameter name (`inspect.signature`); dataclasses and DTOs are dumped, and other values pass through. The status is `ok` for `Ok` and `failure` with the `code` for `Failure`. `result_count` is `0`/`1` for an `Optional` value, `len` for a list, and absent for other values. The wrapper is generic, so a new port needs no new code (NFR-10). The `isinstance` check in `Container.register_port` must pass.
        - `TOOL_PORT_NAMES`: `{UsersPort: "users_port", CatalogPort: "catalog_port", PolicyPort: "policy_port", GroupsPort: "groups_port", JobsPort: "jobs_port", NodesPort: "nodes_port", ReservationsPort: "reservations_port", WindowsPort: "windows_port", EventStorePort: "event_store_port", PolicyContentPort: "policy_content_port", RunbookRegistryPort: "runbook_registry_port"}`. The clock, idgen, prose and stores are not tool calls (D3).
  - [x] 3.2 `src/application/audit_writer.py` (new). `AuditWriter(store: AuditStorePort, idgen: IdGenPort)` with `entries_for(session, now, head: RecordedCall, calls) -> Result[list[AuditEntry]]`:
        - It mints a `tool_call` id and an `audit` id for each call, in order (head first). An idgen failure is returned as-is.
        - It redacts the params into `params_summary`.
        - `result_summary = redact({"tool_name", "status", "error_code"?, "result_count"?})`, because the openapi `AuditRecord` has no tool-name field (D5).
        - Every row gets `actor = "copilot"`, `timestamp = now.instant`, and the session id and `operator_role`.
        - `write(entries)` calls `store.append`. On failure it returns `fail("AUDIT_WRITE_FAILED", tool_call_id=<first id>)`.
  - [x] 3.3 `session_service.py`. `SessionService` gains `uow: UnitOfWorkPort`, `audit: AuditWriter` and `recorder: ToolCallRecorder`.
        - In `submit_query`, run `self._pipeline.respond(...)` inside `with self._recorder.turn() as calls:`.
        - On `Ok`, build the head `RecordedCall("toolcall.answer_query", params={"answer_id", "intent", "resolved_entities"}, status="ok", result=...)` with `diagnosis_class` or `canonical` in its summary, and never the query text. Then call `entries_for(...)`, so every id is minted **before** the transaction (D-2.3).
        - Then `with self._uow.atomic() as tx:` run `append_turn` and `audit.write(entries)`. Call `tx.abort()` and return the failure if either one fails.
        - `reset_session` does the same with one `toolcall.reset_session` call. The operator role comes from the session row already read.
  - [x] 3.4 `bootstrap.py`:
        - Build `SqliteAuditStore(writer, settings.audit_retention_cap)`.
        - Seed `SimIdGen.from_counters` with the session-store counters merged with the audit-store counters. This closes the deferred 1-2 item for `tool_call`/`audit` (E43).
        - Wrap every port in `TOOL_PORT_NAMES` with `audited(...)` **once** and hand the wrapped ports to the resolvers, assembler, handlers and `EvidenceService`. Register the wrapped instances in `container.ports` (deferred-work 1-1: "wrap the ports in the composition root, no adapter edits needed").
        - Register `AuditStorePort`, `UnitOfWorkPort`, `ToolCallRecorder`.
        - Add an `audit` readiness check, a cheap `page` on a nonexistent session.
  - [x] 3.5 Tests:
        - `tests/unit/test_tool_audit.py`. The wrapper delegates and returns the adapter's result unchanged. It records name, params, status and count for `Ok` and for `Failure`, and records nothing outside a turn. The generated class `isinstance` the port. Nested or parallel contexts do not leak: two threads each in their own turn see only their own calls.
        - `tests/unit/test_audit_writer.py`. Ids are minted in order with the head first. Redaction is applied. An idgen failure mints no further id. A store failure maps to `AUDIT_WRITE_FAILED`.
        - Extend `test_session_service.py`:
          - S1 turn: the row count equals 1 plus the number of port calls the S1 handler makes. Assert the exact ordered `tool_name` list (pin it). All rows have the turn instant and the session's role.
          - A canonical `S_ENF` turn is audited.
          - A 503 turn (fake provider `Failure`) and a 404, 410 and 400 turn write 0 audit rows, and the next `tc`/`aud` id is unchanged.
          - An `AUDIT_WRITE_FAILED` injected at the store rolls back the `Answer` too (no answers row, context unchanged).
          - Reset writes exactly one row.
        - In `tests/unit/test_bootstrap.py`, assert the seeded `tc`/`aud` counters on a file DB after a restart. Assert that the registered ports are the audited ones.
- [x] **Task 4: `GET /api/v1/sessions/{sid}/audit`** (AC: 6) -> `feat(story-1.5): get_audit_page route`
  - [x] 4.1 `src/ports/inbound/audit_use_cases.py`: `AuditUseCases.get_audit_page(session_id, page, page_size) -> Result[GetAuditPageResponse]`. Export it.
  - [x] 4.2 `src/application/audit_service.py`: `AuditService(sessions: SessionStorePort, audit: AuditStorePort, retention_cap)`. Validate the pagination first (`PAGINATION_INVALID`, AC 6), then `sessions.get` (`SESSION_NOT_FOUND`), then `audit.page`. It writes nothing and reads no clock. Add an `UnavailableAuditUseCases` fallback in `unavailable.py`, wired like the evidence fallback.
  - [x] 4.3 `src/adapters/inbound/audit.py`. The router uses prefix `/api/v1` and tag `audit`. `sid` is `SessionIdPath`, the same pattern as `sessions.py`, and `page`/`page_size` are plain `int` query params with defaults 1/20, so the use case, not FastAPI, returns `PAGINATION_INVALID`. Keep the route `def`, never `async def` (D-2.6). Include it in `app.py`.
  - [x] 4.4 Tests in `tests/api/test_audit_api.py`, through `TestClient(create_app(...))`:
        - S1 then page: 200, the exact ordered `tool_name`s, the schema-valid body, `has_more`, and the page beyond the rows;
        - 400 for `page=0`, `page_size=101` and the depth over the cap;
        - 404 for an unknown session;
        - 503 with `UnavailableAuditUseCases`;
        - row count unchanged after two reads (Q3).
- [x] **Task 5: State inspection routes** (AC: 7, 8) -> `feat(story-1.5): get_state_record and browse_state`
  - [x] 5.1 Add a query-only `browse(q, page, page_size)` to `WindowsPort` and `EventStorePort` (D8). `SimWindows`/`SimEventStore` delegate to `RecordStore.browse`. Update the two test doubles that break, as in 1.4. `test_ports_query_only.py` must pass.
  - [x] 5.2 `src/ports/inbound/state_use_cases.py` and `src/application/state_service.py`. `StateService` holds one table `{route_name: (entity_type, get, browse)}` over the nine ports: `users→user`, `catalog→model`, `policy→policy`, `groups→group`, `jobs→job`, `nodes→node`, `reservations→reservation`, `windows→window`, `events→event`. It is the only map, and a new type adds one row (NFR-10).
        - `get_state_record` checks, in order: the entity type (`VALIDATION_BAD_ENTITY_TYPE`, with `value`/`enum` slots), the id regex (`VALIDATION_MALFORMED_BODY`), then the port `get`. `None` gives `fail("ENTITY_NOT_FOUND", ref_list=key)`, and a `Failure` passes through.
        - `browse_state` checks the pagination (`page`, `page_size`, `page <= 10_000 / page_size`) before any read. `items` comes from the port `browse(q, page, page_size)`. `total` comes from paging the same port with `page_size = 100` until a short page, stopping at 10,000 (E49, D9).
        - Add the `UnavailableStateUseCases` fallback only if the providers can be absent. They cannot (a failed estate is already a typed `Failure` on every read), so do not add one.
  - [x] 5.3 `src/adapters/inbound/state.py`. Use the router tag `state`, `GET /state/{entity_type}/{id:path}` (so an id with an encoded `/` reaches the regex and returns 400, not the framework 404) and `GET /state/{entity_type}`. `entity_type` is a plain `str`, so the use case returns `VALIDATION_BAD_ENTITY_TYPE`. 200 bodies are `record.model_dump(mode="json")` and `BrowseStateResponse(...).model_dump(mode="json")`. Include the router in `app.py`.
  - [x] 5.4 Tests:
        - `tests/unit/test_state_service.py`:
          - every route name maps to the right port;
          - validation order (a bad type wins over a bad id; pagination is checked before any read, so a spy port has 0 calls);
          - the `total` clamp at 10,000 with a fake port;
          - a page beyond `total`;
          - a provider `Failure` passes through.
        - `tests/api/test_state_api.py`:
          - for **every** record of **every** fixture file, `GET /state/{type}/{id}` equals the fixture JSON field-for-field (100% sample, FR-12);
          - 404 body `S_ENF` for `nodes/ghost`;
          - 400 for `gpus/x` and `nodes/ws gpu 11`;
          - browse `nodes?q=WS-GPU-11` gives 1 item and `total = 1`;
          - browse `windows` and `events`;
          - the page beyond `total`;
          - 400 at `page_size=101` and `page=10001&page_size=1`;
          - `SimProviders.estate_snapshot()` unchanged after all calls (AD-1).
- [x] **Task 6: ATDD, contract docs, evidence** (AC: 1–9) -> `test(story-1.5): ATDD for the audit log and state inspection`
  - [x] 6.1 `tests/atdd/test_story_1_5.py` on the real app, `create_app(Settings.from_env({...}))` with a **file** DB under `tmp_path`:
        - The S1 investigation (`POST /api/v1/sessions`, then `POST /sessions/{sid}/queries` with `Why was student Alex denied access to model deepseek-coder?`), then `GET /sessions/{sid}/audit`. Each tool call appears once, in call order, with no edit or delete route (the route audit plus `PUT`/`PATCH`/`DELETE` on `/sessions/{sid}/audit` answer 405 or 404, never 2xx).
        - The redaction query of AC 4.
        - Retention at `M12_AUDIT_RETENTION_CAP=5`.
        - State routes: `user#alex`, `model#deepseek-coder` and `policy#catalog.4.2` (the S1 evidence) field-for-field; `user#ghost` → `S_ENF`.
        - Concurrency: 8 sessions released by `threading.Barrier(8)` through the use cases (pattern: `tests/integration/test_sessions_concurrency.py`). Audit rows = 8 × the per-turn count, with distinct ids, no gaps and no `database is locked`.
  - [x] 6.2 `test/atdd/module12_contracts.test.py` is a contract source only and cannot go green: do not edit it. Its `test_get_state_record_happy_renders_fields_verbatim` expects `toolcall.state.get`. Record the D2 divergence in the completion notes.
  - [x] 6.3 Contract docs, same commit as each code change:
        - `openapi.yaml`:
          - `/sessions/{sid}/audit` gets `503` and adds `PROVIDER_UNAVAILABLE` and `VALIDATION_MALFORMED_BODY` to `x-error-codes` (D6);
          - `/copilot/query` adds `AUDIT_WRITE_FAILED` to `x-error-codes` (it already declares 500);
          - `DELETE /sessions/{sid}` gets `500` and `AUDIT_WRITE_FAILED`.
        - `contracts.md`:
          - `get_audit_page`: P1 depth rule, Q-fail 503, and response fields `total`/`has_more` (openapi already has them);
          - Q3 of `get_state_record`, `browse_state`, `get_answer_evidence` and `get_citation` (D2);
          - OP-8/OP-9 `browse` (D8);
          - `answer_query` Q3: rows atomic with the `Answer`, none on a failed turn (D1);
          - I20 retention config.
        - `epics.md`, both copies, identical: story 1.5 `Schema/DTO` says `SQL audit_events (append-only trigger)`; the tool-call audit table is `audit_records` (`audit_events` is the telemetry log). Fix that one word.
  - [x] 6.4 `docs/ai-decision-log.md`: I2-15 already records D1–D9 (Reviewer Julio). At the end of development, add the outcome (test count, coverage, evidence log) to that entry. Do not create a new entry for these decisions.
  - [x] 6.5 Gate: `pytest` (full), branch coverage ≥ 90%, `ruff check .`, `python test/ci/schema_check.py`. Save the coverage run to `docs/evidence/impl2/flow-b-1-5-coverage.log`. Never edit an existing evidence file.

## Dev Notes

### What already exists (do not rebuild)

- **The schema is complete. No new migration.** `migrations/001_module12_copilot_schema.sql` already has `tool_calls`, `audit_records`, `ux_audit_tool_call`, `ux_audit_executor_apply`, `ix_audit_session_ts`, `audit_rotation_gate`, `trg_audit_records_no_update`, and `trg_audit_records_no_delete` (gate-aware), plus the C8/C9 SQL in comments. Do **not** edit `001_*.sql`: its SHA-256 is checked and every applied DB would refuse it (log I2-01..09 "Not applied yet").
- `audit_events` is a **different** table (telemetry envelopes). Story 1.5 writes `tool_calls` + `audit_records` only.
- DTOs exist and must not change: `ToolCallDTO`, `AuditRecordDTO`, `GetAuditPageResponse` (`total`, `has_more`), `BrowseStateResponse`, `RecordDTO`. `src/dto.py` must equal `planning/detailed-design/schemas/dto.py` byte for byte (`test_dto_contract.py`).
- `SimIdGen` already knows the `tool_call` (`tc-`, 16) and `audit` (`aud-`, 16) kinds. The schema CHECKs lengths 19 and 20.
- `RecordStore.browse` already does case-folded exact matching on the full key or the bare id, the `page_size <= 100` check and slicing. Reuse it through the ports.
- `fail("ENTITY_NOT_FOUND", ref_list=...)`, `fail("SESSION_NOT_FOUND", sid=...)`, `fail("AUDIT_WRITE_FAILED", tool_call_id=...)`, `failure_response` and `S_ENF` already exist. Never hand-format a canonical literal.
- `EvidenceService._sources` is the citation-type → port map. `StateService` needs the route-name → (type, port) map, which is a different key space. Do not merge them.
- `tests/integration/test_sessions_concurrency.py` is the `Barrier` pattern to copy.

### Current state of the files this story changes

- `connection.py` is one `sqlite3.connect(check_same_thread=False)`. It is **deleted**.
- `session_store.py` has its own `RLock`, `PRAGMA foreign_keys` in `__init__`, and implicit transactions committed when `in_transaction`. This is the IR-05 defect: once a second store with a second lock exists, store B's `commit()` commits A's half-written turn. Keep every SQL statement and every return shape. Change only how the connection is reached.
- `migrate.py` calls `executescript("BEGIN; … COMMIT;")` and `connection.rollback()`. The behaviour stays the same; only the calls move through the writer.
- `bootstrap.py` opens the connection, builds providers, `_wire_sessions`, the pipeline with the handlers, `SessionService` and `EvidenceService`, and readiness. Preserve:
  - a broken DB never crashes the build (`Unavailable*UseCases` plus a failing `/readyz`);
  - the readiness probe goes through a store, never the raw connection;
  - the clock probe consumes no read id.
- `session_service.py` has a per-session `_Guard` and one clock read inside the guard. It mints `answer_id` before `respond`, and `append_turn` is the only write. Keep the guard. It serializes the turns of one session, and the writer lock serializes the DB, which is a different job. Never take the writer lock across `pipeline.respond` (prose), or 50 operators would queue behind one LLM call (D-3 phase 3, same reasoning).

### Decisions (confirmed by Julio 2026-11-07, log I2-15)

- **D1. Atomic turn audit.** The audit rows of a turn commit in the same writer transaction as its `Answer`. A turn that returns a typed failure persists nothing, so it leaves no orphan rows (contracts `answer_query` Q3 "voided"). The ids are minted before the transaction, in call order, which keeps the order deterministic and is the D-2.3 precondition for 1-6.
- **D2. Session-less reads are not audited (confirmed by Julio).** contracts Q3 asks for `toolcall.state.get`, `toolcall.state.browse`, `toolcall.evidence.get` and `toolcall.citation.get`. Those routes have no session. `tool_calls.session_id` is `NOT NULL`, the audit API is per session, and those routes read no clock while `timestamp` is `NOT NULL`. Auditing them would need a schema migration and an extra clock read per request. Decision: not audited in 1.5. Amend the four Q3 lines to read "not audited: session-less read (story 1.5 D2)". The wrapped ports still record nothing outside a turn.
- **D3. What a tool call is.** Every call to one of the 11 provider ports (`TOOL_PORT_NAMES`) during a turn, plus one `toolcall.answer_query` head per turn and `toolcall.reset_session`. The clock read (the turn stamp), idgen, prose and the stores are not tool calls.
- **D4. The wrapper is ambient, through `contextvars`.** No handler, resolver or port signature changes. 1-6's `asyncio.to_thread` copies the context, so recording keeps working there. **Forward constraint for 1-6:** a parallel fan-out appends in completion order. `ParallelReads` must reserve the recorder slots in argument order before the gather (D-2.1/2.3). Do not build that here; leave a docstring note on `ToolCallRecorder`.
- **D5. Tool metadata lives in `result_summary`** (`tool_name`, `status`, `error_code`, `result_count`), because openapi `AuditRecord` has no tool-name field and `additionalProperties: false`. `params_summary` (entity ids, selectors, windows) stays in `tool_calls`. The query text is never stored.
- **D6. The audit route can fail with 503**, and openapi will declare it (precedent: I2-14 for the evidence route).
- **D7. `GET /state/{type}/{id}` returns the bare record.** openapi says `schema: Record`, and contracts says `-> Record`. `GetStateRecordResponse(record=…)` in `dto.py` is not used on the wire. Leave it untouched (verbatim copy rule).
- **D8. `browse` on `WindowsPort` and `EventStorePort`.** Query-only, the same precedent as 1.4 D3 (`EventStorePort.get`). Without it, `windows` and `events` cannot honour `browse_state` P2 (q matching).
- **D9. `total` by paging the port (confirmed by Julio, kept as deferred work).** No `count` method is added to seven ports. The cost is at most 100 page reads at the 10,000 cap. The fixtures hold far less (32 nodes). Add a deferred-work line: "add `count` to the read ports if stores grow."
- **Audit page depth.** `(page - 1) * page_size < cap` (contracts "page depth never exceeds the retention cap"). `browse_state` keeps its literal contract rule `page <= 10_000 / page_size`. The two rules differ on purpose. Write the audit one into contracts.md.

### Guardrails (docs/impl2-rules.md)

- Use `src/` paths. The epics' `service/app/audit_writer.py` → `src/application/audit_writer.py`, `service/adapters/db/audit_store.py` → `src/adapters/outbound/db/audit_store.py`, and `api/routes/{audit,state}.py` → `src/adapters/inbound/{audit,state}.py`.
- `src/domain`, `src/ports` and `src/application` import no adapter, framework, `sqlite3`, `time`, `os`, `random` or `uuid` (`test_architecture_imports.py`). `contextvars`, `inspect`, `threading` and `dataclasses` are fine.
- Time comes only from the Clock port (the turn's one read, reused for every audit row). Ids come only from `idgen_port`.
- Registered routes must equal `openapi.yaml`. Update `SERVED_IN_THIS_STORY` with `("GET", "/api/v1/sessions/{}/audit")`, `("GET", "/api/v1/state/{}/{}")` and `("GET", "/api/v1/state/{}")`. None of the three is mutating.
- Never use `sleep`, `asyncio.sleep` or `waitForTimeout`; CI greps for them. Use `Event` and `Barrier`.
- Never mock the unit under test. Use the real SQLite schema, the real stores and the real app. Fakes go only at outbound ports. Assert what did **not** happen: no audit row on a failed turn, no id drawn, estate unchanged, gate closed.
- Keep both `epics.md` copies identical, and both `sprint-status.yaml` copies (`_bmad-output/implementation-artifacts/` and `implementation-artifacts/`).
- Story 1.8 owns the console. Do not touch `console/` or `tests/e2e/`.

### Files

| File | Change |
|---|---|
| `src/adapters/outbound/db/sqlite_writer.py` | new |
| `src/adapters/outbound/db/connection.py` | delete |
| `src/adapters/outbound/db/migrate.py` | update (writer) |
| `src/adapters/outbound/db/session_store.py` | update (writer, no lock) |
| `src/adapters/outbound/db/audit_store.py` | new |
| `src/adapters/outbound/sim/fixtures_adapter.py` | update (`browse` for windows, events) |
| `src/ports/outbound/{unit_of_work,audit_store}.py`, `__init__.py` | new / update |
| `src/ports/outbound/{windows,event_store}.py` | update (`browse`) |
| `src/ports/inbound/{audit_use_cases,state_use_cases}.py`, `__init__.py` | new / update |
| `src/domain/redaction.py` | new |
| `src/application/{tool_audit,audit_writer,audit_service,state_service}.py` | new |
| `src/application/session_service.py`, `unavailable.py` | update |
| `src/adapters/inbound/{audit,state}.py`, `app.py` | new / update |
| `src/bootstrap.py`, `src/config.py` | update |
| `planning/detailed-design/schemas/openapi.yaml`, `planning/detailed-design/contracts.md` | update |
| `planning/epics.md`, `_bmad-output/planning-artifacts/epics.md` | one word, identical |
| `docs/ai-decision-log.md`, `_bmad-output/implementation-artifacts/deferred-work.md` | update |
| tests listed per task, `tests/atdd/test_story_1_5.py` | new / update |

### Testing standards

- Markers: `unit`, `integration`, `api`, as in the existing files. `--import-mode=importlib` means no `__init__.py` is needed.
- Run concurrency and cross-store cases on a **file** DB (`tmp_path`). The default `:memory:` is fine elsewhere.
- Pin the exact ordered `tool_name` list of the S1 turn in one test (as 1.4 pinned evidence order). A test that only asserts `count > 0` passes vacuously.
- Every red-if-removed guard gets one test: the writer lock (cross-store), redaction, the rotation gate, the trigger, atomicity (audit failure rolls back the answer), and session-less recording (no rows outside a turn).

### Previous-story intelligence

- **1.4 / I2-14:** routes whose store can fail must declare 503 in openapi. The evidence route shipped an undeclared 503 and the review caught it. The same applies here to `/audit` (D6).
- **1.4:** a new abstract port method breaks test doubles (`_FailingEvents`, `_RecordingEvents`). Expect the same for `WindowsPort.browse` and `EventStorePort.browse`.
- **1.4:** `ruff format` reformats the hand-aligned `src/dto.py`. Do not run the formatter over it, and leave `dto.py` alone.
- **1.4 audit (I2-14):** tests that pass by scan order or hash order hid mutants. For audit order, make the expected order differ from insertion order in at least one case (a timestamp tie broken by `audit_id`).
- **Deferred 1-2:** extend `highest_counters` when new id kinds persist. That is this story (`tool_call`, `audit`).
- **Deferred 1-2:** `isolation_level` is not pinned. D-6 pins it to `None`.
- **Deferred 1-3 / 3-1:** diagnosers emit no tool-call audit. The composition-root wrapper closes this with no diagnoser edits.
- **Deferred 1-4:** clock ids restart per process. Audit timestamps come from the sim clock, which also restarts, so rotation "oldest first" across a restart orders by sim time. This is a known limitation, inherited from that item. Do not fix it here.

### Git intelligence

Recent commits: `feat(story-1.4)` (citations), Flow C test backfill, CI (GitHub Actions with a banned-waits step under `bash -e -o pipefail`, k6, Playwright traces). Commit style: one Conventional Commit per Flow B task, `feat(story-1.5): …` / `refactor(story-1.5): …`. No new dependency is needed. The code uses stdlib `sqlite3`, `contextvars` and `inspect`, plus the pinned FastAPI and Pydantic v2. The runtime is Python ≥ 3.11, and SQLite ≥ 3.35 is asserted by `tests/support/db.py`.

### Latest tech notes

No new library, so no version research was needed. Behaviours the developer relies on:
- With `isolation_level=None`, sqlite3 opens no implicit transaction, so `BEGIN IMMEDIATE` is explicit.
- `executescript` commits any pending transaction first.
- Each worker thread in Starlette's thread pool runs in a copy of the request context, so a `ContextVar` set inside one sync route does not leak into another request.

### References

- [Source: planning/epics.md#Story 1.5]
- [Source: planning/ARCHITECTURE.md AD-10, §2.2 ToolCall/AuditRecord, Stack Decisions]
- [Source: planning/detailed-design/contracts.md §1 answer_query Q3, §2 get_state_record, browse_state, get_audit_page, reset_session, §3 Q-port-3, OP-8, OP-9, §4 AUDIT_WRITE_FAILED, PAGINATION_INVALID, §5 I14, I15, I18, I20, I22]
- [Source: planning/detailed-design/schemas/openapi.yaml `/sessions/{sid}/audit`, `/state/*`, `AuditRecord`, `GetAuditPageResponse`, `BrowseStateResponse`]
- [Source: migrations/001_module12_copilot_schema.sql tool_calls, audit_records, audit_rotation_gate, triggers, C8, C9]
- [Source: reviews/review-impl2-shift-left.md §2 D-2.3/D-2.6, §5 D-6; docs/ai-decision-log.md I2-06]
- [Source: test/test-design.md R-10, IR-05, §6.3.5 cross-store row, §6.6 TG-I2-1]
- [Source: _bmad-output/implementation-artifacts/deferred-work.md stories 1-1, 1-2, 1-3, 3-1, 1-4]
- [Source: docs/impl2-rules.md Code rules, Test rules]

## Dev Agent Record

### Agent Model Used

Claude Opus 5.5 (`claude-opus-5-5`), Claude Code, `bmad-dev-story` (Flow B).

### Debug Log References

- Baseline before any change: `pytest` 1104 passed at `a3f9161`.
- Cross-store case (Task 1.6) red against the old design: a scratch script ran the pre-1.5 `session_store.py` and `migrate.py`
  (from `git show HEAD:`) with two `SqliteSessionStore` instances, each with its own lock, on one shared file connection. Thread A
  inserted a session row inside its store lock and raised; thread B's `create()` committed meanwhile. Result: `stored:
  ['sess-0000000000000001', 'sess-0000000000000002']`, so B's commit persisted A's half-written row. With `SqliteWriter` the same
  case leaves only B's row (`tests/integration/test_sqlite_writer.py::test_a_failing_transaction_is_never_committed_by_another_stores_write`).
- Mutation checks on the red-if-removed guards (each mutant applied to `src`, then reverted):
  - gate not closed after rotation: killed (`test_audit_store.py`, ATDD);
  - recorder never appends: killed (11 tests);
  - redaction of string values disabled: killed by `test_redaction.py` and `test_audit_writer.py`. The ATDD redaction case
    survives it on its own, because no secret from the query reaches a port parameter in the S1 path; the unit tests are the guard;
  - `tx.abort()` removed after an audit write failure: first survived the full suite, because a store exception already marks the
    writer rollback-only. Added `test_an_audit_failure_without_a_driver_error_still_rolls_back_the_answer` (a store that returns
    a `Failure` without raising); the mutant is now killed.
- With `isolation_level=None`, the existing `test_session_service.py` corrupt-instant case no longer needs its `commit()` call
  (the raw `UPDATE` autocommits); that line was removed from the test helper only.
- Newer FastAPI nests included routers in `app.routes`, so the ATDD lists the audit routes from `app.openapi()["paths"]`, the same
  source the route audit cross-checks.

### Completion Notes List

- Story context created 2026-11-07, scoped against `src/` at `a3f9161`. Ultimate context engine analysis completed - comprehensive developer guide created.
- **Task 1:** `SqliteWriter` owns the only connection (`isolation_level=None`, `foreign_keys = ON`, `busy_timeout = 5000`) and the
  only `RLock`. `transaction()` is re-entrant with rollback-only semantics (`RollbackOnly` is a `sqlite3.Error`), `atomic()` is the
  `UnitOfWorkPort` form (begin or commit failures raise `UnitOfWorkError`, so the application never sees a driver type), `read()`
  takes the same lock, and `run_script()` serves the migration runner. `connection.py` is deleted; the session store and migration
  runner go through the writer with every SQL statement and return shape unchanged. `UnitOfWorkPort` is registered as an owned
  port in `test_ports_query_only.py` and exempt only from the "returns `Result`" rule (it yields a scope).
- **Task 2:** pure `redact()` (key names and `bearer` / `key=value` / `key: value` patterns), `AuditStorePort` +
  `SqliteAuditStore` (C8 inserts, C9 rotation in the same transaction, deleting `audit_records` first and then their `tool_calls`,
  one INFO log after a successful rotating append), `Settings.audit_retention_cap` (`M12_AUDIT_RETENTION_CAP`, default 10,000, `ge=1`).
  The user-requested proof that `UPDATE` and `DELETE` on audit rows fail against the real SQL schema is in
  `tests/integration/test_audit_store.py` (through the writer, on memory and file DBs, plus a raw second connection) and in the
  ATDD on the app's own file DB. The gate is asserted closed after a commit and after a failure injected mid-rotation.
- **Task 3:** `ToolCallRecorder` (one `ContextVar` per recorder) and the generic `audited()` wrapper, built per port with
  `type()` over the port's abstract methods; `AuditWriter` mints `tc`/`aud` ids interleaved per call, head first, before the
  transaction; `SessionService` runs the pipeline inside `recorder.turn()` and writes the answer (or reset) and its audit rows in
  one `uow.atomic()`, aborting on either failure; the writer lock is never held across `pipeline.respond`. The composition root
  wraps the 11 tool ports once and gives the wrapped instances to the resolvers, assembler, handlers, `EvidenceService`,
  `StateService` and the registry; it seeds `SimIdGen` from both stores' counters and adds an `audit` readiness check. Pinned S1
  order: `answer_query`, `users_port.get`, `catalog_port.get`, `policy_port.for_model`, `event_store_port.query`.
- **Task 4:** `AuditUseCases` / `AuditService` (pagination incl. depth `(page - 1) * page_size < cap`, then session, then page),
  `UnavailableAuditUseCases`, and the sync `GET /api/v1/sessions/{sid}/audit` route.
- **Task 5:** query-only `browse` on `WindowsPort` / `EventStorePort` (and the three test doubles), `StateUseCases` /
  `StateService` with the single route-name table, and the two `/state` routes (`{id:path}` so an encoded `/` reaches the id check).
  `StateService` needs no database, so it is wired even when the session store is down. 100% of the 65 fixture records render
  field-for-field.
- **Task 6:** `tests/atdd/test_story_1_5.py` (9 cases, file DB, real app). `test/atdd/module12_contracts.test.py` untouched: its
  `test_get_state_record_happy_renders_fields_verbatim` expects `toolcall.state.get`, which diverges from D2 (session-less reads
  are not audited) by decision. openapi.yaml, contracts.md and both `epics.md` copies amended (6.3); I2-15 outcome recorded (6.4);
  deferred work added for D9 (`count`), D2, the D4 forward constraint for 1-6, and the still-unemitted per-diagnoser events.
- **Gate (6.5):** `pytest` 1379 passed; branch coverage of `src` 97.06%; `ruff check .` clean; `python test/ci/schema_check.py`
  GATE PASS; `src/dto.py` byte-identical to the contract copy; no banned waits. Evidence: `docs/evidence/impl2/flow-b-1-5-coverage.log`.
- **Commits:** none made. Flow B asks for one commit per task; the work is left uncommitted in the working tree for the user to
  commit (the task boundaries are listed in the File List).

### File List

Task 1 (writer):
- `src/adapters/outbound/db/sqlite_writer.py` (new)
- `src/adapters/outbound/db/connection.py` (deleted)
- `src/adapters/outbound/db/migrate.py`, `src/adapters/outbound/db/session_store.py`, `src/bootstrap.py` (modified)
- `src/ports/outbound/unit_of_work.py` (new), `src/ports/outbound/__init__.py` (modified)
- `tests/unit/test_single_writer.py`, `tests/integration/test_sqlite_writer.py` (new)
- `tests/integration/test_migrations.py`, `tests/integration/test_session_store.py`, `tests/unit/test_bootstrap.py`,
  `tests/unit/test_session_service.py`, `tests/unit/test_evidence_service.py`, `tests/unit/test_citation_binding_handlers.py`,
  `tests/unit/test_ports_query_only.py`, `tests/api/conftest.py`, `tests/api/test_sessions.py` (modified)

Task 2 (redaction, audit store, retention):
- `src/domain/redaction.py`, `src/ports/outbound/audit_store.py`, `src/adapters/outbound/db/audit_store.py` (new)
- `src/config.py` (modified)
- `tests/unit/test_redaction.py`, `tests/integration/test_audit_store.py` (new); `tests/unit/test_config.py` (modified)

Task 3 (tool-call recording):
- `src/application/tool_audit.py`, `src/application/audit_writer.py` (new)
- `src/application/session_service.py` (modified)
- `tests/unit/test_tool_audit.py`, `tests/unit/test_audit_writer.py` (new); `tests/api/test_health.py` (modified)

Task 4 (audit route):
- `src/ports/inbound/audit_use_cases.py`, `src/application/audit_service.py`, `src/adapters/inbound/audit.py` (new)
- `src/ports/inbound/__init__.py`, `src/application/unavailable.py`, `src/adapters/inbound/app.py` (modified)
- `tests/api/test_audit_api.py` (new); `tests/api/test_contract_routes.py` (modified)

Task 5 (state routes):
- `src/ports/inbound/state_use_cases.py`, `src/application/state_service.py`, `src/adapters/inbound/state.py` (new)
- `src/ports/outbound/windows.py`, `src/ports/outbound/event_store.py`, `src/adapters/outbound/sim/fixtures_adapter.py` (modified)
- `tests/unit/test_state_service.py`, `tests/api/test_state_api.py` (new)
- `tests/unit/test_access_denial_handler.py`, `tests/unit/test_evidence_assembler.py`,
  `tests/unit/test_window_diagnosis_handler.py` (modified)

Task 6 (ATDD, contract docs, evidence):
- `tests/atdd/test_story_1_5.py` (new)
- `planning/detailed-design/schemas/openapi.yaml`, `planning/detailed-design/contracts.md` (modified)
- `planning/epics.md`, `_bmad-output/planning-artifacts/epics.md` (modified, identical)
- `docs/ai-decision-log.md`, `_bmad-output/implementation-artifacts/deferred-work.md` (modified)
- `docs/evidence/impl2/flow-b-1-5-coverage.log` (new)
- `_bmad-output/implementation-artifacts/sprint-status.yaml`, `implementation-artifacts/sprint-status.yaml` (modified, identical)

## Change Log

- 2026-11-07: Story created (ready-for-dev).
- 2026-11-07: Julio confirmed D1–D9. Session-less reads write no audit rows (D2), browse `total` by paging stays as deferred work (D9), and the session reset audit stays in 1.5. Recorded as log I2-15 (Reviewer Julio).
- 2026-11-07: Implemented (Flow B, Tasks 1-6): single `SqliteWriter`, append-only audit store with write-time redaction and
  retention, every turn and reset audited atomically with its write, `GET /sessions/{sid}/audit`, `GET /state/{type}/{id}` and
  `GET /state/{type}`, ATDD, contract amendments. 1379 tests pass, branch coverage 97.06%, ruff clean. Status -> review.
