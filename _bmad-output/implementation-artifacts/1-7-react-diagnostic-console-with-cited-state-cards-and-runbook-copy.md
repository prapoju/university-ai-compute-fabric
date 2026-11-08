# Story 1.7: React diagnostic console with cited state cards and runbook copy

Status: done

<!-- Annex 12.6 of the Impl-2 task (docs/task-impl2.md). Flow E (Playwright E2E + Page Object Model).
     Red phase first: the E2E spec and CopilotConsolePage are committed before console/ exists.
     Scope decided by Julio (I2-54): two E2E tests (the Annex 12.6 scenario and one failure path with a
     visible error state). The other cases of test/test-design.md §6.3.7 are out of scope (see Scope). -->

## Story

As Nadia, a Frontline Lab Helpdesk Specialist,
I want to type a student's complaint into a console and get a cited state card and a runbook I can copy,
so that I can close the ticket at the counter without reading raw state.

## Acceptance Criteria

Source: `planning/epics.md` Story 1.7, Annex 12.6 of `docs/task-impl2.md`. Requirements: FR-01, FR-07, FR-08, FR-13, NFR-9, NFR-10, AD-9, UX-DR4. Test cases: `test/test-design.md` §6.3.7 (scoped, see Scope).

1. **Submit and pending state.** Given Nadia is on `/helpdesk/copilot`, when she types `Student Alex was denied model deepseek-coder. Diagnose and provide runbook.` and clicks `Submit Inquiry`, then a pending state is visible until the response arrives. The request is a single synchronous `POST /api/v1/copilot/query`. No stream, no SSE (ARCHITECTURE, impl2-rules: Streaming output).
2. **Cited badge.** The answer renders the badge `Verified via Policy Engine [RULE-CAT-04]`. The rule id is derived from the policy evidence snippet of the answer, never hard-coded in the console (see Dev Notes, badge derivation).
3. **Runbook card.** A troubleshooting runbook card renders the registry template's steps verbatim, in template order, as an ordered list (AD-9). The steps come from `answers[0].recommendation.runbook.steps`.
4. **Copy.** When Nadia clicks `Copy Runbook to Clipboard`, a success checkmark confirms the copy, and the clipboard text equals the rendered runbook text (the steps joined by a newline, in order).
5. **Error state (failure path).** Given the same console, when Nadia submits `Student Zed was denied model deepseek-coder. Diagnose and provide runbook.`, the API answers with the canonical `ENTITY_NOT_FOUND` body (`Entity Not Found in State: user#Zed.`). The console shows a visible error state with that message, and renders **no** badge, **no** runbook card and **no** copy button.
6. **Verbatim canonical text.** Canonical strings are shown exactly as the API returns them. The console never rewrites, translates or paraphrases them.
7. **Input cap.** The composer accepts at most 1,000 characters (UX-DR4). The API limit (`VALIDATION_QUERY_TOO_LONG`) is shown in the same visible error state.
8. **POM discipline.** Every selector and every user action lives in `tests/e2e/pages/CopilotConsolePage.ts`. The spec contains no `locator(`, no `getBy*`, no CSS selector and no `waitForTimeout`. Assertions are web-first (`expect(locator).toBeVisible()`, `toHaveText()`, and so on).
9. **Config-only runbook (NFR-10).** The console contains no runbook or rule logic. A new template in `fixtures/runbooks/` changes what the console shows with no console change.
10. **Build and trace.** `npx playwright test --trace on --fail-on-flaky-tests` passes locally and in the `e2e` CI job. The CI job keeps a `trace.zip` (the `test-results/` artifact).

## Scope

In scope (decided by Julio, logged as I2-54):

- E2E test 1: the Annex 12.6 scenario (AC 1 to 4).
- E2E test 2: one failure path with a visible error state (AC 5). The failure is `ENTITY_NOT_FOUND` (`Student Zed`), which needs no fault switch.

Declared out of scope for this story (the other cases of `test/test-design.md` §6.3.7 are not implemented here):

- Double-click and concurrency cases (one request while pending; two sequential answers).
- Held-response pending case via `page.route` (the pending state is still implemented and is exercised by test 1).
- Checkmark auto-hide via `page.clock`.
- Clipboard denied (no permission) case.
- Provider 503 case (needs a fault switch, TG-I2-6).
- Badge binding via `waitForResponse` (IR-10).
- Lint check on `locator(` (AC 8 is enforced by review, not by a lint rule).

UX-DR8 (alertdialog, `Esc`, delegation card labels from story 2-4) is **not** covered by 1-7. It belongs to optional story 1-8 and is declared there as a gap, not implemented here.

## Tasks / Subtasks

Flow E: the spec and the page object are committed red before any console code (Task 1). Task 2 is the green code. Commits follow `test(story-1.7): ...` and `feat(story-1.7): ...`.

- [x] **Task 1: Red E2E with the page object model** (AC: 1-5, 8)
  - [x] 1.1 `tests/e2e/pages/CopilotConsolePage.ts`: prompt input, `Submit Inquiry`, pending state, response container, citation badge, runbook card, ordered runbook steps, `Copy Runbook to Clipboard`, success checkmark, error state. Actions only (`ask(text)`, `copyRunbook()`), no assertions.
  - [x] 1.2 `tests/e2e/copilot-console.spec.ts`: test 1 (Annex scenario, AC 1 to 4) and test 2 (failure path, AC 5). Grant `clipboard-read` and `clipboard-write`. Read the clipboard through `page.evaluate(() => navigator.clipboard.readText())`.
  - [x] 1.3 Run it. Save the output to `docs/evidence/impl2/red-1-7.log`. Every failure must come from the missing console (no route, no element), not from an import, a fixture or a syntax error.
- [x] **Task 2: Console scaffold and behaviour** (AC: 1-7, 9)
  - [x] 2.1 `console/`: Vite 8, React 19, TypeScript strict (`"strict": true`, no `any`). Route `/helpdesk/copilot` (React Router or a single route switch; no framework beyond React).
  - [x] 2.2 `console/src/api.ts`: `askCopilot(query)` calls `POST /api/v1/copilot/query` with `{query}` and returns the parsed body. It is the only module that calls `fetch`.
  - [x] 2.3 Pending state while the request is in flight; the submit button is disabled while pending (single request per submit).
  - [x] 2.4 Answer rendering: the answer chain of the first answer, the cited badge (AC 2, see Dev Notes), the runbook card (AC 3), `Copy Runbook to Clipboard` (AC 4) with a success checkmark after `navigator.clipboard.writeText`.
  - [x] 2.5 Error rendering (AC 5, 7): when the body has `code` (an `ErrorBody`), show `message` in a visible error element and render no badge, card or copy button.
- [x] **Task 3: Playwright configuration and CI** (AC: 10)
  - [x] 3.1 `playwright.config.ts`: `webServer` as a list. Entry 1: uvicorn on `:8000` with `/healthz` as the readiness URL (unchanged command). Entry 2: `npm --prefix console run build && npm --prefix console run preview -- --port 4173 --strictPort`, readiness `http://127.0.0.1:4173/`. `baseURL` moves to `http://127.0.0.1:4173`. `trace: 'on-first-retry'` stays.
  - [x] 3.2 `console/vite.config.ts`: preview proxy for `/api` and `/healthz` to `http://127.0.0.1:8000`, so the console talks to the real app with no CORS (D-P5).
  - [x] 3.3 `.github/workflows/quality-gate.yml`, job `e2e`: add `npm ci --prefix console` and `npm run build --prefix console` before the Playwright step. Keep `--trace on` and the `test-results/` artifact upload.
  - [x] 3.4 `Makefile` `e2e` target: no change needed (it runs `npx playwright test`, which builds the console through `webServer`).
- [x] **Task 4: Evidence and gates** (AC: 10)
  - [x] 4.1 `npx playwright test --trace on --fail-on-flaky-tests 2>&1 | tee docs/evidence/impl2/e2e-1-7.log`.
  - [x] 4.2 Copy the Annex test trace to `docs/evidence/impl2/trace-1-7-annex-12-6.zip`.
  - [x] 4.3 `grep -rnE 'sleep\(|waitForTimeout' src tests console --exclude-dir=node_modules` returns nothing.
  - [x] 4.4 `.venv/bin/python -m ruff check .`, `.venv/bin/python test/ci/schema_check.py`, and the pytest suite with coverage (`--cov-fail-under=90`).

### Review Findings

Inline review (no subagents) of the console (`console/src`), the page object, the spec and the Playwright configuration. Findings are ordered by severity.

- [x] [Review][Patch] **M-1 (medium), fixed** in `b36c676`. `isAnswer` checked only `answer_id` and `evidence` is an array. A 200 body with malformed `claims` or evidence items would crash the render instead of showing the visible error state. The guard now checks claims and each evidence item.
- [x] [Review][Patch] **L-1 (low), fixed** in `224ba7f`. The spec read the template from a path relative to the working directory. It now resolves from its own folder. Only the path changed; no assertion was touched.
- [x] [Review][Decision] **POM purity: pass.** The spec has no `locator(`, no `getBy*`, no CSS selector. Every selector is in `CopilotConsolePage.ts`. The spec reads the registry template as data, not as a selector.
- [x] [Review][Decision] **Flaky waits: none.** No `sleep`, `setTimeout` waits or `waitForTimeout` in `console/src` or `tests/e2e`. Assertions are web-first.
- [x] [Review][Decision] **Types: pass.** `tsc --noEmit` passes under `strict` with `noUncheckedIndexedAccess`. No `any`. API bodies are narrowed with type guards. The one `as` cast is in the spec, on the template JSON.
- [x] [Review][Decision] **Blindly Green.** The failure-path test awaits the error message before the absence checks, so `toHaveCount(0)` cannot pass before the answer arrives. The Annex test checks the exact badge text.
- [x] [Review][Decision] **Mutation.** Badge text changed in `console/src/CopilotConsole.tsx`: the Annex test fails on the badge (`Received: Verified via Policy Engine (RULE-CAT-04)`), the failure-path test still passes, which is correct. Log `docs/evidence/impl2/mutation-1-7-badge.log`. Restored; `git diff` clean.
- [x] [Review][Decision] **Coverage gap, declared.** UX-DR8 (alertdialog, `Esc`, delegation card labels from story 2-4) is not covered by 1-7. It is a gap for optional story 1-8, which is where the S-D surface lives. The pending-state case is exercised by the Annex test but not asserted (a fast local answer may never show it). The held-response case is out of scope (see Scope).
- [x] [Review][Decision] **Accepted, not changed.** `ruleOfClause.ts` mirrors the regex of `src/domain/rule_ids.py`. Only the E2E text pins it. A shared fixture would be stronger, but it would couple the console build to the Python test suite. Recorded in I2-55.

## Dev Notes

### Backend contract the console consumes

- `POST /api/v1/copilot/query`, body `{query}` (`CopilotQueryRequest`, openapi). Opens a session itself; the console keeps no session state.
- HTTP 200 with `AnswerEnvelope` `{answers: [AnswerDTO, ...]}`, or HTTP 200 with `ErrorBody` `{code, status, message, retryable, explanation}` for canonical failures (`ENTITY_NOT_FOUND`, `VALIDATION_QUERY_TOO_LONG`, `PROVIDER_UNAVAILABLE`, ...). Check for `code` first.
- `AnswerDTO` fields used: `answer_chain` (ordered stages), `diagnosis_class`, `claims`, `evidence` (`citation_id`, `source_type`, `snippet`, `position`), `recommendation`, `prose`.
- Verified against the running app (TestClient, I2 probe): the annex query returns `intent = diagnose_access_denial`, `diagnosis_class = access_denial_not_in_allowlist`, `answer_chain = [observation, evidence, diagnosis, recommendation]`, and `recommendation = {runbook: {steps, required_tools, safety_warnings, provenance: {source, version}}}`. The 5 steps are the template steps in order.
- `Student Zed ...` returns `ErrorBody` with `code = ENTITY_NOT_FOUND`, `message = Entity Not Found in State: user#Zed.`.
- S1 (`Why was student Alex denied ...`, no word `runbook`) returns `recommendation = null`. The console must render no card for it (the card renders only when `recommendation.runbook` exists).
- Node-triage misses carry a canonical literal `no runbook available for code {code}.` in `canonical` with no steps. The console renders the literal and no card when `recommendation` is null.

### Badge derivation (rule_of_clause)

- The badge rule id is `rule_of_clause(snippet, clause_id)` from story 1-6 (`src/domain/rule_ids.py`): the parenthesised `RULE-[A-Z]+-\d{2}` right after the clause id in the policy snippet.
- Policy evidence in the annex answer: citation `policy#catalog.4.2`, snippet `policy#catalog.4.2 (RULE-CAT-04) [not-in-allowlist]: ...`.
- The console mirrors that fixed pattern in `console/src/ruleOfClause.ts` (the console holds no domain logic, ARCHITECTURE §1.1; a fixed regex is display derivation, not a rule). Drift check: the E2E asserts the exact badge text, so a changed pattern fails the spec.
- Badge text: `Verified via Policy Engine [${ruleId}]`. Render only when `ruleId` is found; no badge otherwise (AD-2, AD-8: badges render only cited evidence).
- The runbook steps are rendered verbatim (AD-9). The console never generates steps, never edits them, never paraphrases a canonical string.

### Previous story intelligence (3-3, done)

- The access-denial runbook is keyed by `access_denial_not_in_allowlist` (`fixtures/runbooks/access-denial-not-in-allowlist.json`) and attached only when the query contains `runbook` (I2-48). Story 1-7 relies on this: the Annex query has the word, so the card is present.
- The S1 golden body has no `recommendation` (I2-48 regression). Do not change the backend for the console.
- The console changes nothing in `src/`, `fixtures/` or `planning/`. If a backend fact is missing, that is an E.6 stop (contract change), not a console workaround.

### Architecture guardrails

- React 19 + TypeScript + Vite 8 SPA (ARCHITECTURE §1.1, §1.12). One FastAPI process in production serves the built assets; in tests Vite preview proxies `/api` to uvicorn (D-P5).
- Synchronous HTTP. No SSE, no WebSocket, no polling (impl2-rules: Streaming output).
- `console/` holds no domain logic. Rules, ids, citations and runbooks come from the API.
- `strict` TypeScript, no `any`, no `as` casts on API bodies except through a type guard in `api.ts`.
- No `setTimeout`, `sleep` or `waitForTimeout` in `console/src` or `tests` (impl2-rules; CI banned-waits job).

### Test rules (Flow E)

- Page object owns every selector and every action. The spec reads like the Annex story (Nadia's steps).
- Web-first assertions only. No waits for time; the pending state and the checkmark are awaited with `expect(...).toBeVisible()`.
- Clipboard: `clipboard-read` and `clipboard-write` granted on the context. Read with `navigator.clipboard.readText()` through `page.evaluate`.
- `trace: 'on-first-retry'` in local runs; CI passes `--trace on` so a `trace.zip` exists even when every test passes.
- Red log: `docs/evidence/impl2/red-1-7.log`. Green log: `e2e-1-7.log`. Trace: `trace-1-7-annex-12-6.zip`.

### Project Structure Notes

- New: `console/` (Vite app), `console/src/ruleOfClause.ts`, `console/src/api.ts`, `tests/e2e/pages/CopilotConsolePage.ts`, `tests/e2e/copilot-console.spec.ts`.
- Changed: `playwright.config.ts`, `.github/workflows/quality-gate.yml` (e2e job only), `_bmad-output/implementation-artifacts/sprint-status.yaml` and `implementation-artifacts/sprint-status.yaml` (identical).
- Existing `tests/e2e/smoke.spec.ts` keeps working: `/healthz` is proxied by Vite preview.

### References

- [Source: planning/epics.md#Story 1.7] acceptance criteria and DoD.
- [Source: docs/task-impl2.md#Story 12.6] Annex scenario and Page Object requirement.
- [Source: docs/impl2-rules.md] Streaming output, Test rules, Annex-to-specification decisions.
- [Source: test/test-design.md#6.3.7] case list (scoped above).
- [Source: planning/ARCHITECTURE.md#1.1, #1.12] SPA, Vite, single process.
- [Source: src/domain/rule_ids.py] `rule_of_clause`.
- [Source: _bmad-output/implementation-artifacts/3-3-runbook-registry-and-node-triage-runbook.md] runbook attachment and the S1 golden body.

## Dev Agent Record

### Agent Model Used

Claude (Haiku 5.5) via Claude Code

### Debug Log References

### Completion Notes List

- Red phase committed first (`20d9d09`): both E2E tests failed on the missing prompt textbox (`docs/evidence/impl2/red-1-7.log`). The smoke test passed.
- Green: console, route, badge, runbook card, copy and error state (`ffb27d2`). Playwright config and CI (`dcb5d26`, `2a55f63`).
- Playwright: 3 passed with `--trace on --fail-on-flaky-tests` (`docs/evidence/impl2/e2e-1-7.log`). Annex trace: `docs/evidence/impl2/trace-1-7-annex-12-6.zip`.
- Full suite: 2155 passed, branch coverage 97.53 % (`docs/evidence/impl2/flow-e-1-7-review-coverage.log`).
- Scope: two E2E tests (I2-54). The other §6.3.7 cases are out of scope in the story.

### File List

- `_bmad-output/implementation-artifacts/1-7-react-diagnostic-console-with-cited-state-cards-and-runbook-copy.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml` and `implementation-artifacts/sprint-status.yaml` (identical)
- `console/` (package.json, package-lock.json, tsconfig.json, vite.config.ts, index.html, src/*)
- `tests/e2e/pages/CopilotConsolePage.ts`, `tests/e2e/copilot-console.spec.ts`, `tests/e2e/pages/README.md`
- `playwright.config.ts`, `.github/workflows/quality-gate.yml`
- `docs/ai-decision-log.md` (I2-54, I2-55, I2-56), `docs/evidence/impl2/` (red-1-7, e2e-1-7, trace, mutation-1-7-badge, flow-e-1-7-review-coverage)
