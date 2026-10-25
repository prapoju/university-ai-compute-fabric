# AI Decision Log — Impl-1 (Module 12, AI Operations Copilot)

Provenance of AI-assisted work in the Impl-1 build: what was asked, what the AI produced, and what the
human reviewer decided. Earlier phases keep their own logs (`ai-log/decision-log.md`, `ai-log/decision-log-solu2.md`).

- **Agent:** Claude Code (BMad `bmad-agent-dev` ceremony), driven by the team through the full-ceremony skills.
- **Reviewer column:** `Juan` = the human explicitly decided in the session; `Pending` = the AI decided
  within the story's rules and the team must confirm in `bmad-code-review` / the walkthrough.
- **Category:** `Correction` (AI output was wrong and was fixed), `Refactor` (rewritten to satisfy an
  architectural invariant), `Rejected` (AI/tool suggestion declined), `Decision`, `Limitation`.

## Summary

| ID | Phase | Category | Short title | Reviewer |
|---|---|---|---|---|
| AD-01 | Setup | Correction | Non-interactive BMad installer overwrote project config | Juan (informed) |
| AD-02 | Plan | Decision | Two `epics.md` files — which one is canonical | Juan |
| AD-03 | Create story | Decision | Spec conflicts found before coding (layout, `register()`, SQL vs JSON, probes) | Juan (layout) / Pending (rest) |
| AD-04 | Build · scaffold | **Correction (invariant R1/R3)** | ruff `per-file-ignores` glob silently disabled the import ban | Pending |
| AD-05 | Build · domain | **Correction (code defect)** | Lost backslash in `\\#` escape (D61) | Pending |
| AD-06 | Build · adapters | **Refactor (AD-2 determinism)** | Readiness probe consumed clock read ids | Pending |
| AD-07 | Build · scaffold | Rejected | Library warning suggested installing unvetted `httpx2` | Pending |
| AD-08 | Build · scaffold | Decision | Lint legacy Phase-3 harness by exception, not by mass rewrite | Pending |
| AD-09 | Build · verify | Limitation → resolved | Docker build was not executable at first; verified once the daemon was up | Juan |
| AD-10 | Cleanup | Decision | Removed the generated opencode skill copies (`.agents/`, `.opencode/`) | Juan |
| AD-11 | Review | Decision | Three-layer code review of story 1.1: 3 decisions, 19 patches, 6 deferred, 7 dismissed | Juan (decisions + "apply all") |
| AD-12 | Review fix | **Correction (AI-written patch)** | The atomic-migration patch broke file databases; only Docker caught it | Pending |
| AD-13 | Review fix | Decision | PyYAML added as a dev dependency (contract route test) | Pending |
| AD-14 | Story 1.2 · create | Decision | Spec conflicts found before coding (no React console, no audit rows, wire shape, ...) | Juan (proceeded after the proposal) / Pending (rest) |
| AD-15 | Story 1.2 · build | **Correction (test tooling)** | FastAPI 0.162 wraps included routers; the route audit silently saw only the probes | Pending |
| AD-16 | Story 1.2 · build | Correction (scripted edits) | A here-doc dropped README line continuations and a script left junk in a test | Pending |
| AD-17 | Story 1.2 · build | Decision | Mutation check proved the concurrency tests can fail | Pending |

Open assumptions to confirm: see the end of this file.

---

## AD-01 — Non-interactive BMad installer overwrote project config
- **Date / phase:** 2026-10-24, setup.
- **Prompt (intent):** "Check whether BMad is installed; if not, install it" (user) → agent ran
  `bmad-method install --action update --yes --tools opencode,claude-code` to add Claude Code.
- **AI output:** installer succeeded, but silently rewrote `project_name`, `user_name`, `output_folder`,
  turned `product_languages` into a quoted string, and left 57 `.bak` files.
- **Review:** the agent diffed the result against git, recognised the "idempotent update" assumption was wrong,
  restored the six config files with `git checkout`, verified every `.bak` was identical (only CRLF/LF) and deleted them.
- **Outcome:** only the Claude Code registration in `_bmad/_config/manifest.yaml` and the new skill directories remained.

## AD-02 — Two `epics.md` files
- **Phase:** Plan (`bmad-sprint-planning`).
- **AI output:** the skill reads `{planning_artifacts}/*epic*.md`, which held a superseded 3-epic / 23-story draft
  (the agent first mis-counted it as 22 stories and corrected itself after checking). The canonical file is
  `planning/epics.md` (4 epics / 16 stories).
- **Review (Juan):** chose option A — archive the old file under `_bmad-output/planning-artifacts/archive/` and mirror
  the canonical one in its place. The existing `sprint-status.yaml` was validated against the canonical file
  (4 epics, 16 stories, 4 retrospectives) instead of regenerated.

## AD-03 — Spec conflicts found while creating story 1.1
- **Phase:** Create story (`bmad-create-story`), analysis of PRD, ARCHITECTURE, contracts, ports-and-adapters, OpenAPI.
- **AI findings (all recorded in the story's Dev Notes):**
  1. Planning uses `service/…`; the course requires `src/…` → mapping documented; `ports/in` renamed `inbound`
     (`in` is a Python keyword). **Juan approved following the course guide.**
  2. `contracts.md` OP-12 lists `register(template)` on a port that AD-1/AD-13 say is query-only → the port exposes only `get`;
     templates are validated at fixture-load time. *Pending team confirmation.*
  3. Epic says "SQL seed tables" for the estate, but the contract schema has only Module-12-owned tables → estate is JSON.
  4. Health probes (required by the course) are absent from `openapi.yaml` → added under an `ops` tag, enforced by a
     route-vs-contract test so no other endpoint can appear.
  5. Epic invariant cross-references were off (AD-1→I18, AD-13→I22); `contracts.md` §5 says I1 / I18+I22.
- **Why it matters:** each would otherwise have become a hallucinated column/endpoint or an invariant violation.

## AD-04 — ruff glob silently disabled the architecture ban  *(critical correction)*
- **Phase:** Build, Task 1 → found in Task 6.
- **Prompt (intent):** "Mirror R1/R3 in the linter: ban `fastapi`, `sqlite3`, `random`, `uuid`, … in `src/domain` and `src/ports`
  only" (story Task 6.1).
- **AI output (wrong):** `per-file-ignores = { "src/*.py" = ["TID251"] }` meant to exempt only top-level modules.
  In ruff globs `*` crosses `/`, so the ignore covered **every** file under `src/`; the ban never fired and `ruff check` was green.
- **How it was caught:** the architecture-audit test contains a self-test that runs ruff on a probe file in `src/domain`
  expecting `TID251`; it failed. Investigation showed the glob semantics.
- **Fix:** explicit paths (`src/bootstrap.py`, `src/config.py`, `src/dependency_check.py`); the self-test now guards the rule.
  After the fix `ruff check src` still passes, i.e. the pure layers really are clean.

## AD-05 — Lost backslash in the D61 escape  *(code defect)*
- **Phase:** Build, Task 2 (`src/domain/entity_key.py`).
- **AI output (wrong):** the file contained `entity_id.replace("\#", "#")` (single backslash): an invalid escape sequence, because the
  second backslash was lost when the file was written through a shell here-doc. The string value happened to be right, but Python emits
  a `DeprecationWarning` and may turn it into an error in a future version, so the D61 escape rule rested on undefined behaviour.
- **How it was caught:** the test run printed the warning; re-running with `-W error::DeprecationWarning` confirmed it.
- **Fix:** double backslash in code and docstring, and `error::DeprecationWarning` is now configured in `pytest.ini` so any future
  regression fails the suite. Files are written with the file-writing tool rather than here-docs from then on.

## AD-06 — Readiness probe consumed clock read ids  *(refactor for AD-2)*
- **Phase:** Build, Task 5 (`src/bootstrap.py`).
- **AI output (first draft):** the `clock` readiness check called `providers.clock.now()`.
- **Problem:** every `/readyz` poll advanced the simulated clock's `read_id` counter. FR-14 / AD-2 require the *N*-th read to be
  reproducible, so an external health poller would have changed citation ids (`clock#<read_id>`) between runs.
- **Fix:** `SimClock.available` (a non-consuming probe) is used for readiness; a test (`test_probing_readiness_does_not_consume_clock_read_ids`)
  asserts the first real read is still `clk-0000000000000001` after three probes.

## AD-07 — Unvetted `httpx2` suggestion rejected
- **Phase:** Build, Task 1.
- **Tool output:** Starlette's `TestClient` warns "Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead."
- **Decision:** `httpx2` was not vetted and the story forbids unvetted dependencies; the single known warning is ignored by a narrowly
  scoped `filterwarnings` entry in `pytest.ini` (message-matched, so other warnings still surface). Revisit when the team vets an alternative.

## AD-08 — Legacy test harness linted by exception
- **Phase:** Build, Task 1.
- **Observation:** the first `ruff check` reported 32 findings, 28 of them in the Phase-3 harness (`tests/support/**` and early tests).
- **Rejected approach:** `ruff --fix` / reformatting the whole repo — it would bury story work in unrelated diffs and alter files the story says not to modify.
- **Decision:** per-file style exceptions for exactly those legacy files; all new code is held to the full rule set (`E, F, I, B, UP, TID`).

## AD-09 - Docker build not executed, then verified
- **Phase:** Build, verification.
- **First pass:** `docker compose config` validated the file, but the Docker daemon was not running, so the image build and container run
  were **not** executed; the agent did not start Docker Desktop on its own. Compensating evidence at that time: a clean `git clone` -> new venv ->
  `pip install -e ".[dev]"` -> `python -m src.dependency_check` -> `pytest` (258 passed) -> `ruff` -> `uvicorn` + `/healthz` + `/readyz`.
- **Resolution (Juan started Docker):** `docker compose up --build -d` built the image and the container reached `healthy`;
  `GET /healthz` -> `{"status":"ok"}` and `GET /readyz` -> `{"status":"ready","checks":{"dependencies":"ok","migrations":"ok","estate":"ok","clock":"ok"}}`.
  The stack was then removed with `docker compose down -v`.

## AD-10 - Generated opencode skill copies removed
- **Phase:** Cleanup after story 1.1.
- **What they were:** the BMad installer, because the original manifest lists `opencode`, also generated `.agents/skills` (66 skills, ~7.8 MB) and
  `.opencode/commands`. Claude Code only reads `.claude/skills`, so these were byte-for-byte duplicates for another assistant.
- **Problem:** the agent had committed them (`462597c`); their very deep paths made a plain `git clone` fail on Windows from a long parent
  directory ("Filename too long"), which contradicts the "clone and run" requirement.
- **Decision (Juan):** remove them from the repository and ignore them in `.gitignore`. They can be regenerated at any time with
  `npx bmad-method install --action update --tools opencode`; history keeps the original commit.

---

## AD-11 - Three-layer code review of story 1.1
- **Phase:** Review (`bmad-code-review`), same model as the build (the user chose not to switch models because of usage), so independence
  comes from three reviewers started with no conversation context: Blind Hunter (diff only), Edge Case Hunter (diff only) and Acceptance Auditor
  (diff + story + contracts). Scope: `src/` without the verbatim `dto.py`, `tests/`, and the config files (~3,600 diff lines).
- **AI output:** about 60 raw findings across the three reports. Nothing was taken at face value: the agent read the code at each location and
  reproduced the doubtful cases in Python before rating (e.g. `load_estate` raising `TypeError` on a null `text`, an event dated `2026-02-30`
  breaking every query, `GET /nope` returning `{"detail": ...}`).
- **Triage result:** 3 decisions, 19 patches (2 high, 8 medium, 9 low), 6 deferred, 7 dismissed with reasons (written in the story's
  *Review Findings* section and `deferred-work.md`).
- **Human decisions (Juan):** startup gate = hybrid (abort on Python/SQLite/package problems, keep serving `/readyz` 503 when only fixtures
  are missing); the provisional selector vocabulary is deferred to story 2.2; the framework-generated `/docs`, `/redoc`, `/openapi.json`
  are disabled so the app serves exactly the contract routes; and "apply all patches".
- **Notable corrections that came out of it:** `load_estate` now never raises (strict policy-content model); impossible dates are rejected in
  settings and in every Instant field of the estate; the SimClock counter is lock-protected; the architecture audit now tracks aliases,
  relative imports and `from src import adapters` (22 self-tests), and the exact-route contract test also sees routes that are not `APIRoute`s.

## AD-12 - The atomic-migration patch broke file databases  *(correction of an AI-written patch)*
- **Phase:** review fixes, group 3 ("startup robustness").
- **AI output (wrong):** to make a migration all-or-nothing, the runner wrapped the whole SQL file in `BEGIN; ... COMMIT;`. The contract schema
  starts with `PRAGMA journal_mode = WAL;`, which SQLite refuses inside a transaction ("cannot change into wal mode from within a transaction")
  - but only for a *file* database. All unit and integration tests used `:memory:`, where the pragma is silently ignored, so 297 tests stayed green.
- **How it was caught:** the Docker re-verification after the patch round: `/readyz` answered 503 with the exact SQLite error.
- **Second error while fixing it:** the first version of the PRAGMA splitter used `$` in a multiline regex and missed the pragma lines because
  the schema file has CRLF line endings on Windows.
- **Fix:** PRAGMA lines are applied first and the DDL plus its bookkeeping row stay atomic; new tests migrate a real file database (WAL
  enabled, idempotent restart) and run the splitter with both `\n` and `\r\n`. Lesson recorded: any test of a persistence path must also run on a file.

## AD-13 - PyYAML as a dev dependency
- **Phase:** review fixes (finding raised by the Acceptance Auditor: the story required a log entry for any dependency beyond its list).
- **What:** `PyYAML>=6.0` is declared in the `dev` extra. It is used only by `tests/api/test_contract_routes.py` to read `openapi.yaml` and
  compare the served routes against the contract. It is a mature, ubiquitous library, is not a runtime dependency and ships no code in the service.

---

## AD-14 - Story 1.2: spec conflicts found before coding
- **Phase:** Create story (`bmad-create-story` for 1.2), analysis of epics, contracts section 2, openapi, dto.py and the migrated schema.
- **AI findings (written as D1-D10 in the story's Dev Notes):**
  1. The canonical story lists a React console; the course track is Python/FastAPI. The console is out of scope, the 1,000-character cap is
     enforced on the server and the answer chain is the `answer_chain` field. (The agent proposed this before building; Juan asked to continue.)
  2. contracts.md Q3 wants a `toolcall.*` audit row per call, but the audit writer is story 1.5 (outside the Impl-1 scope): no audit rows are
     written, and the walkthrough must say NFR-8 "every tool call audited" is unmet until 1.5.
  3. The contract says a canonical body has an `error_code` field; `dto.py` and openapi use `code`. The DTO wins.
  4. `SubmitQueryRequest.query_text` is a `QueryText`, which would reject empty/over-long input as a generic error, yet the contract requires
     `VALIDATION_EMPTY_QUERY` / `VALIDATION_QUERY_TOO_LONG` with their own messages: a local request model plus domain validation.
  5. The epic mentions a SQL `turns` table; the schema has none. Turns are the session's `answers` rows.
  6. FR-02 follow-ups are scoped to the *intent* (entity resolution is story 1.3 / 3.4).
  7. Two ports that no contract defines for Module 12's own storage were added: OP-13 `IdGenPort` (contracted) and an internal `SessionStorePort`.
- **Build-time decisions to confirm at review:** a query to a *reset* session returns 410 and persists `status = expired` (contract P2 taken
  literally, so a later GET shows `expired`, not `reset`); a clarification is stored with `intent = "clarification"` and the 200 `ErrorBody` is
  what goes on the wire; the simulated clock is frozen in Docker (`M12_CLOCK_START`), so idle expiry only occurs when a test advances it.

## AD-15 - The route audit went blind to the new routes  *(correction of test tooling)*
- **Phase:** Build, Task 5 (session REST endpoints).
- **What happened:** the story-1.1 audit enumerated `app.routes` and compared it with the contract. After `include_router(...)` the audit
  still listed only `/healthz` and `/readyz`: this FastAPI version (0.162) wraps included routers in an `_IncludedRouter` object whose routes
  are not `APIRoute` instances at the top level. The equality assertion happened to fail (it listed the declared-but-"unserved" routes), but an
  audit written only as "served is a subset of declared" would have kept passing while no longer seeing the real endpoints.
- **Fix:** the audit now flattens included routers recursively and cross-checks the result with `app.openapi()` (the schema FastAPI
  generates from the same routes); the route list of the story is explicit, so a missing or an extra endpoint both fail.

## AD-16 - Scripted edits corrupted two files
- **Phase:** Build, Tasks 5-6.
- **What happened:** (a) a shell here-doc used to edit the README turned `\` + newline into spaces, merging the multi-line `curl` examples;
  (b) a scripted replacement left a junk placeholder (`assert {type(None)} or True`) in an existing test while the real assertion was being
  rewritten. Both are the same class of failure as story 1.1 (AD-05): editing through shell strings.
- **How they were caught:** reading the README back after `ruff` passed, and re-reading the test when its name no longer matched what it asserted.
- **Fix:** restored the line continuations with the file-edit tool and replaced the placeholder with the real assertion (the twelve provider
  ports are registered, the session ring only adds ports).

## AD-17 - Mutation check on the concurrency tests
- **Phase:** Build, Task 7 (NFR-6).
- **What:** the concurrency tests passed on the first run, which proves nothing by itself. A throw-away mutation disabled the per-session lock
  and the "60 parallel queries in one session" test failed on both `:memory:` and file databases (lost updates), so the test can fail for the
  right reason. The mutation script lives outside the repository.

---

## Open assumptions to confirm at review
1. `Selector.method == "filter"` (equality filter over record fields) is an adapter convention invented for `select()`; the contract only
   says "method + params". Decided with the user: deferred to story 2.2 (dry-run snapshot), where it is confirmed or replaced.
2. Port `browse` returns `list[Record]` exactly as `contracts.md` §3 says, but the inbound `browse_state` response needs a `total`.
   Story 1.5 will need a contract-level decision (count method or a page type).
3. The 2 × 48 GB server is stored as `gpu_memory_gb = 96` because `NodeRecord` forbids extra fields.
4. Night Policy hours are 22:00–06:00 UTC (PRD leaves fixture values open, A-10).
5. Unexpected exceptions degrade to `PROVIDER_UNAVAILABLE` (503) because the error catalog has no generic internal-error code (AD-12 safe failure).
6. A query to a reset session is 410 and persists `status = expired` (contracts.md P2 read literally); a later GET shows `expired`.
7. Clarification turns are stored as `intent = "clarification"`, `canonical = "CLARIFICATION"`; the wire body is the 200 `ErrorBody` (D58).
8. The simulated clock does not advance by itself (`M12_CLOCK_START`), so the 30-minute idle expiry is only exercised by tests that advance it.
