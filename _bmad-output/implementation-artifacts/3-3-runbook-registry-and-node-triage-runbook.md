# Story 3.3: Runbook registry and node-triage runbook

Status: review

<!-- Annex 12.6 of the Impl-2 task (docs/task-impl2.md). Flow B (test-along): tests and code in the
     same commit, no red-phase commit. Scope is the annex, not the full epic: the node-triage
     diagnoser, the runbook registry read path, and the access-denial runbook extension the annex
     query needs. The optional stories 3-2 and 3-4 are out of scope. -->

## Story

As Nadia, a Helpdesk specialist,
I want a sanctioned, ordered remediation runbook for a cordoned node that reports a recorded error code,
so that I follow approved steps with safety warnings instead of inventing guidance.

## Acceptance Criteria

Source: `planning/epics.md` Story 3.3, Annex 12.6 of `docs/task-impl2.md`. Requirements: FR-07, FR-08, AD-9, NFR-1, NFR-5, NFR-10. Contract: `planning/detailed-design/contracts.md` (`diagnose_node_triage`, `lookup_runbook`, `get_runbook`, OP-12).

1. **S3 diagnosis.** Given node `node#ws-gpu-11` is `cordoned: true` with `error_code: ERR_THERMAL_88` in the estate, when the operator asks `Node ws-gpu-11 is cordoned with code ERR_THERMAL_88. What should I do?`, the answer has `diagnosis_class == node_triage_runbook`, chain `observation -> evidence -> diagnosis -> recommendation`, and `recommendation.runbook = {steps, required_tools, safety_warnings, provenance: {source, version}}`. `steps` equal the registered template's `steps` in template order, verbatim (100 % step-match). `provenance` is `{source: "Lab Safety SOP-THERM-01", version: "1.0"}`. The claim cites the node record only (`node#ws-gpu-11`), as the contract's diagnoser input has no event record; evidence positions are `0..n-1`. The cordon event is not read (I2-49).
2. **Precondition: cordoned.** A node that is not cordoned is not diagnosed as a runbook case. The operation's P1 is a violation (contracts.md `diagnose_node_triage`). The chat turn renders the canonical literal `no runbook available for code {code}.`, where `{code}` is the recorded code (`null` when none is recorded), with class `no_runbook_available` and no steps (Decision D-3, approved).
3. **Precondition: code match (P2).** The queried code must equal the node's recorded `error_code`. A null recorded code, or a code that differs from the recorded one, returns `no_runbook_available`, `recommendation == null`, and the literal `no runbook available for code {code}.` (`RUNBOOK_NOT_FOUND`). `{code}` is the recorded code, or `null` when none is recorded. Zero steps are rendered.
4. **Unknown code.** A code with no registered template returns the same literal and zero fabricated steps. Lookup is exact on `error_code` (no fuzzy match, AD-9).
5. **Physical intervention needs a source.** A template with `physical_intervention: true` and `approved_source: null` renders unavailability (`no_runbook_available`), never its steps. The registry rejects such a template at registration (`RUNBOOK_TEMPLATE_UNSOURCED`, 422). The loader already rejects it at startup.
6. **Empty template rejected.** A template with `steps: []` is rejected at registration (`RUNBOOK_TEMPLATE_EMPTY`, 422) (D44).
7. **Runbook read route.** `GET /api/v1/runbooks/{error_code}` returns 200 with `{steps, provenance}` as two separate sections (AD-9). An unknown code returns 404 with body `no runbook available for code {error_code}.`. A code that fails `^[A-Za-z0-9._-]{1,64}$` returns 400 (`VALIDATION_MALFORMED_BODY`). This is the only operation of the contract that is not served yet. The route is added to `openapi.yaml` (already present) and to `SERVED_IN_THIS_STORY` in the same commit.
8. **Annex 12.6 access-denial query.** `Student Alex was denied model deepseek-coder. Diagnose and provide runbook.` routes to `diagnose_access_denial` (it does not route today) and the answer attaches the access-denial runbook template `access_denial_not_in_allowlist` from `fixtures/runbooks/`. The runbook is attached **only when the query explicitly asks for a runbook** (the query contains the word `runbook`; Decision D-2, approved). The access-denial diagnosis, claims and class are unchanged.
   - S1 (`Why was student Alex denied access to model deepseek-coder?`), S2 and the `ghost_user_99` edge case return bodies **byte-identical to HEAD**. The tests compare the response bodies against bodies captured at HEAD before the change, not against values re-typed by hand.
9. **Config-only template (NFR-10).** A new template file added under `fixtures/runbooks/` is served by the registry and the read route with no code change. A test proves it, using a temporary fixture folder.
10. **Performance.** The read path is a registry lookup (p95 < 50 ms per contract). The node-triage operation stays inside NFR-5 (p95 ≤ 5 s).

## Tasks / Subtasks

- [x] **Task 1: Domain, pure** (AC: 1-6)
  - [x] 1.1 `src/domain/runbook.py`: `triage_node_runbook(node, error_code, template) -> NodeTriageDiagnosis | CanonicalCode`. Pure: checks P1 and P2, renders the template verbatim, applies the physical-source guard (AC 5). Time and ids are not used.
  - [x] 1.2 `src/domain/intent.py`: register rule `diagnose_node_triage` (`RULE-INTENT-NODE-TRIAGE`). Add the access-denial pattern for `denied ... diagnose` (AC 8). Regression cases for S1, S2, `ghost_user_99`, and the destructive guard (`cordon`, `drain` as requests must still route to refusal, never to triage).
  - [x] 1.3 `src/domain/references.py`: a node reference extractor (`node#ws-gpu-11`, `ws-gpu-11`) and the error-code token (`ERR_THERMAL_88`). Exact match only. The access-denial extractor accepts `Student Alex was denied model deepseek-coder.`
- [x] **Task 2: Application** (AC: 1-6, 8)
  - [x] 2.1 `src/application/node_triage_handler.py`, following `window_diagnosis_handler.py`: resolve the node (`EntityResolver`), read the node record (`NodesPort`), look up the template (`RunbookRegistryPort.get`), call the pure domain function, bind claims, guarded prose once (`write_prose`), mint claim ids. Register it in `src/bootstrap.py`.
  - [x] 2.2 Registry registration rules: `RunbookRegistryPort.register` rejects empty steps (422) and an unsourced physical template (422). Add to the fixture loader's existing checks, not as a second copy of the rule.
  - [x] 2.3 Access-denial runbook: `src/application/access_denial_handler.py` attaches the template keyed `access_denial_not_in_allowlist` only when the query contains `runbook` (Decision D-2). The diagnosis class and claims stay unchanged.
  - [x] 2.4 Contract amendment, same commit as the code (Decision D-2): `planning/detailed-design/contracts.md`, access-denial `diagnose_access_denial` Q1, changes `recommendation: null` to allow `recommendation.runbook` (same shape as node triage) when the query asks for a runbook and a template exists for the class. Amend `openapi.yaml` only if the answer schema needs it. Log the amendment as a new I2-NN entry.
- [x] **Task 3: Read route** (AC: 7)
  - [x] 3.1 `src/adapters/inbound/runbooks.py`: `GET /api/v1/runbooks/{error_code}`, mounted in `src/adapters/inbound/app.py`. Response DTO `GetRunbookResponse` from `src/dto.py` (no DTO change).
  - [x] 3.2 `tests/api/test_contract_routes.py::SERVED_IN_THIS_STORY` gains the route, in the same commit as the route.
- [x] **Task 4: Fixtures** (AC: 8, 9)
  - [x] 4.1 `fixtures/runbooks/access-denial-not-in-allowlist.json`: non-physical template with the content approved in Decision D-1 (`template_id: rb-access-denial-not-in-allowlist`, `error_code: access_denial_not_in_allowlist`, five steps, `physical_intervention: false`, `approved_source: "Course fixture: help-desk access procedure (Impl-2)"`, `version: "1.0"`). Copied as approved, not reworded.
  - [x] 4.2 A config-only test: add a template in a temp folder and read it back with no code change.
- [x] **Task 5: Tests and guard** (AC: all)
  - [x] 5.1 Unit: domain (`tests/unit/test_runbook.py`), handler (`tests/unit/test_node_triage_handler.py`), intent regressions (`tests/unit/test_intent.py`), reference extraction.
  - [x] 5.2 API through the real container (`tests/api/test_runbook_api.py`): S3 verbatim, mismatch, null code, unknown code, unsourced physical, empty steps, route 200/404/400, annex 12.6 query. Regression: S1, S2 and `ghost_user_99` response bodies compared byte-for-byte with bodies captured at HEAD before any code change, and the S1 body must carry no runbook.
  - [x] 5.3 Mutation: break the code comparison in `triage_node_runbook` (P2). At least one node-triage test must fail. Restore. `git diff` clean.
  - [x] 5.4 `pytest tests -q --strict-markers --cov=src --cov-branch --cov-fail-under=90`, `ruff check`, `python test/ci/schema_check.py`, `cmp src/dto.py planning/detailed-design/schemas/dto.py`.
  - [x] 5.5 Live check of the annex queries with the script in the operational guide (E.3), output recorded in the log entry.

### Review Findings

_(Inline review pending: Julio approves each fix before it is applied, per the operating rules.)_

## Dev Notes

- **Layout.** Real paths are `src/{domain,ports,application,adapters}` and `fixtures/`. The epics file lists `service/...` paths; those are not used (log entry AD-03).
- **Template as the registry key (AD-9, contracts `lookup_runbook` Q4).** The registry is keyed by exact `error_code`. The access-denial template is keyed by the diagnosis class string (Decision D-2), so no contract change is needed for the lookup itself.
- **Verbatim rendering.** Steps are rendered by copy, never by generation. The prose call (`LlmProsePort`) may only connect the steps. No step text reaches the prose input as something to rewrite; `scan_prose` guards the output as in 1.3.
- **Existing fixture.** `fixtures/runbooks/err-thermal-88.json` holds `physical_intervention: true`, `approved_source: "Lab Safety SOP-THERM-01"`, `version: "1.0"`, and five steps. The estate loader (`src/adapters/outbound/sim/estate_loader.py`, `_load_runbooks`) already validates it.
- **Node state.** `node#ws-gpu-11` is `cordoned: true`, `error_code: ERR_THERMAL_88`, `health: fault` in `fixtures/estate/nodes.json`. Do not change it (AC 1 depends on it).
- **Intent collision check.** `cordoned` is a reported state, not a request (`src/domain/intent.py`, `_DESTRUCTIVE`). The triage phrasing must not contain a base-form destructive verb.
- **Audit event.** Contracts `diagnose_node_triage` Q3 requires `toolcall.diagnose_node_triage`. The same gap is recorded in `_bmad-output/implementation-artifacts/deferred-work.md` for 1.3 and 3.1 (the diagnosers do not emit tool-call audit events yet). Decision D-4.
- **Out of scope.** Story 3.2 (retrospective event log), story 3.4 (intent taxonomy and follow-up references), the console (story 1.7).

### Decisions (approved by Julio, 2026-11-08)

- **D-1. Access-denial runbook content: approved.** The template is the one the approver supplied. It is `fixtures/runbooks/access-denial-not-in-allowlist.json`, keyed by the diagnosis class `access_denial_not_in_allowlist`. Its steps cite `policy#catalog.4.2` (RULE-CAT-04), forbid changing allowlists or credentials, and route exceptions to the platform owner. It is non-physical, so `approved_source` is informational. The key choice is recorded as a new I2-NN entry in the dev commit.
- **D-2. Attaching the access-denial runbook: approved.** Amend `contracts.md` (access-denial `diagnose_access_denial` Q1) in the same commit as the code, and `openapi.yaml` only if needed. The runbook is attached only when the query explicitly asks for a runbook. S1, S2 and `ghost_user_99` stay byte-identical to HEAD, and regression tests compare the bodies (AC 8, Task 2.4, Task 5.2).
- **D-3. Non-cordoned node in chat: approved.** Canonical literal `no runbook available for code {code}.` with the recorded code (or `null`), no steps, class `no_runbook_available` (AC 2).
- **D-4. Audit event for the diagnoser: approved, deferred again.** `toolcall.diagnose_node_triage` is not implemented in this story. The gap is recorded under a "Deferred from: story 3-3" section in `deferred-work.md`, next to the 1.3 and 3.1 entries.

### Project Structure Notes

- New: `src/domain/runbook.py`, `src/application/node_triage_handler.py`, `src/adapters/inbound/runbooks.py`, `fixtures/runbooks/access-denial-not-in-allowlist.json`, tests listed in Task 5.
- Modified: `src/domain/intent.py`, `src/domain/references.py`, `src/application/access_denial_handler.py`, `src/bootstrap.py`, `src/adapters/inbound/app.py`, `src/adapters/outbound/sim/estate_loader.py` (only if needed), `tests/api/test_contract_routes.py`, `planning/detailed-design/contracts.md` (D-2), `planning/detailed-design/schemas/openapi.yaml` (only if needed), `docs/ai-decision-log.md` (new entry I2-47), `_bmad-output/implementation-artifacts/deferred-work.md` (section for 3-3), `README.md` (one line), both `sprint-status.yaml` copies.
- No conflicts with the architecture found; the design follows the window-diagnosis pattern of story 3.1.

### References

- Epic and AC source: `planning/epics.md`, section "Story 3.3" (line 463).
- Annex: `docs/task-impl2.md`, Story 12.6 and the Scenario "Helpdesk specialist investigates access denial and copies verified runbook".
- Contract: `planning/detailed-design/contracts.md` §1 `diagnose_node_triage` (Q1-Q4, L1), `lookup_runbook` (Q1-Q4), `get_runbook`, OP-12 `runbook_registry_port`, error table rows `RUNBOOK_NOT_FOUND`, `RUNBOOK_TEMPLATE_EMPTY`, `RUNBOOK_TEMPLATE_UNSOURCED`.
- OpenAPI: `planning/detailed-design/schemas/openapi.yaml`, path `/api/v1/runbooks/{error_code}` (line 278).
- Fixtures: `fixtures/runbooks/err-thermal-88.json`, `fixtures/estate/nodes.json`, `fixtures/estate/events.json`.
- Pattern: `_bmad-output/implementation-artifacts/3-1-schedule-and-window-diagnosis.md` (Dev Notes D4).

## Dev Agent Record

### Agent Model Used

Claude (Impl-2 dev agent), claude-haiku-5-5

### Debug Log References

- Mutation check (Task 5.3): breaking the code/cordon guard of `runbook_miss` fails 3 tests (`test_runbook.py`, `test_node_triage_api.py`); breaking `is_renderable` fails 2 tests. Both restored, `git diff` clean.
- Baseline before the story: 2092 pass, coverage 97.73 %. After the last commit: 2150 pass, coverage 97.49 %.
- The runbook miss stores `canonical` unset: the answer DTO enum has no `RUNBOOK_NOT_FOUND` (I2-47).

### Completion Notes List

- Node triage: pure domain (`src/domain/runbook.py`), intent rule `diagnose_node_triage` (`RULE-INTENT-NODE-TRIAGE`), handler `src/application/node_triage_handler.py`, registered in `bootstrap.py`. S3 renders the template steps verbatim; a miss is the literal `no runbook available for code {code}.` with no steps (D-3).
- Read route `GET /api/v1/runbooks/{error_code}` (`RunbookService`, `src/adapters/inbound/runbooks.py`), in `SERVED_IN_THIS_STORY`. The committed ATDD assertion of story 2.4 is now `test_every_contract_operation_is_served` (I2-47).
- Access-denial runbook (annex 12.6): template `access_denial_not_in_allowlist`, attached only when the query asks for a runbook; `contracts.md` access-denial Q1 amended (I2-48). S1, S2 and `ghost_user_99` are byte-identical to HEAD (`tests/api/golden/copilot_query_at_head.json`).
- NFR-10 (config-only template served) and the loader registration rules are tested.
- Deferred (D-4): `toolcall.diagnose_node_triage` audit event; and `toolcall.runbook.get` (contracts `get_runbook` Q3), see `deferred-work.md`, section 3-3.

### File List

New: `src/domain/runbook.py`, `src/application/node_triage_handler.py`, `src/application/runbook_service.py`, `src/ports/inbound/runbook_use_cases.py`, `src/adapters/inbound/runbooks.py`, `fixtures/runbooks/access-denial-not-in-allowlist.json`, `tests/unit/test_runbook.py`, `tests/unit/test_node_triage_intent.py`, `tests/unit/test_node_triage_handler.py`, `tests/unit/test_access_denial_runbook.py`, `tests/unit/test_runbook_fixture_rules.py`, `tests/api/test_node_triage_api.py`, `tests/api/test_runbook_read_api.py`, `tests/api/test_access_denial_runbook_api.py`, `tests/api/test_config_only_runbook_api.py`, `tests/api/golden/copilot_query_at_head.json`.

Modified: `src/domain/intent.py`, `src/domain/references.py`, `src/domain/canonical_strings.py`, `src/application/access_denial_handler.py`, `src/bootstrap.py`, `src/ports/inbound/__init__.py`, `src/adapters/inbound/app.py`, `tests/unit/test_intent.py`, `tests/unit/test_access_denial_handler.py`, `tests/unit/test_citation_binding_handlers.py`, `tests/unit/test_anti_fabrication.py`, `tests/unit/test_session_service.py`, `tests/api/test_contract_routes.py`, `tests/atdd/test_story_2_4.py`, `planning/detailed-design/contracts.md`, `docs/ai-decision-log.md` (I2-47 to I2-49), `_bmad-output/implementation-artifacts/deferred-work.md`, `README.md`, both `sprint-status.yaml` copies.

### Change Log

- 2026-11-08: story created (ready-for-dev); decisions D-1 to D-4 approved by Julio.
- 2026-11-08: dev complete (Flow B, one commit per task); status -> review. Code review inline is next.
