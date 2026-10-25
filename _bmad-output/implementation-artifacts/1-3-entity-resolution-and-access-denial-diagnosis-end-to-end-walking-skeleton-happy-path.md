---
baseline_commit: 3405dbf3c210f5c801b174c961cca6b124c4aa2e
---

# Story 1.3: Entity resolution and access-denial diagnosis end-to-end (walking-skeleton happy path)

Status: in-progress

<!-- This is the core story of the Impl-1 delivery (Annex 12.1, "Natural Language Access Denial Diagnosis"):
     the first cited, deterministic answer through every layer. Stories 1.1 (fixtures + read-only ports) and
     1.2 (sessions + intake) are done; this one plugs the first real diagnoser into the pipeline seam. -->

## Story

As Nadia,
I want the Copilot to resolve Alex and deepseek-coder against state and explain the exact policy reason, with citations,
so that I can point to the clause when I answer Mateo at the counter.

## Acceptance Criteria

Source: `planning/epics.md` → Story 1.3 and Annex 12.1 of the Impl-1 task. Requirements: FR-03, FR-04, FR-13 (citing), AD-2, AD-7, NFR-1, NFR-5, NFR-9.

1. **Exact entity resolution (AD-7).** Given the S1 fixture and the read-only ports, when I submit `why was alex denied deepseek-coder` (or `Why was student alex denied access to deepseek-coder?`), the resolver canonicalizes each reference to `{type}#{id}` (`user#alex`, `model#deepseek-coder`) and matches **exactly, case-folded, never fuzzy**; every required reference resolves to exactly one record **before** diagnosis proceeds.
2. **Cited diagnosis (FR-04).** The answer states Alex's role (`student`), the applicable clause `policy#catalog.4.2` with its text and rule (`RULE-CAT-04`), and the reason class `not-in-allowlist` (diagnosis class `access_denial_not_in_allowlist`), each grounded in retrieved evidence and in the denial event `event#evt-4711`. The `answer_chain` is `observation → evidence → diagnosis`.
3. **Deterministic core, LLM prose only (AD-2).** The diagnosis class, claims and citations are computed by pure code over the `EvidenceSet`; the (simulated) LLM is invoked **exactly once** to write connective prose over the fixed evidence payload and contributes no facts: prose containing any evidence token (entity id, clause id, role, reason class, time) is rejected and retried once, then fails the answer (`LLM_PROSE_REJECTED`).
4. **Canonical outcomes.** An unresolved reference answers HTTP 200 `ErrorBody` `ENTITY_NOT_FOUND` with the literal `Entity Not Found in State: {ref_list}.` naming every unresolved reference in input order and **no diagnosis**; an existing user and model without a matching clause/event answer `CANNOT_CONFIRM` (`Cannot confirm (insufficient evidence): checked {checked_list}.`); a provider or LLM failure aborts the turn (503) with no partial evidence.
5. **Session context.** A resolved turn adds `user#alex` and `model#deepseek-coder` to `session.context.resolved_entities`; a follow-up such as `and what about mateo?` resolves the new user against the provider and the model from the session context (FR-02).
6. **Quality (NFR-5, NFR-1).** The submit → cited answer path is well inside p95 ≤ 3 s / p99 ≤ 8 s on the fixtures; the S1 fixture is 100% accurate; the stores are unchanged by any read (AD-1).

### BDD scenarios (drive the tests, Given/When/Then)

```gherkin
Scenario: Diagnose the S1 access denial with citations
  Given the seeded estate, a frozen clock and an active session
  When I submit "why was alex denied deepseek-coder"
  Then I get 200 with one Answer, intent "diagnose_access_denial", answer_chain ["observation","evidence","diagnosis"]
  And diagnosis_class is "access_denial_not_in_allowlist" and canonical is null
  And the claims state role "student", clause "policy#catalog.4.2" with rule "RULE-CAT-04" and its text, and reason class "not-in-allowlist"
  And every claim cites user#alex, policy#catalog.4.2 and event#evt-4711, and every citation id exists in the evidence list
  And evidence positions are 0..n-1 with user, model, policy, event, then clock#<read_id>
  And session context resolved_entities is ["user#alex","model#deepseek-coder"]

Scenario: The LLM only connects, it never informs
  Given a prose writer that is called through the llm prose port
  When the S1 query is answered
  Then the port was called exactly once, with the evidence sections as data
  And the stored prose contains none of: user#alex, deepseek-coder, policy#catalog.4.2, student, not-in-allowlist, evt-4711
  And when the writer returns prose containing "alex" the whole prose is rejected and the writer is called once more
  And when the second attempt also contains a fact the turn fails with 503 LLM_PROSE_REJECTED and nothing is stored

Scenario: Unresolved references never produce a diagnosis
  When I submit "why was ghost_user_99 denied deepseek-coder"
  Then I get 200 ErrorBody ENTITY_NOT_FOUND with message "Entity Not Found in State: user#ghost_user_99."
  And no evidence, claims or diagnosis are returned
  And "why was alex denied imaginary-model" names model#imaginary-model, and both unknown names are listed in input order

Scenario: Resolution is exact and case-folded, never fuzzy
  Then "WHY WAS ALEX DENIED DEEPSEEK-CODER" resolves to user#alex and model#deepseek-coder
  And "why was ale denied deepseek-code" is ENTITY_NOT_FOUND naming user#ale and model#deepseek-code

Scenario: Existing entities without a matching clause or event cannot be confirmed
  When I ask why "sofia" (a student with no recorded denial) was denied "deepseek-coder"
  Then I get 200 ErrorBody CANNOT_CONFIRM with the checked list naming what was looked at
  And when I ask why "dr-vance" (a privileged user) was denied "deepseek-coder" the role is allowed, no clause explains a denial, and the answer is CANNOT_CONFIRM

Scenario: Follow-up resolves from the session context
  Given the S1 turn resolved model#deepseek-coder in this session
  When I submit "and what about mateo?"
  Then user#mateo is resolved against the provider and model#deepseek-coder comes from the session context
  And the diagnosis cites user#mateo and its denial event
  And in a fresh session the same text is a clarification ("name both a user and a model")

Scenario: Failures and reads are safe
  Given the estate fails to load, or the clock fails, or the prose writer is unavailable
  Then the turn returns the typed 503 and stores no answer, evidence or context change
  And after any answered turn the estate snapshot is identical (read-only)

Scenario: Determinism and speed
  When the S1 query is answered three times with a frozen clock in three fresh sessions
  Then the evidence membership, position sequence, citation set, claims and diagnosis class are identical every time (prose may differ)
  And each request completes far below 3 seconds
```

## Tasks / Subtasks

Full Ceremony: test first, then code, per subtask; commit per numbered task (conventional commits, **no co-author trailer**). Write and edit source with the file tools, never with shell/script strings containing escapes (three corruptions so far: stories 1.1 and 1.2). Test persistence on a **file** database as well as `:memory:`.

- [x] **Task 1: Domain - references, diagnosis, evidence, prose guard (pure)** (AC: 1-3) → `feat(story-1.3): pure domain for references, diagnosis and prose guard`
  - [x] 1.1 Fixture alignment (Annex 12.1 and follow-up): clause `policy#catalog.4.2` gets `rule = "RULE-CAT-04"` and text stating that deepseek-coder requires enrollment in CS-480 and the student role is not on the allowlist (missing course entitlement); add `event#evt-4713` (`access_denied`, `user#mateo`, `not-in-allowlist: policy#catalog.4.2`). Update `tests/unit/test_fixture_estate.py` accordingly; no DTO or schema change.
  - [x] 1.2 `src/domain/references.py`: deterministic extraction of the user and model references from an access-denial query (the shapes of the S1 variants in `tests/unit/test_intent.py`, typed `user#x` tokens, trailing punctuation stripped) and of the single reference of a follow-up (`what/how about X`); returns raw tokens in input order. No fuzzy matching, no LLM.
  - [x] 1.3 `src/domain/diagnosis.py`: pure `diagnose_access_denial(user, model, clauses, events, clock, ...) -> Diagnosis | Cannot` per contracts section 1: clause match rule (not-in-allowlist applies iff `user.role` is not in `model.allowed_roles`; quota/window clauses apply when the user's denial event cites them), fixed precedence `not-in-allowlist > quota > window`, denial-event match (type `access_denied`, `entity_ref` = user, `recorded_reason` cites a matching clause id), the `EvidenceSet` with ordered entries (user, model, clauses, events, clock; `position` 0..n-1; snippets within 500/2000 chars) and the structured claims (role, clause + rule + text, reason class), each citing the user, the clause and the event. Claim ids come from the caller (idgen), never generated here.
  - [x] 1.4 `src/domain/prose_guard.py`: `evidence_vocabulary(evidence) -> set[str]` (citation ids, bare ids, display names, roles, rule ids, reason classes, instants) and `scan_prose(prose, vocabulary) -> list[str]` (whole-word, case-folded, NFKC-normalised). Canonical strings: add `S_CNC`/`S_ENF` renderers and the reason `the query must name both a user and a model` to `canonical_strings.py`.
- [ ] **Task 2: Ports** (AC: 3, 4) → `feat(story-1.3): llm prose port`
  - [ ] 2.1 `src/ports/outbound/llm_prose.py`: `LlmProsePort.compose(prompt: ProsePromptDTO) -> Result[str]` exactly as contract OP-14 (`LLM_UNAVAILABLE` on failure). Update `tests/unit/test_ports_query_only.py` (it is an owned/generator port, not a provider port).
- [ ] **Task 3: Outbound adapters** (AC: 2, 3) → `feat(story-1.3): persist claims and evidence; simulated prose writer`
  - [ ] 3.1 `SqliteSessionStore.append_turn` persists `evidence`, `claims` and `claim_citations` of the answer in the same transaction (remove the story-1.2 guard) and `list_turns` returns them (evidence ordered by `position`, claims in id order with their citations). Respect the table CHECKs and FKs; test on memory **and** file databases; atomicity: a bad citation leaves no partial answer.
  - [ ] 3.2 `src/adapters/outbound/sim/prose_adapter.py`: deterministic simulated writer (no Ollama, no network): fixed connective sentences, **never** repeats any text of the evidence sections; supports failure injection (`fail()` -> `LLM_UNAVAILABLE`) and a hook for tests to script its output.
- [ ] **Task 4: Application - resolver, assembler, handler** (AC: 1-5) → `feat(story-1.3): access-denial diagnosis through the pipeline`
  - [ ] 4.1 `src/application/entity_resolver.py`: resolves references against `users_port`/`catalog_port` using `EntityKey` parsing and exact case-folded match; returns the resolved records or the list of unresolved keys in input order (typed key form `user#ghost`); session-context-first for follow-ups; a bare follow-up reference matching both a user and a model is a clarification (contracts P3).
  - [ ] 4.2 `src/application/evidence_assembler.py`: provider reads for the intent (`policy_port.for_model`, `event_store_port.query` over a fixed 30-day look-back ending at the turn's clock instant, half-open) turned into the domain `EvidenceSet`; any provider failure discards everything (`Failure`, AD-12).
  - [ ] 4.3 `src/application/access_denial_handler.py`: orchestrates extract -> resolve -> assemble -> diagnose -> prose (exactly one `compose` call, guard + one retry, `LLM_PROSE_REJECTED` after the second hit) -> `TurnOutput` (Answer with evidence/claims/diagnosis class, `resolved_entities`, or the canonical `ENTITY_NOT_FOUND` / `CANNOT_CONFIRM` / clarification outcome stored as a turn, D3). Claim ids and nothing else are minted via `IdGenPort`.
  - [ ] 4.4 Tests for every scenario above with real fixtures, the SQLite store, `SimClock` and a scripted prose port; include the AST audit (`src/application` imports no adapter) and the read-only proof (estate snapshot unchanged).
- [ ] **Task 5: Composition and REST** (AC: 2, 4, 5) → `feat(story-1.3): wire the handler into the container`
  - [ ] 5.1 `src/bootstrap.py`: register `LlmProsePort` (simulated) and `AnswerPipeline.register("diagnose_access_denial", handler)`; when the estate failed to load the handler returns the typed failure (503), the app still starts and `/readyz` already reports the estate.
  - [ ] 5.2 API tests through the real container: the S1 response validates against `SubmitQueryResponse` (all DTOs `extra="forbid"`), canonical outcomes are 200 `ErrorBody`, `GET /sessions/{sid}` returns the stored evidence/claims, **no endpoint is added** (the route audit stays green). Update the story-1.2 wiring/API expectations that assumed an observation-only S1 answer.
- [ ] **Task 6: Quality and DoD** (AC: 6) → `test(story-1.3): determinism, latency and DoD`
  - [ ] 6.1 Determinism x3 (membership, positions, citations, claims, class identical), latency (p95 well under 3 s), concurrency regression (the 1.2 NFR-6 tests still pass with the real handler), estate read-only proof.
  - [ ] 6.2 README (what an answer looks like), `ruff check src tests`, full `pytest` (0 skipped), Docker smoke of the S1 flow; update `docs/ai-decision-log.md`; promote the story in both `sprint-status.yaml` copies.

## Dev Notes

### Decisions and discrepancies found while creating this story (read first)

- **D1 - Annex 12.1 alignment.** The Impl-1 Annex expects the denial to explain a *missing course entitlement* and to cite *RULE-CAT-04*; the repo spec (PRD S1) explains a *role allowlist* via clause `policy#catalog.4.2`. Both are satisfied without new DTO fields: the existing clause fields carry `rule = "RULE-CAT-04"` and a text about enrollment in CS-480 / the student role not being on the allowlist; the diagnosis cites that clause verbatim. Fixture-only change.
- **D2 - What "matching clause" means.** `contracts.md` does not define clause matching. Decision: `not-in-allowlist` clauses apply iff `user.role` is not in `model.allowed_roles` (the catalog field is authoritative, the free-text `rule` is not parsed); `quota`/`window` clauses apply only when the user's denial event cites them. Fixed precedence `not-in-allowlist > quota > window` (contracts Q1). A privileged user for whom no clause applies is `CANNOT_CONFIRM`.
- **D3 - What "matching event" means.** `OperationalEvent` has no model field, so an event matches iff `type == access_denied`, `entity_ref` is the user and `recorded_reason` cites a clause id that applies. The denial event is **required** (FR-04: "a referenced denial event must exist"); the look-back is 30 days up to the turn's clock instant, half-open `[start, end)` (D40). Without it the answer is `CANNOT_CONFIRM`.
- **D4 - Canonical turns are stored.** As in story 1.2, `ENTITY_NOT_FOUND`/`CANNOT_CONFIRM` are returned as the 200 `ErrorBody` and also stored as an `answers` row (`canonical` set, `diagnosis_class` null; a `CANNOT_CONFIRM` answer keeps the evidence it gathered for audit, AD-8). `contracts.md` resolve_entities Q-fail says "no Answer is composed, context unchanged"; storing the turn keeps one uniform rule for all canonical outcomes and the turn is visible in `GET`. `resolved_entities` is only updated by successful resolutions. Confirm at review.
- **D5 - Simulated LLM.** The Impl-1 task needs no GPU or Ollama: OP-14 is implemented by a deterministic simulated writer. The guard (AD-8) lives in the domain and the call/retry orchestration in the application ring; the port only generates text. The writer must never echo evidence, so a scripted port in tests proves the guard rejects facts.
- **D6 - Reference extraction is rule-based and intent-scoped.** The classifier (story 1.2) routes; this story extracts references with deterministic patterns for the known S1 shapes. A routed query whose references cannot be extracted becomes a clarification (`the query must name both a user and a model`); extraction never guesses. Broader taxonomy and follow-up forms are story 3.4 / 3.1.
- **D7 - No new endpoints.** Everything flows through `POST /api/v1/sessions/{sid}/queries`; evidence/citation retrieval routes (`GET /answers/{aid}/evidence`, `/citations/{cid}`) belong to story 1.4 (outside Impl-1) and must not be added here. The structured claims, evidence list and positions are returned inside the `Answer`.
- **D8 - Annex 12.3 literal vs contract.** Annex Story 12.3 expects the message `User ghost_user_99 does not exist in cluster records`, while the contract's `S_ENF` is `Entity Not Found in State: {ref_list}.`. This story implements the contract literal; reconciling the Annex wording is story 4.1's decision (do not change `S_ENF`).
- **D9 - Audit still absent.** No `toolcall.*` rows (story 1.5), as recorded for 1.2; NFR-8 stays unmet in Impl-1.

### Architecture compliance (binding)

- **AD-1/AD-13:** only the read ports (`users`, `catalog`, `policy`, `event_store`) are used; nothing in the estate is written; a test snapshots the estate before/after. **AD-2:** diagnosis, claims, citations are pure functions of the `EvidenceSet`; the single prose call carries no facts and its output is never read for a field. **AD-7:** canonicalize to `{type}#{id}`, exact case-fold, no fuzzy, no LLM in resolution. **AD-8/AD-14:** claims bind >= 1 citation through the `claim_citations` join; citation ids are `{type}#{id}`/`clock#{read_id}` resolving to a unique evidence entry; positions 0..n-1. **AD-12:** every provider/LLM failure aborts the turn before anything is stored. **AD-11:** retrieved content (clause text, event reasons) is data placed in delimited evidence sections, never control.
- **R1-R4:** `src/domain` and `src/application` stay pure (no fastapi, sqlite3, randomness, wall clock, adapters); time only from the turn's `ClockReadDTO`; ids only via `IdGenPort`. The AST audit and ruff TID251 enforce it.
- **Contracts to match:** contracts.md section 1 `resolve_entities`, `assemble_evidence`, `diagnose_access_denial`, section 3 OP-14, section 4 (`S_ENF`, `S_CNC`, `LLM_PROSE_REJECTED`), section 0.4 (`Evidence`, `Claim`, `Answer`); SQL `evidence`, `claims`, `claim_citations` (existing, unchanged).

### Previous story intelligence (stories 1.1 and 1.2)

- The pipeline seam is ready: `AnswerPipeline.register(intent, handler)`; a handler receives `TurnInput` (session id, answer id, trimmed query, `ClockReadDTO`, the routing decision, the session context) and returns `Result[TurnOutput]` (`answer`, optional `canonical`, `resolved_entities`). `SessionService` already persists context (one `prior_intents`/`active_answer_ids` entry per Answer; `resolved_entities` superset, de-duplicated) and takes the clock read inside the per-session guard.
- `SqliteSessionStore.append_turn` currently refuses answers with claims/evidence (deferred to this story); `list_turns` returns empty claims/evidence. `AnswerDTO` validates `answer_chain` as a contiguous prefix and evidence positions `0..n-1`.
- Existing helpers: `Failure`/`Ok`, `fail()` (error catalog), `canonical_strings`, `parse_entity_key`/`key_matches`, `SimProviders` (all read ports over the fixtures), `SimClock`, `SimIdGen`, `Container.register_port`, `tests/unit/conftest.py` (`providers`, `fixtures_copy`), `tests/api/conftest.py` (`api` rig).
- Review lessons: tests of persistence must also run on a file database; timestamps validated as real instants; anything touched by the thread pool is locked; routes audited against the contract; classify precision matters (a query must never be force-routed); no raw shell/script strings for source edits; `ruff format` only files you create.
- Tests from story 1.2 that assumed an observation-only S1 answer through the **real container** (`tests/api/test_sessions_wiring.py`) must be updated; the unit/API rigs without a registered handler keep the observation-only behaviour.

### Files to create or touch

```
NEW  src/domain/{references,diagnosis,prose_guard}.py        EDIT src/domain/canonical_strings.py
NEW  src/ports/outbound/llm_prose.py                         EDIT src/ports/outbound/__init__.py
NEW  src/application/{entity_resolver,evidence_assembler,access_denial_handler}.py
NEW  src/adapters/outbound/sim/prose_adapter.py
EDIT src/adapters/outbound/db/session_store.py   src/bootstrap.py   README.md
EDIT fixtures/estate/{policy,events}.json   tests/unit/{test_fixture_estate,test_ports_query_only}.py
EDIT tests/api/test_sessions_wiring.py (S1 expectations)     tests/integration/test_session_store.py (guard test)
NEW  tests: unit (references, diagnosis, prose_guard, resolver, assembler, handler, prose adapter),
     integration (store persistence), api (S1 end to end), determinism/latency
```

Do **not** modify `planning/**`, `test/atdd/**`, `tests/support/**`, `src/dto.py`, the migrated schema, or add any route.

### Testing standards

Pytest, 0 skipped, no network/wall clock/sleep; frozen `SimClock`; real `SimProviders`, real SQLite (memory and file). Assert body semantics (ids, texts, classes, positions, citations), not status codes only. Mutation-check the key safeguards when practical (prose guard disabled -> the fact-in-prose test must fail; resolver made fuzzy -> the `ale`/`deepseek-code` test must fail). Corpus tests: all S1 variants resolve (100%), at least 10 non-existent references return `ENTITY_NOT_FOUND` with zero fabricated detail.

### Latest tech notes

No new dependency. Pydantic v2 DTOs (`ClaimDTO`, `EvidenceDTO`, `AnswerDTO`, `ProsePromptDTO`) are the contract; build them, never redefine. `str.casefold()` + NFKC for comparisons. Evidence snippets: <= 500 chars (policy <= 2000) per the table CHECK.

### References

- [Source: planning/epics.md#Story 1.3] - canonical story and ACs; Annex 12.1 in the task PDF
- [Source: planning/detailed-design/contracts.md#resolve_entities, #assemble_evidence, #diagnose_access_denial; #3.1 OP-14; #4 error catalog; #0.4 answer composition; #5 I2/I3/I4/I5]
- [Source: planning/ARCHITECTURE.md#AD-2, #AD-7, #AD-8, #AD-11, #AD-12, #AD-14]
- [Source: planning/prd.md FR-02, FR-03, FR-04, NFR-1, NFR-5; planning/ux/C-UX-Scenarios/scenario-1.md] - S1 fixture and expected chain
- [Source: planning/detailed-design/schemas/dto.py] `EvidenceDTO`, `ClaimDTO`, `AnswerDTO`, `ProsePromptDTO`; [schemas/001_module12_copilot_schema.sql] `evidence`, `claims`, `claim_citations`
- [Source: story files 1-1 and 1-2 (Dev Agent Record, Review Findings, deferred-work.md)]

## Dev Agent Record

### Agent Model Used

_(filled by dev-story)_

### Debug Log References

### Completion Notes List

### File List
