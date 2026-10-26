# Impl-1 Walkthrough - Module 12: AI Operations Copilot

Working code for the Impl-1 delivery of the **AI Operations Copilot** (Python 3.11, FastAPI, SQLite, Ports & Adapters).
Run it with `docker compose up --build` or `pip install -e . && pytest`. Decisions, AI corrections and process notes are in
[`docs/ai-decision-log.md`](docs/ai-decision-log.md) (26 entries); sprint progression is in
[`implementation-artifacts/sprint-status.yaml`](implementation-artifacts/sprint-status.yaml).

## 1. Scope delivered

| Part | Story | Annex | Status |
|---|---|---|---|
| Scaffold | 1.1 Fixture estate and read-only adapter ring | - | done |
| Scaffold | 1.2 Session store and conversational intake | - | done (3-layer review) |
| Core | 1.3 Entity resolution and access-denial diagnosis | 12.1 | done (3-layer review) |
| Core | 3.1 Schedule and window diagnosis | 12.2 | review |
| Core | 4.1 Anti-fabrication guardrail and content hygiene | 12.3 | review |

Everything else in `planning/epics.md` stays `backlog` for Impl-2 (stories 1.4, 1.5, the whole of Epic 2, 3.2-3.4, 4.2, 4.3).
Stories 3.1 and 4.1 were deliberately kept to the annex behaviour and were not put through the subagent review (decision log AD-23); they
stop at `review` for that reason.

## 2. Architecture (hexagonal)

```
src/
  domain/        pure rules: intent routing, references, diagnosis, window_diagnosis, prose_guard,
                 canonical_strings, error_catalog, instants, entity_key, result      (no I/O, no clock, no ids)
  ports/
    inbound/     SessionUseCases (the REST adapter's only dependency)
    outbound/    12 read-only provider ports + SessionStorePort, IdGenPort (OP-13), LlmProsePort (OP-14)
  application/   AnswerPipeline, SessionService, EntityResolver, EvidenceAssembler,
                 AccessDenialHandler, WindowDiagnosisHandler, turn_support (guarded prose, claim ids, canonical turns)
  adapters/
    inbound/     FastAPI app, session routes, health/readiness, typed ErrorBody
    outbound/    db/ (SQLite store, migrations)   sim/ (fixtures, clock, id generator, prose writer)
  bootstrap.py   the only composition root         config.py   env-driven settings
```

Rules enforced by tests: the domain/ports/application rings import no adapter, `sqlite3`, `fastapi`, `random`, `uuid` or wall clock (AST audit +
ruff `TID251`); every provider port is query-only; the registered routes equal the ones in `planning/detailed-design/schemas/openapi.yaml`
(plus `/healthz`, `/readyz`). The estate is read-only: a snapshot is compared after bursts of turns.

How a turn flows: `POST /api/v1/sessions/{sid}/queries` -> `SessionService` (per-session guard, one clock read) -> deterministic intent rules ->
handler -> resolver (exact, case-folded, never fuzzy) -> provider reads -> **pure diagnosis** (class, claims, citations, evidence order) ->
the simulated LLM writes connective prose **once**, the prose guard rejects any fact in it (one retry, then `LLM_PROSE_REJECTED`) -> the answer and its
evidence/claims/citations are stored in one transaction. The LLM never decides or states a fact (AD-2, AD-8).

## 3. Endpoints (identical to the OpenAPI)

| Method and path | Purpose |
|---|---|
| `POST /api/v1/copilot/query` | **annex 12.1 inbound**: body `{ "query": "..." }`; opens a session and answers like `submit_query` (stored, readable via `GET /sessions/{sid}`) |
| `POST /api/v1/sessions` | open a session (201) |
| `POST /api/v1/sessions/{sid}/queries` | ask a question; a diagnosis is 200 `AnswerEnvelope`, a canonical outcome is 200 `ErrorBody` |
| `GET /api/v1/sessions/{sid}` | context and stored turns, with evidence and claims |
| `DELETE /api/v1/sessions/{sid}` | reset (204) |
| `GET /healthz`, `GET /readyz` | liveness; readiness per dependency (dependencies, migrations, estate, clock, sessions) |

Errors are typed `ErrorBody` JSON: 400 malformed/empty/over-long query, 404 unknown session, 410 reset/expired session, 503 provider failure
(`PROVIDER_UNAVAILABLE`, `CLOCK_UNAVAILABLE`, `LLM_UNAVAILABLE`, `LLM_PROSE_REJECTED`). The DTOs are a verbatim copy of the contract (`extra="forbid"`).
The annex route `/api/v1/copilot/query` was added to `openapi.yaml` (and to the route audits) once the annex text was confirmed (AD-26); it
reuses the session use cases, so the sessions API and the annex endpoint return the same answers.

## 4. Database

SQLite, one migration (`migrations/001_module12_copilot_schema.sql`) applied at start-up. Used by the delivered stories: `sessions` (context as JSON),
`answers`, `evidence` (ordered by `position`), `claims`, `claim_citations` (FK to the evidence of the same answer). The 32-node estate, users,
groups, jobs, policy clauses, windows and events are JSON fixtures behind the read-only ports (`fixtures/estate/`). `docker-compose.yml` keeps the
database on a volume, so sessions survive a container restart.

## 5. The three scenarios

**12.1 Access denial (story 1.3).** `why was alex denied deepseek-coder` -> class `access_denial_not_in_allowlist`, chain
`observation -> evidence -> diagnosis`; claims state Alex's role (`student`), the clause `policy#catalog.4.2` with rule `RULE-CAT-04` and its text,
the reason class and the denial event `event#evt-4711`; evidence = user, model, policy, event, clock read. `and what about mateo?` reuses the model from the
session. An unknown user is `ENTITY_NOT_FOUND`; a student with no recorded denial is `CANNOT_CONFIRM`.

**12.2 Night schedule (story 3.1).** `why can't group 4 run their fine-tuning job right now` at `2026-10-16T15:00:00.000Z` -> class
`schedule_window_restricted`: job `job#job-8823` is constrained to `window#night`; the next open window is `2026-10-16T22:00:00.000Z` to
`2026-10-17T06:00:00.000Z` (UTC), stated in the claims and returned as `recommendation.next_open_window` (chain
`observation -> evidence -> diagnosis -> recommendation`, as in `planning/ux/EXPERIENCE.md`). The window is half-open `[start, end)`; past the only
recorded window the answer stays restricted with `next_open_window: null` and says no later window is on record (contracts.md Q1, D55); a group with no
constrained job gets `schedule_no_constraint` and `next_open_window: null`; a failed clock read is a 503 and no window is invented.

**12.3 No invented entities (story 4.1).** `why was ghost_user_99 denied deepseek-coder` -> `200 ENTITY_NOT_FOUND`,
`Entity Not Found in State: user#ghost_user_99.`, with no claims, evidence or diagnosis. The same holds for a non-existent model, group or `policy#...`.
Instruction-like text inside records or in the query never changes a diagnosis.

Docker run of the three scenarios (`docker compose up --build`, `GET /readyz` all `ok`):

```
Q: why was alex denied deepseek-coder
   access_denial_not_in_allowlist | The reason class is not-in-allowlist, recorded by event#evt-4711: not-in-allowlist: policy#catalog.4.2.
Q: why can't group 4 run their fine-tuning job right now
   schedule_window_restricted | The next open window starts 2026-10-16T22:00:00.000Z and ends 2026-10-17T06:00:00.000Z (UTC).
Q: why was ghost_user_99 denied deepseek-coder
   ENTITY_NOT_FOUND | Entity Not Found in State: user#ghost_user_99.
```

## 6. Test evidence

```
$ pytest -q                 956 passed, 0 skipped   (unit 784, integration 74, api 95)
$ ruff check src tests      All checks passed!
```

| Story | New test files | What they prove |
|---|---|---|
| 1.1 | `test_fixture_estate`, `test_story_1_1_read_only`, `test_ports_query_only`, `test_architecture_imports`, `test_contract_routes` | 32-node estate, read-only ports, ring boundaries, route audit |
| 1.2 | `test_intent`, `test_session_service`, `test_session_store`, `test_sessions`, `test_sessions_wiring`, `test_sessions_concurrency` | routing, lifecycle, atomic persistence, restart, parallel turns |
| 1.3 | `test_references`, `test_diagnosis`, `test_prose_guard`, `test_entity_resolver`, `test_access_denial_handler`, `test_access_denial_api` | exact resolution, cited diagnosis, prose guard and retry, canonical outcomes, follow-ups, 503 stores nothing |
| 3.1 | `test_window_diagnosis`, `test_window_diagnosis_handler`, `test_window_diagnosis_api` | S2, half-open boundary, no constraint, missing group/window/clock, 10 phrasings |
| 4.1 | `test_anti_fabrication`, `test_anti_fabrication_api` | 12 imaginary references, injection parity on records and query, annex edge case over HTTP |
| annex 12.1 route | `test_copilot_query` | the annex payload on `POST /api/v1/copilot/query`, structured 400s, other scenarios on the same endpoint |

## 7. Process and AI use

The BMad cycle was run per story (sprint planning, create-story, dev-story, code-review, sprint-status updates) with a commit per phase
(`git log --oneline`). `docs/ai-decision-log.md` records 26 entries, including these AI mistakes caught and corrected:

* a database migration that broke file databases (found only by running Docker) - AD-12;
* route audit blind to included routers - AD-15;
* force-routing of out-of-domain questions, an undetected destructive request, and an ordering race (story 1.2 review) - AD-18;
* claim ids not seeded after a restart (story 1.3 build) - AD-20;
* a stale follow-up entity, an unbacked clause hiding a confirmed denial, substring clause matching, a prose guard that a display name could
  disable (story 1.3 review and story 4.1) - AD-22, AD-25;
* the architecture ban silently disabled by a ruff glob - AD-04;
* tool-corruption of files by scripted edits, four times (AD-05, AD-16, AD-22, AD-25).

## 8. Known limits

* The LLM is a deterministic simulation (no Ollama); the prose guard is lexical, so inflections and homoglyphs of a fact can pass (deferred, AD-22).
* The React console, the tool-call audit log and the state-inspection viewer (stories 1.4, 1.5) are Impl-2; no audit rows are written yet.
* The simulated clock is frozen at `2026-10-16T15:00:00.000Z` unless a scenario advances it.
* Stories 3.1 and 4.1 were not code-reviewed with subagents; the ATDD stub tests of the course template stay red by design.
