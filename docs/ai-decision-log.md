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
| AD-09 | Build · verify | Limitation | Docker image build could not be executed | Juan (informed) |

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

## AD-09 — Docker build not executed
- **Phase:** Build, verification.
- **What happened:** `docker compose config` validates the compose file, but the Docker daemon was not running, so the image build and
  container run were **not** executed. The agent did not start Docker Desktop on its own.
- **Compensating evidence:** a clean `git clone` → new venv → `pip install -e ".[dev]"` → `python -m src.dependency_check` → `pytest` (258 passed)
  → `ruff` → `uvicorn` + `/healthz` + `/readyz` all succeeded. **To do by the team:** run `docker compose up --build` once and tick this item.

---

## Open assumptions to confirm at review
1. `Selector.method == "filter"` (equality filter over record fields) is an adapter convention invented for `select()`; the contract only
   says "method + params". Story 2.2 (dry-run snapshot) should confirm or replace it.
2. Port `browse` returns `list[Record]` exactly as `contracts.md` §3 says, but the inbound `browse_state` response needs a `total`.
   Story 1.5 will need a contract-level decision (count method or a page type).
3. The 2 × 48 GB server is stored as `gpu_memory_gb = 96` because `NodeRecord` forbids extra fields.
4. Night Policy hours are 22:00–06:00 UTC (PRD leaves fixture values open, A-10).
5. Unexpected exceptions degrade to `PROVIDER_UNAVAILABLE` (503) because the error catalog has no generic internal-error code (AD-12 safe failure).
