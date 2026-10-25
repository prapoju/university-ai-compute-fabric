---
baseline_commit: 17a292faae21c0a4e5a29482b1a04e75c2ab8339
---

# Story 1.1: Seed the fixture estate and stand up the read-only adapter ring

Status: in-progress

<!-- Impl-1 note: this story ALSO carries the "Foundation scaffold" required by the course task (Impl-1 §1, §4):
     runnable project skeleton, config, migrations, dependency validation, health probes, 32-node fixtures.
     The scaffold work is tracked as Task 1 and committed as `feat(scaffold): ...`; the story work as `feat(story-1.1): ...`. -->

## Story

As Nadia (Frontline Lab Helpdesk Specialist),
I want the Copilot's simulated estate seeded with realistic users, catalog, nodes, jobs, groups, windows, policy and runbook content,
so that every later answer is grounded in real, inspectable records rather than invented data.

## Acceptance Criteria

Source: `planning/epics.md` → Story 1.1 (canonical). Requirements: FR-03 (data), AD-1, AD-12, AD-13, NFR-10, C-5.

1. **Fixture estate seeded.** Given the greenfield workspace, when the estate is authored, then `fixtures/` seeds the nine stores `{users, catalog, policy, groups, jobs, nodes, reservations, windows, events}` plus policy content and runbook templates, including:
   - **S1:** `user#alex` (role `student`), model `deepseek-coder` (catalog), clause `policy#catalog.4.2` with `reason_class = not-in-allowlist`, event `event#evt-4711` (`access_denied`).
   - **S2:** `group#group-4` + its pending fine-tuning job `job#job-8823` + Night Policy window `night` (+ policy content `policy#night.2`).
   - **S3:** `node#ws-gpu-11` cordoned with `error_code = ERR_THERMAL_88`, status `fault`, plus the matching runbook template.
   - **S4:** several `pending` jobs for course `CS201`, including `job#job-8823` (the same job S2 uses, per `planning/epics.md`); other ids are fixture content.
   - **Fleet:** exactly **32 nodes** — 31 × 24 GB workstations (`ws-gpu-01`..`ws-gpu-31`) + 1 server with 2 × 48 GB GPUs (Impl-1 §1 "Standalone Engineering Mandate").
2. **Query-only ports.** Each port (`users_port`, `catalog_port`, `policy_port`, `groups_port`, `jobs_port`, `nodes_port`, `reservations_port`, `windows_port`, `event_store_port`, `clock_port`, `policy_content_port`, `runbook_registry_port`) declares **query-only** methods; the simulated adapter reads fixtures and holds no write path (AD-1, AD-13).
3. **Offline + typed results.** The estate loads offline with a freezable clock, and every read returns a typed `ok | failure` result (C-5, AD-12).
4. **Extensibility.** Adding a new entity type (one fixture set + one query-only port) requires no change to the console, the other ports, or the answer pipeline (NFR-10).
5. **Scaffold (Impl-1 §4 — course addition).** `pytest` and the service run from a clean clone following only `README.md`; `GET /healthz` (liveness) and `GET /readyz` (readiness: estate loaded, clock readable, SQLite ≥ 3.35, migrations applied) respond; startup dependency validation fails fast with a clear message.

### BDD scenarios (drive the tests — Given/When/Then)

```gherkin
Scenario: Estate loads offline and exposes S1 through read-only ports
  Given the seeded fixtures directory and a frozen clock at 2026-10-16T15:00:00.000Z
  When the simulated adapters are constructed with no network access
  Then users_port.get("user#alex") returns Ok(UserRecord role="student")
  And policy_port.for_model("model#deepseek-coder") includes clause "policy#catalog.4.2" with reason_class "not-in-allowlist"
  And event_store_port.query(user#alex, access_denied, window containing evt-4711) returns event "event#evt-4711"

Scenario: Fleet fixture has exactly 32 nodes with the specified hardware
  Given the seeded nodes store
  When nodes_port.browse("", 1, 100) is read in full
  Then the total is 32
  And 31 nodes report gpu_memory_gb 24 and exactly 1 reports 96 (2 x 48 GB)
  And node#ws-gpu-11 is cordoned with error_code "ERR_THERMAL_88"

Scenario: Ports are query-only (AD-1 / AD-13)
  Given every outbound port interface
  When its public methods are inspected
  Then no method name denotes mutation (register/set/add/update/delete/write/create/apply/save)
  And the adapter holds no write path and the fixture data is unchanged after any sequence of reads

Scenario: Missing record and failing provider are typed, never raised or fabricated (AD-12)
  When users_port.get("user#ghost") is called
  Then it returns Ok(None)
  Given an adapter whose fixture failed to load
  When any read is made
  Then it returns Failure(code="PROVIDER_UNAVAILABLE") and no partial data

Scenario: Adding an entity type needs no change elsewhere (NFR-10)
  Given a new fixture set and one new query-only port + adapter registered in the composition root
  When the application starts
  Then no existing port, adapter or test file had to be modified
```

## Tasks / Subtasks

Follow the Full Ceremony: write each test **with** its code (red → green → refactor). Commit after each numbered task.

- [ ] **Task 1 — Foundation scaffold** (AC: 5) → commit `feat(scaffold): ...`
  - [x] 1.1 `pyproject.toml` (Python ≥ 3.11; runtime deps: `fastapi`, `uvicorn[standard]`, `pydantic>=2`; dev deps: `pytest`, `pytest-asyncio`, `pytest-cov`, `hypothesis`, `httpx`, `ruff`). Resolve and record the exact versions installed; do **not** add anything else without logging it in `docs/ai-decision-log.md`. Keep `requirements-test.txt` working (or make it `-e .[dev]`).
  - [x] 1.2 Create the `src/` tree (see *File structure*), every package with `__init__.py`. Add `pythonpath = .` to `pytest.ini` so `from src...` imports resolve; keep `testpaths = tests` and existing markers.
  - [x] 1.3 `src/config.py`: `Settings` (Pydantic v2 `BaseModel`) loaded from environment (`M12_*`), validated at startup: `M12_FIXTURES_DIR`, `M12_DB_PATH` (default `:memory:`-safe path), `M12_CLOCK_START` (ISO `Instant`), `M12_LOG_LEVEL`. No extra settings library. `.env.example` documents every variable.
  - [x] 1.4 `src/dependency_check.py` (+ `python -m src.dependency_check`): Python ≥ 3.11, `sqlite3.sqlite_version` ≥ 3.35 (AD-10), required packages importable, fixtures dir present. Returns a list of problems; startup aborts with a readable message if non-empty.
  - [x] 1.4b Migrations: copy `planning/detailed-design/schemas/001_module12_copilot_schema.sql` to `migrations/001_module12_copilot_schema.sql` **verbatim** and add a tiny stdlib-`sqlite3` runner (`src/adapters/outbound/db/migrate.py`, `schema_migrations` table, idempotent). No ORM, no Alembic (ARCHITECTURE "Stack Decisions": no ORM).
  - [x] 1.5 `src/adapters/inbound/app.py` + `src/bootstrap.py` (composition root): `create_app(settings)`; `GET /healthz`, `GET /readyz`. Structured JSON error handler skeleton (`ErrorBody`) so no stack trace ever leaks.
  - [ ] 1.6 `Dockerfile` + `docker-compose.yml` (single service, port 8000, healthcheck on `/healthz`) + `README.md` quick start (`pip install -e .[dev]` → `pytest` → `uvicorn src.adapters.inbound.app:create_app --factory`). Add a `Makefile` target or keep the existing ones working.
  - [x] 1.7 Tests: `tests/unit/test_config.py`, `tests/unit/test_dependency_check.py`, `tests/integration/test_migrations.py`, `tests/api/test_health.py` (healthz 200; readyz 200 when ready and 503 + structured JSON when fixtures missing).
- [ ] **Task 2 — Shared DTOs + domain primitives** (AC: 2, 3)
  - [x] 2.1 Copy `planning/detailed-design/schemas/dto.py` **verbatim** to `src/dto.py` (it is the contract). Add `tests/unit/test_dto_contract.py` asserting the copy is byte-equal (modulo line endings) to the planning file so drift fails the build.
  - [x] 2.2 `src/domain/result.py`: `Ok[T]`, `Failure` (frozen dataclasses; `Failure.code` ∈ the §4 `ErrorCode` literal), plus `is_ok` helpers. Pure — no I/O.
  - [x] 2.3 `src/domain/entity_key.py`: parse/format `{type}#{id}`, case-fold compare (AD-7 groundwork only — resolution logic is story 1.3). Unit-test escape rule `\#` (D61) and bad types → `VALIDATION_BAD_ENTITY_TYPE`.
- [ ] **Task 3 — Outbound ports** (AC: 2, 4)
  - [x] 3.1 `src/ports/outbound/` (ABCs or `Protocol`s): `users.py`, `catalog.py`, `policy.py`, `groups.py`, `jobs.py`, `nodes.py`, `reservations.py`, `windows.py`, `event_store.py`, `clock.py`, `policy_content.py`, `runbook_registry.py`. Signatures exactly as `contracts.md` §3 OP-1..OP-12, returning `Result[...]`, using DTO types only (R4).
  - [x] 3.2 Test `tests/unit/test_ports_query_only.py`: introspect every port; assert the method set equals the allowed set from §3 and that no name matches the mutation denylist (BDD "Ports are query-only").
- [ ] **Task 4 — Fixture estate** (AC: 1)
  - [x] 4.1 `fixtures/estate/{users,catalog,policy,groups,jobs,nodes,reservations,windows,events}.json`, `fixtures/policy_content/*.json`, `fixtures/runbooks/*.json`. Content rules in *Fixture content* below.
  - [x] 4.2 Static copies of the 32-node fleet where the course expects them: `tests/fixtures/nodes.json` may be a **copy generated from** `fixtures/estate/nodes.json` (single source of truth is `fixtures/`; add a test that both match).
  - [x] 4.3 Tests: `tests/unit/test_fixture_estate.py` — 32 nodes (31 × 24 + 1 × 96), S1–S4 anchors present, every record validates against its DTO (`extra="forbid"`), ids unique, `start < end` for reservations/windows (D66).
- [ ] **Task 5 — Simulated adapters** (AC: 2, 3, 4)
  - [x] 5.1 `src/adapters/outbound/sim/estate_loader.py`: loads + validates fixtures once into an immutable `Estate` (tuples / `MappingProxyType`); any load/validation error ⇒ adapters return `Failure("PROVIDER_UNAVAILABLE")` (never raise to callers, never partial data).
  - [x] 5.2 `src/adapters/outbound/sim/fixtures_adapter.py`: one adapter class per port over the shared `Estate`; stable ordering (`id` / `clause_id` / `window_id` ascending; events by `timestamp`, then `event_id`); `browse` = case-folded exact-id match, empty `q` returns all, `page_size ≤ 100` (else `PAGINATION_INVALID`), page beyond total ⇒ empty list not error (E13).
  - [x] 5.3 `src/adapters/outbound/sim/clock_adapter.py`: freezable, advanceable `SimClock` implementing OP-10 (`read_id` `^clk-[0-9a-f]{16}$`, `source="clock"`, `instant` from `M12_CLOCK_START`). Never calls `datetime.now()` (R1/R2).
  - [x] 5.4 Wire everything in `src/bootstrap.py` (composition root builds adapters from `Settings`; the app and tests both use it).
  - [x] 5.5 Tests (BDD-mapped, one file per scenario group): `tests/unit/test_story_1_1_estate_ports.py`, `tests/unit/test_story_1_1_typed_failures.py`, `tests/unit/test_story_1_1_extensibility.py` (registers a toy `widgets` store + port without touching existing modules). Add a **read-only proof**: deep-compare estate snapshot before/after a battery of reads.
- [ ] **Task 6 — Architecture guards** (AC: 2)
  - [ ] 6.1 Import audit test `tests/unit/test_architecture_imports.py`: `src/domain` and `src/ports` import no `fastapi`, `sqlite3`, `datetime.now`-style clock, `random`, `uuid`, `httpx`; `src/domain` and `src/ports` never import `src.adapters.*` (R1, R3). Add the `ruff` `TID` banned-api config in `pyproject.toml` to mirror it.
- [ ] **Task 7 — DoD verification and review report**
  - [ ] 7.1 Run `ruff check src tests` and `pytest` (all green, **0 skipped**); paste the output summary in the Dev Agent Record.
  - [ ] 7.2 Update `_bmad-output/implementation-artifacts/sprint-status.yaml` (and its mirror `implementation-artifacts/sprint-status.yaml`): `in-progress` when starting, `review` when done.
  - [ ] 7.3 Append ≥ 1 entry to `docs/ai-decision-log.md` per notable AI interaction (prompt, output, human review decision); record every correction of an AI hallucination or invariant violation.

## Dev Notes

### Decisions & discrepancies found while creating this story (read first)

1. **Folder layout follows the course guide, not the Plan-2 seed.** Planning docs say `service/{api,application,core,ports,adapters}`; Impl-1 §4 mandates `src/{domain,ports,adapters/{inbound,outbound}}`. Mapping used everywhere: `service/core → src/domain`; `service/ports/in → src/ports/inbound`; `service/ports/out → src/ports/outbound` (**`in` is a Python keyword and cannot be a package name**); `service/api → src/adapters/inbound`; `service/adapters/sim|db|llm → src/adapters/outbound/{sim,db,llm}`; `service/application → src/application`. Document this mapping in `README.md` and the walkthrough.
2. **`register(template)` is NOT a port method in this story.** `contracts.md` §3 OP-12 lists `register`, but AD-1/AD-13 and this story's DoD require *query-only* ports. Runbook registry port exposes only `get(error_code)`; templates are validated at **fixture load time** (≥ 1 step; physical-intervention ⇒ `approved_source`, D44). Registration semantics belong to Story 3.3.
3. **Epic's invariant cross-refs are off by one in places.** Story text says AD-1 → I18 and AD-13 → I22; per `contracts.md` §5 the correct mapping is AD-1 → **I1**, AD-13 → **I18** (route/import audit) and **I22** (browse cap), AD-12 → I17. Use the §5 table.
4. **Estate data is JSON fixtures, not SQL.** The epic says "SQL seed tables users/catalog/…", but `001_module12_copilot_schema.sql` contains **only Module-12-owned tables** and ARCHITECTURE §2.1 says the estate is "owned by mock providers". Do **not** invent estate tables. SQLite in this story is only the migrated Module-12 schema (used by later stories).
5. **Record ids are full `EntityKey`s** (e.g. `node#ws-gpu-11`, `user#alex`, `job#job-8823`, `policy#catalog.4.2`), matching the existing harness (`tests/support/builders.py`, `fleet.py`) and ATDD. Ports take the canonical key; the inbound adapter (story 1.5) turns bare route ids (`ws-gpu-11`) into keys.
6. **Server node VRAM:** `NodeRecord` allows no extra fields, so the 2 × 48 GB server is `gpu_memory_gb = 96` (aggregate, same convention as `tests/support/fleet.py`); the per-GPU breakdown lives in the fixture comment/README. Hostname `ws-gpu-32`.
7. **Night Policy hours:** PRD leaves them to fixture authoring (A-10). Use **22:00–06:00** (matches Impl-1 Annex 12.2 / Story 12.2); express the `night` window as concrete `Instant` start/end pair for the scenario day with `timezone` = `UTC`.
8. **Health probes are not in `openapi.yaml`.** The course requires them; the contract has none. Add `GET /healthz` and `GET /readyz` to `planning/detailed-design/schemas/openapi.yaml` under a separate `ops` tag **in the same commit** and note it in `docs/ai-decision-log.md` — this is the only permitted contract addition (no other endpoints in this story).
9. **ATDD note.** The epic lists `test/atdd/...::test_browse_state_*`/`test_get_state_record_*` as this story's ATDD path, but they call the *inbound* use-case (`CopilotInboundPort`) which lands with Story 1.5. They stay red here; this story's evidence is the new unit tests. Also expect `make test` (`red-phase` check) to need updating as ATDD tests go green — do **not** weaken ATDD tests to make them pass.
10. **React console is out of scope for Impl-1** (course track = Python/FastAPI; no `console/`). Revisit when creating Story 1.2.

### Architecture compliance (binding)

- **AD-1 / AD-13:** query-only ports; no scheduling/quota/cordon/metering method anywhere; no mutating route.
- **AD-12:** every port read returns `Ok | Failure`; failures never carry partial data.
- **R1:** `src/domain` + `src/ports` import only stdlib data types and DTOs — no `fastapi`, `sqlite3`, `datetime.now()`/`time.time()`, `random`, `uuid`, network clients.
- **R2:** time only via `clock_port`; ids only via a future `idgen_port` (not in this story).
- **R3:** domain/application never import `src.adapters.*`; the composition root (`src/bootstrap.py`) is the only place that wires adapters.
- **R4:** DTOs/port signatures use primitive-typed Pydantic DTOs only; no `Request`/`Response`/ORM rows.
- **§0.3:** records have exactly the contract fields (`extra="forbid"`).
- **Port shared preamble (§3):** P-port-1 id non-empty ≤ 200 chars → `VALIDATION_MALFORMED_BODY`; P-port-2 adapter unavailable → `PROVIDER_UNAVAILABLE`; single-record miss → `Ok(None)`; Q-port-2 no store mutation; (Q-port-3 audit rows arrive with Story 1.5 — leave a clearly-named seam, no stub audit writer).

### Port method sets (exact — `contracts.md` §3)

| Port | Methods |
|---|---|
| users | `get(id)`, `browse(q,page,page_size)`, `by_ids(ids)` |
| catalog | `get(model_id)`, `browse(...)` |
| policy | `get(clause_id)`, `for_model(model_id)`, `browse(...)` |
| groups | `get(group_id)`, `browse(...)` |
| jobs | `get(job_id)`, `select(selector)`, `browse(...)` |
| nodes | `get(node_id)`, `select(selector)`, `browse(...)` |
| reservations | `get(reservation_id)`, `browse(...)` |
| windows | `get(window_id)`, `list()` |
| event_store | `query(entity_ref, type, window)` — half-open `[start,end)`; `start<end` else `VALIDATION_MALFORMED_BODY` |
| clock | `now()` |
| policy_content | `get(source_id)` — miss → `ENTITY_NOT_FOUND` (canonical) |
| runbook_registry | `get(error_code)` only (see decision 2) |

`policy.for_model` with an unknown model → `ENTITY_NOT_FOUND`. `users.by_ids` requires every key type `user` → `VALIDATION_BAD_ENTITY_TYPE`. `select(selector)` is bounded by the 10,000-row store cap and ordered by `id` ascending.

### Fixture content (decide here, keep deterministic)

- Roles ∈ `{student, staff, faculty, privileged}`. Include at least: `user#alex` (student), `user#mateo` (student), a staff and a faculty user, one privileged.
- Catalog: `deepseek-coder` (allowed_roles excludes `student`), plus a few open models; clause `policy#catalog.4.2` (`not-in-allowlist`, text stating students are not on the allowlist), clauses sorted by `clause_id`.
- `group#group-4` (members are `user` keys), job `job#job-8823` (pending, fine-tuning, course `CS201`, constraint `night` — serves S2 and S4), ≥ 2 more `pending` CS201 jobs, a few jobs in other statuses.
- `event#evt-4711`: `access_denied`, `entity_ref=user#alex`, with `recorded_reason`.
- Nodes: 31 workstations + 1 server; all `available`/healthy **except** `node#ws-gpu-11` (`fault`, cordoned, `ERR_THERMAL_88`, health `fault`). A few reservations with `start < end`.
- Runbook template for `ERR_THERMAL_88`: ≥ 1 step; if physical intervention, `approved_source` is non-null; `steps` and `provenance` stay separate sections.
- Everything is synthetic; no real names or PII (NFR-11). Frozen scenario clock default: `2026-10-16T15:00:00.000Z` (same as `tests/support/clock.py`).

### File structure (this story creates)

```
pyproject.toml  Dockerfile  docker-compose.yml  .env.example  README.md
migrations/001_module12_copilot_schema.sql
fixtures/estate/*.json  fixtures/policy_content/*.json  fixtures/runbooks/*.json
src/
  config.py  bootstrap.py  dependency_check.py  dto.py
  domain/{result.py, entity_key.py}
  ports/outbound/{users,catalog,policy,groups,jobs,nodes,reservations,windows,event_store,clock,policy_content,runbook_registry}.py
  adapters/inbound/app.py                      # /healthz, /readyz only
  adapters/outbound/sim/{estate_loader.py, fixtures_adapter.py, clock_adapter.py}
  adapters/outbound/db/migrate.py
tests/unit/...  tests/integration/test_migrations.py  tests/api/test_health.py  tests/fixtures/nodes.json
```

Do **not** modify: `planning/**` (except the single openapi health addition, decision 8), `test/atdd/**` expectations, `tests/support/**` (reuse as-is; note the intentional duplication between `tests/support/clock.py` and `src/adapters/outbound/sim/clock_adapter.py` — prod adapter is canonical, tests may re-export later).

### Testing standards

- Pytest, `asyncio_mode = auto` (existing `pytest.ini`), strict markers; use `@pytest.mark.unit` / `integration` / `api`. **No skipped tests**, no network, no wall clock, no `sleep`.
- Every BDD scenario above ⇒ ≥ 1 test asserting response **body semantics**, not just status codes. Failure paths assert the typed `Failure.code`.
- Determinism: constructing the estate twice yields identical ordered output (hash compare).
- DoD: `pytest` green (0 skipped), `ruff check` clean, README quick-start verified from a fresh venv.

### Latest tech notes

Versions are pinned by what resolves at install time; verify with `pip index versions fastapi pydantic` and record the result. Pydantic v2 only (`model_validate`, `ConfigDict(extra="forbid")`; no v1 APIs). FastAPI: use `create_app()` factory + `lifespan`, not deprecated `@app.on_event`. Keep SQLite on stdlib `sqlite3` (≥ 3.35 for `RETURNING`/JSON1).

### Project structure notes

- Env: local Python 3.11.9; at story creation **`fastapi`, `pydantic`, `uvicorn`, `httpx`, `hypothesis`, `ruff` are NOT installed** (only `pytest` 9.0.3, `pydantic_core`, PyYAML). First action: create `.venv`, install, run the existing harness (`pytest tests`) to get a green baseline before touching code (currently fails at collection: missing `hypothesis`).
- Git: commit per task, conventional style (`feat(scaffold): …`, `feat(story-1.1): …`, `test(story-1.1): …`); **no co-author trailer**.

### References

- [Source: planning/epics.md#Story 1.1] — canonical story/ACs
- [Source: planning/detailed-design/contracts.md#3. Outbound Port Read Contracts; #4. Typed Error Catalog; #5. Invariant Binding Table]
- [Source: planning/detailed-design/ports-and-adapters.md#2. Hard Rules R1–R4; #1. Component Table]
- [Source: planning/ARCHITECTURE.md#AD-1, #AD-12, #AD-13, #Consistency Conventions, #Stack Decisions, #Structural Seed, #2.1 Read/consume entities]
- [Source: planning/detailed-design/schemas/dto.py] (§0.3 record DTOs, `ErrorBody`), [schemas/001_module12_copilot_schema.sql]
- [Source: planning/ux/C-UX-Scenarios/scenario-1.md … scenario-4.md] — S1–S4 fixture anchors
- [Source: task - impl 1 - university-ai-compute-fabric.pdf §1, §4, §5] — scaffold layout, 32-node fixtures, deliverables
- Existing harness to reuse/align with: `tests/support/{fleet,clock,builders,ids}.py`, `tests/conftest.py`

## Dev Agent Record

### Agent Model Used

_(filled by dev-story)_

### Debug Log References

### Completion Notes List

### File List
