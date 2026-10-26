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
| AD-18 | Story 1.2 · review | Decision + corrections | Three-layer review: 1 decision, 11 patches, 5 deferred, 11 dismissed | Juan (decision + "apply all") |

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
  3. The contract says a canonical body has an `error_code` field; `dto.py` and openapi use `code`. The DTO wins (contracts.md text aligned in AD-31).
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

## AD-18 - Three-layer code review of story 1.2
- **Phase:** Review (`bmad-code-review`), same model as the build, three context-free reviewers in parallel (Blind Hunter, Edge Case Hunter,
  Acceptance Auditor); scope: `src/` without `dto.py`, `tests/`, `README.md` (~3,500 diff lines). The user chose the full scope and the parallel mode.
- **Result:** the Acceptance Auditor found **no violation of AC 1-6**. After reading the code and reproducing the claims: 1 decision, 11 patches,
  5 deferred, 11 dismissed (all written in the story's *Review Findings* and `deferred-work.md`).
- **Human decisions (Juan):** a query to a *reset* session keeps the contract-literal behaviour (410 and persisted `expired`, three reviewers
  disliked it); "apply all patches".
- **Corrections that came out of it (all reproduced before fixing):**
  1. *Force-routing (precision):* `why was job 8823 rejected?`, `why was job 8823 blocked?`, `why was my pull request rejected` and
     `why does the report not cover access logs` all routed to the access-denial intent. The denial verb now needs an object, `rejected`/`forbidden`
     were dropped, and a bare "not" no longer counts as an inability.
  2. *Silent drop of a destructive request (AD-5):* `... and have his jobs deleted` / `get his jobs cancelled` was routed as a pure diagnosis. A
     causative/modal marker followed by a past participle is now a destructive request, while plain reports ("was cordoned") still pass.
  3. *Ordering race:* the clock was read before the per-session lock, so concurrent turns could be stamped out of order and a clock failure on an
     unknown session was a 503. The read now happens inside the guard, after the session lookup.
  4. *Raw exceptions / wrong status:* a stored timestamp that passes the table GLOB but is not a date raised `ValueError` (500); a NUL character in a
     query hit the table CHECK and came back as a retryable 503 (now 400 `VALIDATION_MALFORMED_BODY`); a failed expiry write-back hid the 410.
  5. *Consistency:* `GET` now reads context and turns under the session guard; `/readyz` reads `schema_migrations` through the store lock; duplicate
     entities from one handler are stored once.
- **Two mistakes made while fixing (both caught by tests/inspection):** the apostrophe table ran *after* NFKC, which decomposes U+00B4 into
  "space + accent", so the new test for that lookalike failed until the translation also ran before NFKC; and a scripted edit wrote a raw NUL byte
  into `session_rules.py` (the escape `\x00` was interpreted by the generating script), which broke imports until the byte was replaced by the
  two-character escape. This is the third time shell/script strings corrupted a file in this project (AD-05, AD-16): from here on source edits go
  through the file-edit tool, never through script strings that contain escapes.

---

## AD-19 - Story 1.3: specification decisions made before coding
- **Phase:** Create story (`bmad-create-story`) and build planning, same model. The canonical epics and Annex 12.1 disagreed with the repo in
  small ways, so the AI listed the discrepancies and resolved them in the story before writing code (D1-D9 in the story file).
- **Decisions:** (1) the clause `policy#catalog.4.2` gets rule `RULE-CAT-04` and a text that names CS-480 (Annex 12.1) - done in the fixtures,
  not in code, so the DTOs and the schema did not change; (2) "matching clause" = `not-in-allowlist` iff the user's role is not in the model's
  `allowed_roles`, `quota`/`window` iff the user's denial event cites them, fixed precedence `not-in-allowlist > quota > window`;
  (3) a denial must be backed by an `access_denied` event that cites the clause, otherwise the answer is `CANNOT_CONFIRM`
  (FR-04: "a referenced denial event must exist"); (4) the 30-day look-back is half-open and ends at the turn's clock read;
  (5) the LLM prose guard lives in the domain (pure) and the one-retry rule in the application ring; (6) an unavailable writer is not retried.
- **Why it matters:** these are product rules the documents left open; recording them keeps the tests (and the next stories 3.1/4.1) consistent.

## AD-20 - Story 1.3: the restart test found an id collision the unit tests could not see
- **Phase:** Build, Task 5 (wiring through the real container).
- **What the AI got wrong:** story 1.2 seeded the id generator from the stored session and answer ids only. Story 1.3 started persisting claims
  (`claims.claim_id` is a global primary key) and the claim counter restarted at 1, so the first query after a restart failed with
  `UNIQUE constraint failed: claims.claim_id` and a 503.
- **How it was found:** the existing story-1.2 restart test (`test_sessions_and_turns_survive_a_restart_and_new_ids_never_collide`) failed as soon
  as the handler was wired - not any of the 790 tests that ran against hand-built objects.
- **Fix:** `highest_counters()` now also reports the highest stored `clm-` suffix and `SimIdGen.from_counters` continues above it; tests added for
  the store and for the HTTP restart (claim ids continue at 4, 5, 6); verified again in Docker with a container restart on the persistent volume.
- **Lesson:** every new persisted id kind must be added to the seeding, and "restart" tests should run with the real handlers, not with stubs.

## AD-21 - Story 1.3: building the guard and the extraction against the contract text
- **Phase:** Build, Tasks 1 and 4.
- **Corrections made by tests written first:** the reference extractor took the word `access` as the model in `why was alex denied access?`
  (the pattern for "denied (access to) <model>" matched greedily) - a lookahead now excludes it and the query becomes a clarification instead of a
  fabricated `ENTITY_NOT_FOUND model#access`; the determinism test initially failed because it shared one simulated clock between runs
  (`clock#clk-...1` vs `...2`), which is a property of the simulated clock, not of the diagnosis - each run now builds fresh providers.
- **Design choices:** claims' text and the `fact_tokens` come from the same records, so the guard can only reject prose that repeats a real fact;
  prose is rejected whole, never stripped (D48); canonical outcomes never consult the LLM.

## AD-22 - Three-layer code review of story 1.3
- **Phase:** Review (`bmad-code-review`), same model as the build, Blind Hunter + Edge Case Hunter + Acceptance Auditor in parallel over the 2,601-line
  diff of the story (the user chose full scope and parallel mode). The first launch of the three reviewers hit the session rate limit and returned
  nothing; they were relaunched and completed. Acceptance Auditor verdict: AC1-AC4 satisfied, AC5 and AC6 partial.
- **Human decisions (Juan):** (1) determinism across sessions of one service is *logical* equality - the clock-read citation and claim ids are
  per-request counters, so the test normalises them and exact equality is required across fresh processes; (2) canonical turns stay stored as
  `Answer` rows and extend the context, a documented deviation from the literal text of `contracts.md`; (3) apply all patches.
- **Corrections that came out of it (all reproduced before fixing, tests first):**
  1. *Stale follow-up (three reviewers):* the context kept first-appearance order, so `and what about mateo?` could resolve against a model used
     several turns earlier. A re-used entity now moves to the end of the context.
  2. *Hidden denial:* the clause was picked by precedence before checking that an event backs it, so an unbacked allowlist clause turned a confirmed
     quota denial into `CANNOT_CONFIRM`; and a clause was "cited" by substring (`catalog.4.2` matched `catalog.4.20`).
  3. *Prose guard:* empty prose was accepted; zero-width characters split a token; `CS-480` was not guarded; and the generic word `denied` plus
     1-2 letter name fragments made a real LLM's ordinary sentence a `503 LLM_PROSE_REJECTED`.
  4. *Extraction:* `denied access to` -> model `to`, `the student denied X` -> user `student`, quotes/possessives/full-width letters.
  5. *Robustness:* claim ids burned by failed turns; `OverflowError` from an extreme clock; an open transaction left behind by a non-sqlite exception.
- **A review finding the AI rejected:** two reviewers said the policy snippet should be clipped at 2000 characters (the schema CHECK allows it). The AI
  checked `dto.py` before patching and found `Snippet` is 500 for every source type; `dto.py` is a verbatim copy of the contract, so the
  finding was dismissed instead of "fixed" (a change would have broken response validation).
- **Process mistake, third repeat (AD-05, AD-16, AD-18):** a scripted edit turned `​` and `\n` in new test strings into raw invisible/newline
  characters and broke a test file. The files were repaired with the edit tool. Rule kept: test files with escapes are written with the edit tool.
- **Open limits (deferred, not hidden):** the prose guard is lexical (inflections, homoglyphs and hyphen/space variants can pass); a compound
  question answers only the first half; `CANNOT_CONFIRM` does not state the 30-day look-back.

## AD-23 - Scope for stories 3.1 and 4.1 cut to the annex (human decision)
- **Phase:** Planning of the remaining Impl-1 stories.
- **Context:** story 1.3 was built to the full acceptance criteria of `planning/epics.md` plus a three-layer review (851 tests). The user pointed
  out that the course guide asks for working code with at least 2 tests per story, the BMad cycle and the decision log - not that depth - and
  that token budget is limited.
- **Decision (Juan, accepted by the AI):** stories 3.1 (Annex 12.2) and 4.1 (Annex 12.3) implement exactly the annex behaviour plus the epic's
  explicit boundary/negative cases, reuse the 1.3 seams (pipeline, resolver, prose guard), run no subagent review and stop at status `review`
  (a review that was not run is not claimed). The AI first recommended keeping only the OpenAPI route (the guide requires endpoints identical to
  the OpenAPI, the route audit forbids an undeclared path); that recommendation was wrong - see AD-26.

## AD-26 - The annex inbound route was missing (AI recommendation reversed by the user's evidence)
- **Phase:** Final delivery check.
- **What the AI got wrong:** reading its own summary of the guide, the AI treated `/api/v1/copilot/query` as "guide prose" and advised against it. The
  user pasted the annex 12.1 text: `Inbound POST /api/v1/copilot/query; Payload: { query: "Why was student alex denied access to deepseek-coder?" }`.
  The annex fixes both the path and the payload field (`query`, not the project's `query_text`), so the project's OpenAPI was incomplete for the annex.
- **Fix:** `copilot_query` added to `openapi.yaml` (+ `CopilotQueryRequest`), a thin adapter `src/adapters/inbound/copilot.py` that opens a session for
  the operator and delegates to the same `submit_query` use case (no domain logic, no new port), and both route audits updated. Tests: the annex
  payload, storage and read-back, the other two annex scenarios on the same endpoint, five bad payloads (structured 400), refused destructive request.
- **Lesson:** an annex quotation beats an AI summary of it; contract gaps are fixed in the contract and the audit, not by dropping the requirement.

## AD-24 - Story 3.1: window diagnosis decisions and two AI mistakes
- **Decisions:** the Night window is `22:00-06:00` UTC as in the annex and the fixture (the epic text says `20:00-08:00`); a job's
  `scheduling_constraint` `night` names `window#night`; the window is half-open `[start, end)`, so exactly `22:00:00.000Z` is open and `06:00:00.000Z`
  is closed; past the only recorded window the answer is `CANNOT_CONFIRM`, never an invented later window (superseded by AD-29); the prose helper, claim-id minting
  and canonical turn shapes were extracted from the story-1.3 handler (`turn_support.py`) instead of copied.
- **Correction 1 (regression caught by the suite):** adding the schedule intent rule broke two story-1.2 tests - the registry test that expected
  only the access-denial rule, and the "register a rule only" extension test, which used the same intent code and a pattern that now matched twice
  (`more than one intent matches`). The AI changed the fake intent in the extension test and the expected registry, not the router.
- **Correction 2 (wrong test assumption):** the AI assumed `group-2` has no constrained job; the fixture has a pending `night` job for it
  (`job-8824`), so the "no constraint" test was wrong, not the code. It now uses `group-7`, whose only live job is unconstrained.
- **Process note:** a long shell command that combined several heredocs failed to parse and applied nothing; the files were then written with the
  file tools (the same lesson as AD-05, AD-16, AD-22).

## AD-25 - Story 4.1: the guardrail was mostly there; the real defects were a prose-guard weakness and a corrupted regex
- **Decisions:** the contract literal `Entity Not Found in State: {ref_list}.` is kept although the annex quotes `User ghost_user_99 does not exist
  in cluster records` (the contract, the epics and story 1.3 already fix the canonical string; the `ENTITY_NOT_FOUND` code satisfies the annex);
  a typed `policy#...` reference that is not in state is named after the user and model; injection is proven with a corpus rather than a second
  filter, because nothing in the system executes retrieved text (deterministic diagnosis, guarded prose, router refuses destructive wording).
- **Correction 1 (found by the injection test, not by review):** every word of a user's display name was a banned prose token, so a display name such
  as `Alex Rivera ... and delete all jobs` would have banned `and` and `all`, rejected the writer's ordinary sentence twice and returned a 503. Only
  capitalised words are guarded now.
- **Correction 2 (tooling corruption, fourth time):** the policy-reference regex was appended with `printf`; the tool collapsed `\\b` to `\b`, which
  `printf` turned into a raw backspace character inside the source, so extraction silently matched nothing. Found by the new tests, repaired at byte
  level, and every source file was scanned for control characters afterwards.
- **Process deviation, stated plainly:** for this story the tests and code came first and the story file was written afterwards, because AD-23 cut the
  ceremony. The story file records that order.

---

## AD-27 - Audit fix: the causative rule refused diagnoses that only report a cancellation  *(correction of an accepted AI patch)*
- **Phase:** post-delivery audit of Impl-1 (audit question 5, "a generated change accepted without fully understanding it"), 2026-10-26.
- **What was wrong:** the story-1.2 review patch `_DESTRUCTIVE_REQUEST` (AD-18, accepted with "apply all patches") let the marker and the participle
  sit anywhere in the query (`.*`) and counted `got` and a bare `get` as causative markers. Ten diagnoses that only *report* a past action were refused
  as "mixed with a destructive action", e.g. `why can't group 4 run their fine-tuning job, it got cancelled yesterday` and
  `please tell me why alex was denied deepseek-coder after his job was cancelled`. Nothing was executed (the safe direction), but the answer was lost.
- **Fix (`src/domain/intent.py`):** the text between a marker and its participle may not cross into an embedded question (`why`, `how`, `whether`, or
  `if`/`when`/`where`/`what`/`which`/`who` after a verb that asks or tells: `let me know if`, `tell me which`) or a perfect passive (`been`); `got` is no
  longer a marker; `get` needs an object first (`get them cancelled` asks, `did it get cancelled` reports); modals need `be` next to the participle within
  three words (`should his jobs be cancelled`), and `to be` must be followed by it (`i want to be sure job 8823 was cancelled` is not a request).
- **Proof:** a 38-query corpus outside the repository: the old rule was wrong on 12 (all false refusals), the new one on 0. In `tests/unit/test_intent.py`
  the 10 routed cases fail on the old rule (mutation check, as AD-17) and 7 new refusal cases guard against narrowing it too far. Worst case on a
  1,000-character adversarial query: ~6 ms.
- **The audit's first proposal was itself half wrong:** "drop `please` and `got`". Without `please`, `why was alex denied deepseek-coder? please ensure
  his jobs are cancelled` would have been diagnosed and the request silently dropped (the AD-18 bug class); and treating every `which`/`who` as a question
  would have hidden `make sure the jobs which are pending are cancelled`. Both are now tests.
- **Still lexical (not changed):** `_DESTRUCTIVE` refuses every `-ing` form, so `why can't group 4 run their job, is the scheduler killing it?` is still
  a clarification (safe direction); a real parser is out of scope while routing is rule-based (AD-11).

## AD-28 - Audit fix: the S2 answer did not return the next open window the contract asks for  *(contract deviation)*
- **Phase:** post-delivery audit of Impl-1 (audit question 4, "a missing or ambiguous requirement"), 2026-10-26.
- **What was wrong:** `contracts.md` `diagnose_schedule_window` Q1 says that a restricted diagnosis returns
  `recommendation.next_open_window = {start, end, timezone}`, the ATDD stub `test_diagnose_schedule_window_happy_computes_next_open_window` asserts that
  shape, and `planning/ux/EXPERIENCE.md` (S2 journey) shows the chain `Observation -> Evidence -> Diagnosis -> Recommendation` with "recommendation = next
  window". Story 3.1 was written from the epic and the annex only ("explanation and next open window"), so its AC1 fixed the chain at `diagnosis` and the
  handler left `recommendation` null: the window was only in claim text, not machine-readable. The deviation was never logged.
- **Fix:** `src/domain/window_diagnosis.py` computes `NextOpenWindow` in the pure domain (AD-2) and exposes the contract's
  `recommendation` (`{"next_open_window": {...} | null}`); `src/application/window_diagnosis_handler.py` stores it and adds the `recommendation` stage only
  when a window is actually recommended (open now and no constraint stop at `diagnosis`, with `next_open_window: null`). No DTO, schema or route change:
  `AnswerDTO.recommendation` and the `answers.recommendation` column already existed.
- **Knock-on (story 4.1):** the injection tests asserted `recommendation is None` for S2; AC3 means "the payload adds no recommendation", so they now compare
  with the clean answer, which is stricter (the payload cannot move the window either). AC3 of story 4.1 and AC1 of story 3.1 were reworded.
- **Proof:** new domain, handler, API and annex-endpoint assertions; with the old handler 5 of them fail. The stored turn round-trips the recommendation
  (`GET /sessions/{sid}` returns exactly the posted answer).

## AD-29 - Audit fix: the window edge cases follow the contract instead of `CANNOT_CONFIRM`  *(contract deviation, AI decision reversed)*
- **Phase:** post-delivery audit of Impl-1 (audit question 4), 2026-10-26.
- **What was wrong:** the first version of the audit said that the answer at the exclusive end of the window was "not specified". It was: `contracts.md`
  `diagnose_schedule_window` Q1 (D55) says "if no window satisfies `start > now`, `next_open_window == null` and an explicit no-future-window state is
  rendered", and "if `windows` is empty, the class is `schedule_no_constraint`". The ATDD stub `test_diagnose_schedule_window_invariant_boundary_is_half_open`
  asserts the null, and `planning/reviews/review-detailed-design.md` lists both cases. Story 3.1 (D5, an AI decision recorded in AD-24) answered
  `CANNOT_CONFIRM` in both instead, which says "insufficient evidence" when the evidence is complete: the job is constrained and its only window is over.
- **Fix (`src/domain/window_diagnosis.py`):** at or after the end of the only window the class stays `schedule_window_restricted`, `next_open_window` is
  null and the last claim says "No later window#night is on record, so no next open window can be given" (every stated instant is a record's); a
  constraint whose window is not on record is `schedule_no_constraint` with no window evidence and a claim that names the missing window. The
  `CannotConfirm` branch of `src/application/window_diagnosis_handler.py` became unreachable and was removed.
- **Proof:** 6 tests (domain, handler with a fixture whose only window is not `window#night`, API with `M12_CLOCK_START` at the window end) fail on
  the previous code and pass now.
- **To confirm with the team:** `schedule_no_constraint` for "the named window is not on record" is the contract's literal choice; if the team prefers a
  typed no-window canonical (the other option in the detailed-design review), the contract changes first.

## AD-30 - Audit fix: the epic pinned Night hours that no fixture has  *(planning text)*
- **Phase:** post-delivery audit of Impl-1 (audit questions 3 and 4), 2026-10-26.
- **What was wrong:** the story-3.1 AC in `planning/epics.md` gave the S2 fixture as `night` `20:00–08:00`. The fixture
  (`fixtures/estate/windows.json`) and Annex 12.2 use `22:00–06:00` UTC, and PRD A-10 says the hours are fixture content ("the PRD pins behavior, not
  fixture values"). The code already followed the fixture (story 3.1 D1, assumption 4); only the AC text contradicted it.
- **Fix:** the AC now names `22:00–06:00` UTC, its sources and A-10, in `planning/epics.md` and in its mirror `_bmad-output/planning-artifacts/epics.md`
  (kept byte-identical, AD-02). The PRD and UX examples ("today 20:00–08:00") are left as they are: they are illustrations under A-10, and the PRD-phase
  decision on explicit date + timezone already replaced that rendering.

## AD-31 - Audit fix: contracts.md named the `ErrorBody` field `error_code`  *(planning text)*
- **Phase:** post-delivery audit of Impl-1 (audit question 4), 2026-10-26.
- **What was wrong:** the canonical-wire-shape rule of `contracts.md` §2 (D58) said the canonical code travels in `error_code`; the contract schemas
  (`planning/detailed-design/schemas/dto.py`, `openapi.yaml`, `required: [code, status, message, retryable]`) and the service use `code`. Story 1.2
  followed the schema (AD-14 #3) but left the prose wrong, so a client written from the prose would read a field that never exists.
- **Fix:** one word in `planning/detailed-design/contracts.md`; D58 itself (`ai-log/decision-log-solu2.md`) never named the field, so nothing else changes.
  The other `error_code` occurrences in the contract are the node's error code (`ERR_THERMAL_88`) and are correct.

---

## Open assumptions to confirm at review
1. `Selector.method == "filter"` (equality filter over record fields) is an adapter convention invented for `select()`; the contract only
   says "method + params". Decided with the user: deferred to story 2.2 (dry-run snapshot), where it is confirmed or replaced.
2. Port `browse` returns `list[Record]` exactly as `contracts.md` §3 says, but the inbound `browse_state` response needs a `total`.
   Story 1.5 will need a contract-level decision (count method or a page type).
3. The 2 × 48 GB server is stored as `gpu_memory_gb = 96` because `NodeRecord` forbids extra fields.
4. Night Policy hours are 22:00–06:00 UTC (PRD leaves fixture values open, A-10). The story-3.1 AC in `planning/epics.md` now says the same (AD-30).
5. Unexpected exceptions degrade to `PROVIDER_UNAVAILABLE` (503) because the error catalog has no generic internal-error code (AD-12 safe failure).
6. A query to a reset session is 410 and persists `status = expired` (contracts.md P2 read literally); a later GET shows `expired`. Confirmed by the user in the story 1.2 review (AD-18).
7. Clarification turns are stored as `intent = "clarification"`, `canonical = "CLARIFICATION"`; the wire body is the 200 `ErrorBody` (D58).
8. The simulated clock does not advance by itself (`M12_CLOCK_START`), so the 30-minute idle expiry is only exercised by tests that advance it.
