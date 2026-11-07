---
baseline_commit: 415689df044387b346e859835c6fe3688fe34c35
---

# Story 1.4: Structured claims, citation cards and evidence-level determinism

Status: done

<!-- Impl-2 foundations story, Flow B (test-along): code and its tests ship in the same commit.
     Most of the epic text already exists from story 1.3 (EvidenceSet, Claim, claim_citations,
     positions, persistence). This story adds only what is missing; see "What already exists". -->

## Story

As Nadia,
I want every factual assertion backed by a citation I can open, and the same question to always give the same evidence,
so that I can trust and reproduce what I relay.

## Acceptance Criteria

Source: `planning/epics.md` Story 1.4. Requirements: FR-13, FR-14, AD-8, AD-14, NFR-3, NFR-4. Contracts: `get_answer_evidence`, `get_citation`, `answer_query` Q4/L1/L3, `assemble_evidence` Q1/L1, §5 I2, I3, I5.

1. **Every claim is bound.** On every diagnosis answer (S1 access denial, S2 schedule window), each `Claim` has at least one citation, and each `citation_id` is exactly one entry of the same answer's `EvidenceSet`. `EvidenceSet` entries are unique by `citation_id` and `position` runs `0..n-1`. No answer has an uncited claim (FR-13, NFR-3, AD-8, AD-14).
2. **Unbound citation downgrades.** If a claim cites an id that is not in the answer's `EvidenceSet`, or the set has a duplicate `citation_id`, the claim is never rendered. The turn becomes the canonical `CANNOT_CONFIRM` with the literal `Cannot confirm (insufficient evidence): checked {checked_list}.`, the LLM is not called, and no claim is stored (FR-13, S-3, contracts `get_citation` L1).
3. **`GET /api/v1/answers/{aid}/evidence`.** It returns HTTP 200 and `{evidence: [...]}`: the stored `EvidenceSet` of that answer, ascending by `position` and unchanged. An unknown `aid` returns HTTP 404 `ENTITY_NOT_FOUND`. The route is read-only (contracts `get_answer_evidence` P2/Q1/L1).
4. **`GET /api/v1/citations/{cid}`.** For a `cid` in at least one stored `EvidenceSet`, it returns HTTP 200 and `{source_record, snippet}`. `source_record` is the current record from the read-only provider port (or the clock read, see D4) and `snippet` is the stored snippet. A `cid` that is malformed, cited by no answer, or whose source is no longer in state returns HTTP 404 with the body `Entity Not Found in State: {cid}.`. A provider failure returns HTTP 503 `PROVIDER_UNAVAILABLE`. Every citation of the S1 and S2 answers resolves through this route (100%, NFR-3).
5. **Determinism.** Three S1 runs, and three S2 runs, each on a fresh app with the clock frozen at the same start, produce identical evidence membership, `position` sequence, citation set (including `clock#...`), claim citations and `diagnosis_class`. Prose may differ (FR-14, NFR-4, contracts `answer_query` L3).
6. **Contract kept in sync.** The two routes are added to `SERVED_IN_THIS_STORY` in the route audit. `openapi.yaml`, `contracts.md` and `src/dto.py` change in the same commit as any shape change (D3, D4). Branch coverage of `src` stays at 90% or above, `ruff` is clean and the full `pytest` passes.

## Tasks / Subtasks

Flow B: each task's code and its tests are one commit. Do not commit code without its tests.

- [x] **Task 1: Citation-binding guard** (AC: 1, 2) -> `feat(story-1.4): citation-binding guard with S_CNC downgrade`
  - [x] 1.1 `src/domain/citations.py` (new, pure): `unbound_citations(claims: Sequence[ClaimDraft], evidence: Sequence[EvidenceDTO]) -> tuple[str, ...]`. It returns the cited ids absent from `evidence`, in claim order and deduplicated. A duplicate `citation_id` in `evidence` is also returned. An empty result means the answer is bound.
  - [x] 1.2 `src/application/turn_support.py`: add `bind_or_downgrade(turn, intent, drafts, evidence) -> TurnOutput | None`. On unbound ids it returns `canonical_turn(turn, intent, "CANNOT_CONFIRM", cs.cannot_confirm(<evidence citation ids in position order>), stored="CANNOT_CONFIRM", kept_evidence=evidence, entities=...)`. Call it in **both** handlers (`access_denial_handler._diagnose`, `window_diagnosis_handler`) **before** `write_prose` and `mint_claims`, so a downgrade spends no LLM call and no claim id. *Refined by I2-13 (user-approved): `kept_evidence` and the checked list keep each evidence id once (first entry, positions renumbered), so a duplicated id cannot break the `evidence` primary key. Code review: a claim with no citations is unbound too.*
  - [x] 1.3 Tests: `tests/unit/test_citations.py` covers bound, missing id, duplicate evidence id and order. Handler tests inject a diagnosis with a stray citation. Assert `CANNOT_CONFIRM` with the literal, `SimProse` call count 0, no claim ids drawn (the next `idgen` value is unchanged) and no claims stored.
- [x] **Task 2: Evidence and citation read use cases** (AC: 3, 4) -> `feat(story-1.4): get_answer_evidence and get_citation`
  - [x] 2.1 `SessionStorePort` (`src/ports/outbound/session_store.py`) gets two query-only methods, implemented in `SqliteSessionStore`:
        - `answer_evidence(answer_id) -> Result[list[EvidenceDTO] | None]`: `None` when no `answers` row exists. Reuse `_evidence_of`, which already orders by `position`.
        - `cited_snippet(citation_id) -> Result[str | None]`: the snippet of the most recent stored answer that cites it, ordered by `evidence.created_at DESC, answer_id DESC`, so the choice is deterministic. Compare `citation_id` exactly, because stored ids are canonical.
  - [x] 2.2 `EventStorePort.get(event_id) -> Result[OperationalEventDTO | None]` is a new query-only method (D3). Implement it in `fixtures_adapter.py` over the existing event `RecordStore`, and amend contracts.md OP-9 in the same commit.
  - [x] 2.3 New inbound port `src/ports/inbound/evidence_use_cases.py` (`EvidenceUseCases`: `get_answer_evidence`, `get_citation`), exported from `src/ports/inbound/__init__.py`. Implementation goes in `src/application/evidence_service.py` (new). Keep it separate from `evidence_assembler.py`, which is the story-1.3 provider gather and unrelated.
        - `get_citation`: (a) a `cid` that does not match `CitationId` gives `ENTITY_NOT_FOUND`. (b) `cited_snippet` returns `None`: `ENTITY_NOT_FOUND`. (c) Dispatch on the type prefix to `users/catalog/policy/groups/jobs/nodes/reservations/windows/event_store.get`. For `clock#`, see D4. (d) The provider returns `None`: `ENTITY_NOT_FOUND`. (e) The provider returns a `Failure`: pass it through (`PROVIDER_UNAVAILABLE`). Build the failure with `error_catalog.fail("ENTITY_NOT_FOUND", ref_list=cid)` so the body is the `S_ENF` literal.
        - Use the dispatch table as the single map from `type` to port. The NFR-10 seam is that a new entity type adds one row.
  - [x] 2.4 Wire it in `src/bootstrap.py` with `register_port(EvidenceUseCases, ...)`. Mirror how `SessionUseCases` falls back to `UnavailableSessionUseCases` when the DB is broken: add the same fallback so the routes return a 503 `ErrorBody` and never crash.
  - [x] 2.5 Tests: unit tests for the service on a real in-memory SQLite store and the real `SimProviders`. Do not mock the service. Cover each 404 branch, the 503 pass-through, the clock path, an event citation, and the store returning the snippet of the most recent answer.
- [x] **Task 3: Routes and contract** (AC: 3, 4, 6) -> `feat(story-1.4): evidence and citation routes`
  - [x] 3.1 `src/adapters/inbound/evidence.py` (new router, `tags=["evidence"]`, prefix `/api/v1`): `GET /answers/{aid}/evidence` and `GET /citations/{cid}`. Follow `sessions.py` exactly: thin route, `failure_response` for failures, `model_dump(mode="json")`. `cid` is a plain `str` path parameter. Pattern validation lives in the use case, because openapi declares only 404/503 for this route and a FastAPI pattern would return an undeclared 400. `cid` contains `#`: clients must send it percent-encoded (`user%23alex`), and the test client does too. Include the router in `app.py`.
  - [x] 3.2 `tests/api/test_contract_routes.py`: add both routes to `SERVED_IN_THIS_STORY` with the comment `# story 1.4`.
  - [x] 3.3 `openapi.yaml`, `src/dto.py` and `contracts.md` changes for D4 (clock source record).
  - [x] 3.4 API tests in `tests/api/test_evidence_api.py` over the real container, as `test_sessions_wiring.py` does: 200 shape, 404 bodies, ordering, read-only (two GETs return identical bodies, and the session and turn count are unchanged).
- [x] **Task 4: ATDD suite and determinism** (AC: 1, 4, 5) -> `test(story-1.4): ATDD citation coverage and 3x determinism`
  - [x] 4.1 Create `tests/atdd/` (with `__init__.py` if the suite layout needs one) and `tests/atdd/test_story_1_4.py`. It calls the real app through `create_app(Settings.from_env({}))`, not the `api` fixture with overrides.
        - Citation coverage: for S1 (`why was alex denied deepseek-coder`) and S2 (`why can't group 4 run their fine-tuning job`), every claim citation is in `evidence`, and every evidence `citation_id`, `clock#` included, resolves through `GET /citations/{cid}` with 200. The returned `snippet` equals the evidence snippet.
        - Determinism: three runs, each on a **fresh** app (fresh clock and idgen, the lesson recorded in decision-log AD-21). Compare evidence `(citation_id, source_type, snippet, position)`, the sorted citation set, the claim-citation lists and `diagnosis_class`. Do not compare `prose`.
        - Use the stub `test/atdd/module12_contracts.test.py::test_get_answer_evidence_*` / `test_get_citation_*` only as a source of cases. Never import it.
  - [x] 4.2 Run the full `pytest` and run `make` coverage (`pytest tests --cov=src --cov-branch --cov-fail-under=90`) and `ruff`. Write the coverage log to `docs/evidence/impl2/flow-b-1-4-coverage.log`, generated by the tool and never hand-edited. Add the decision-log entry `I2-NN` (next free number) for D3/D4. Add the walkthrough line. Set sprint status to `review` in **both** copies.

### Review Findings

- [x] [Review][Patch] A claim with zero citations passes the binding guard: it spends the LLM call, then `mint_claims` raises a pydantic `ValidationError` (untyped 500) instead of the `S_CNC` downgrade (AC 1, D1) [src/domain/citations.py:16]
- [x] [Review][Patch] `GET /answers/{aid}/evidence` returns 503 `PROVIDER_UNAVAILABLE` (store failure, broken-DB fallback, Task 2.4) but openapi declares only 200/404 and contracts.md lists no 503 (AC 6) [planning/detailed-design/schemas/openapi.yaml:221]
- [x] [Review][Patch] contracts.md `get_citation` heading still says `source_record: Record`; Q1 says `Record | ClockRead` (D4) [planning/detailed-design/contracts.md:439]
- [x] [Review][Patch] `test_both_routes_are_read_only` asserts no status: two identical 404/503 bodies would pass [tests/api/test_evidence_api.py:122]
- [x] [Review][Patch] A `cid` with an encoded slash (`%2F`) misses the route and gets the framework's `{"detail": "Not Found"}` instead of the `S_ENF` body (D6) [src/adapters/inbound/evidence.py:41]
- [x] [Review][Patch] Story text Task 1.2 / D2 still say `kept_evidence=evidence`; the user-approved I2-13 refinement (dedupe + renumber) is only in the Dev Agent Record [this file, Task 1.2 / D2]
- [x] [Review][Defer] `clock#` read ids restart at `clk-…0001` per process and are not seeded by `highest_counters`, so with a file-backed DB `GET /citations/clock#…` can return another run's clock read and snippet [src/adapters/outbound/sim/clock_adapter.py:35] — deferred, pre-existing (story-1.3 deferred item "id counters are seeded only for session/answer"); this story only makes it observable

## Dev Notes

### What already exists (do not rebuild)

| Epic item | Where it lives today | State |
|---|---|---|
| `EvidenceSet`, monotonic `position` | `src/domain/diagnosis.py` `_number`/`number_evidence`; `AnswerDTO._validate_chain_and_positions` (E21) | done (1.3) |
| Structured `Claim` with ≥ 1 citation | `ClaimDraft`, `_claims`; `ClaimDTO.claim_citations min_length=1`; `turn_support.mint_claims` | done (1.3) |
| SQL `evidence`, `claims`, `claim_citations` | `migrations/001_...sql`. FK `(answer_id, citation_id) -> evidence` is the physical backstop, and the PK dedupes. `SqliteSessionStore.append_turn` / `_evidence_of` / `_claims_of` persist and read them back | done (1.3) |
| Clock read as citable evidence | `_clock_entry` -> `clock#{read_id}`, snippet `clock read {read_id} at {instant}` | done (1.3) |
| Diagnoser purity | `tests/unit/test_diagnosis.py` (same inputs, input order), `test_window_diagnosis_handler.py::test_a_turn_is_deterministic` | partial: unit only, no 3× app-level S1 run |
| `ExplanationDTO` | `src/dto.py:156` | exists, unused by this story |
| `GetAnswerEvidenceResponse`, `GetCitationResponse` DTOs | `src/dto.py:525-541` | DTOs exist, no route |

**Missing, and therefore this story's scope:** an explicit binding guard with the `S_CNC` downgrade (today an unbound citation would only fail at the SQLite FK as a retryable 503), the two GET routes with their use cases and store queries, `EventStorePort.get`, and app-level citation-coverage and 3× determinism tests.

**Out of scope:**
- The visual citation cards are story 1.7 (React console). No `console/` directory exists yet. This story supplies the card data (`/citations/{cid}`).
- The audit events `toolcall.evidence.get` / `toolcall.citation.get` are story 1.5 (no audit writer exists; deferred-work 1-1 and 3-1).
- The `ExplanationDTO` rule ids.

### Decisions

- **D1 - Guard placement.** The binding check is a pure domain function, applied in the shared `turn_support` before the prose call. It does not raise from the DTO: a validator that raises would turn into an unhandled 500. Do **not** add the check to `AnswerDTO`. The SQLite FK stays as the backstop.
- **D2 - `checked_list` for the downgrade.** The evidence citation ids in `position` order, through `cs.cannot_confirm(...)`. Never hand-format the literal. Each id appears once (I2-13).
- **D3 - `EventStorePort.get`.** `get_citation` must return the source record of `event#evt-4711`, and OP-9 has only `query(entity, type, window)`. Add a query-only `get`, as every other entity port has. It stays read-only (AD-1, AD-13 hold: no write path). The `test_ports_query_only.py` audit must still pass, so name it `get`. Amend contracts.md OP-9 "Operations" in the same commit.
- **D4 - Clock citations (test-design T-11 / P0-G9, open until now).** A clock read cannot be re-read from `clock_port`, and `Record` has no clock member. Decision: `GET /citations/clock#{read_id}` resolves. `source_record` is a `ClockReadDTO` rebuilt by a domain inverse of `_clock_entry`: `clock_read_from_entry(citation_id, snippet) -> ClockReadDTO | None`, which lives next to `_clock_entry` in `diagnosis.py` and has a round-trip unit test. Change `GetCitationResponse.source_record` to `Union[RecordDTO, ClockReadDTO]` in `dto.py`, and to `oneOf [Record, ClockRead]` in `openapi.yaml` (add a `ClockRead` schema: openapi has none today). Update the `get_citation` Q1 line in contracts.md. A snippet that does not parse is `ENTITY_NOT_FOUND`.
- **D5 - Which snippet `get_citation` returns.** The route takes no `answer_id`, so it returns the snippet of the most recent answer that cites the `cid`. Snippets are a deterministic function of the record, so answers citing the same record carry the same snippet unless the estate changed. Session reset does not delete turns (`reset` only clears context), so citations stay resolvable after a reset.
- **D6 - Malformed `cid` is 404, not 400.** openapi declares 404/503 only, and a malformed id cannot resolve to a source, which is contract P2.

### Files

| File | Change |
|---|---|
| `src/domain/citations.py` | NEW: `unbound_citations` |
| `src/domain/diagnosis.py` | UPDATE: add `clock_read_from_entry`. Do not change `_clock_entry`'s format, because snippets are already stored |
| `src/application/turn_support.py` | UPDATE: `bind_or_downgrade` |
| `src/application/access_denial_handler.py`, `window_diagnosis_handler.py` | UPDATE: call the guard before prose. Preserve the order "missing entity > clarification" (I2-11) and the 4.1 parity tests |
| `src/application/evidence_service.py` | NEW |
| `src/ports/inbound/evidence_use_cases.py`, `__init__.py` | NEW / UPDATE |
| `src/ports/outbound/session_store.py`, `src/adapters/outbound/db/session_store.py` | UPDATE: two queries, under the store lock (`_run`) like every method there |
| `src/ports/outbound/event_store.py`, `src/adapters/outbound/sim/fixtures_adapter.py` | UPDATE: `get` |
| `src/adapters/inbound/evidence.py`, `app.py` | NEW / UPDATE |
| `src/bootstrap.py`, `src/application/unavailable.py` | UPDATE: wiring and the unavailable fallback |
| `src/dto.py`, `planning/detailed-design/schemas/openapi.yaml`, `planning/detailed-design/contracts.md` | UPDATE (D3, D4) |
| `tests/unit/test_citations.py`, `tests/unit/test_evidence_service.py`, `tests/api/test_evidence_api.py`, `tests/atdd/test_story_1_4.py`, `tests/api/test_contract_routes.py` | NEW / UPDATE |

### Guardrails (docs/impl2-rules.md)

- Use the `src/{domain,ports,application,adapters}` layout, not the `service/...` paths in epics.md (AD-03). `test_architecture_imports.py` enforces that the domain, ports and application rings import no adapter or framework.
- Time comes only from the Clock port, and ids only from `idgen_port`. The guard must run before `mint_claims`, so a downgrade draws no claim id.
- Registered routes must equal `openapi.yaml` in the route audit. Update both together.
- The LLM never states a fact. The guard runs before prose, and a downgrade never calls the LLM.
- No `sleep` / `waitForTimeout`. Never mock the unit under test. Assert on stored state and on what did not happen (no prose call, no claim row, no estate change).
- Keep both `epics.md` copies and both `sprint-status.yaml` copies identical (`_bmad-output/implementation-artifacts/` and `implementation-artifacts/`).

### Previous-story intelligence

- 1.3 D7 deliberately left these two routes for 1.4.
- 4.1 / I2-11: compare every **non-clock** citation across separate sessions in the same app, because clock read ids advance. For 3× determinism use fresh apps, so `clock#clk-0000000000000001` is identical every time.
- I2-12 (Flow C): coverage regressions were caught by new tests. Run coverage before committing, not after.
- Deferred 3-1: diagnosers emit no tool-call audit yet. Do not start the audit here.

### Git intelligence

The last commits are CI (`ci: move the quality gate to GitHub Actions with k6 and Playwright traces`, `fix banned-waits step`) and Flow C test backfill. The banned-waits CI step greps `src`, `tests` and the console, so do not introduce sleeps, even in a helper. No new library is needed: FastAPI, Pydantic v2 and stdlib `sqlite3` are already pinned.

### References

- [Source: planning/epics.md#Story 1.4]
- [Source: planning/detailed-design/contracts.md#get_answer_evidence, #get_citation, #answer_query (Q4, L1, L3), #assemble_evidence, §5 I2/I3/I5, OP-9]
- [Source: planning/detailed-design/schemas/openapi.yaml `/api/v1/answers/{aid}/evidence`, `/api/v1/citations/{cid}`, `GetCitationResponse`, `Record`]
- [Source: planning/detailed-design/schemas/001_module12_copilot_schema.sql `evidence`, `claims`, `claim_citations`]
- [Source: test/test-design.md R-05, R-07, T-11, P0-G9]
- [Source: _bmad-output/implementation-artifacts/1-3-...md D7; deferred-work.md]
- [Source: docs/impl2-rules.md Code rules, Test rules]

## Dev Agent Record

### Agent Model Used

claude-opus-5-5 (Claude Code, `bmad-dev-story`)

### Debug Log References

- Mutation check for Task 1: with the guard disabled, 4 of the 6 handler-binding cases fail (the 2 that pass are the "bound answer is untouched" controls).
- `ruff format` over `src/` reformatted the hand-aligned `src/dto.py` and `src/domain/intent.py`. Both were reverted to HEAD and only the D4 line was reapplied. `ruff format --check` lists 13 files both before and after the story, so none are new.
- New abstract `EventStorePort.get` broke two test doubles (`_FailingEvents`, `_RecordingEvents`). Both gained a `get`.
- `test_dto_contract.py` requires `src/dto.py` to equal `planning/detailed-design/schemas/dto.py` byte for byte, so the D4 change is in both.

### Completion Notes List

- Story context created 2026-11-07, scoped against `src/` at `415689d`. Ultimate context engine analysis completed - comprehensive developer guide created.
- Task 1: `domain/citations.unbound_citations` (pure). `turn_support.bind_or_downgrade` runs in both handlers before prose and before `mint_claims`. Tests prove `S_CNC` with the literal, 0 LLM calls, no claim id drawn and no claim stored, for a stray citation and a duplicated evidence id, in S1 and S2.
- **Refinement (confirmed by the user 2026-11-07, log I2-13):** the downgrade keeps each evidence id once (first entry, positions renumbered) instead of the raw set. A duplicated id would otherwise break the `evidence` PK and turn the downgrade into a 503, so AC 2 would not hold. The handler test stores the downgraded turn to prove it persists.
- Task 2: `SessionStorePort.answer_evidence` / `cited_snippet` (under `_run`). `EventStorePort.get` (D3). `diagnosis.clock_read_from_entry` (D4). `EvidenceService` with one dispatch table from type to port, plus a test that it covers every citation type but `clock`. `UnavailableEvidenceUseCases` fallback wired in `bootstrap.py`.
- Task 3: `adapters/inbound/evidence.py` (plain `str` cid, D6), router included in `app.py`. Route audit updated. openapi `ClockRead` + `oneOf`, dto `Union[RecordDTO, ClockReadDTO]` in both copies, contracts.md OP-9 and `get_citation` Q1 amended.
- Task 4: `tests/atdd/test_story_1_4.py` on `create_app(Settings.from_env({"M12_CLOCK_START": ...}))`. Every claim is bound, every S1/S2 citation (`clock#` included) resolves with the stored snippet, and 3 fresh-app runs with a frozen clock are identical (evidence tuples, citation set, claim citations, class). No `__init__.py` was needed (`--import-mode=importlib`).
- Gate: 1089 passed, branch coverage 96.84% (>= 90%), `ruff check .` clean, `test/ci/schema_check.py` passes. Log: `docs/evidence/impl2/flow-b-1-4-coverage.log`.
- Not done: commits. By the user's decision, the per-task commits are made after the code review.

### File List

- `src/domain/citations.py` (new)
- `src/domain/diagnosis.py`
- `src/application/turn_support.py`
- `src/application/access_denial_handler.py`
- `src/application/window_diagnosis_handler.py`
- `src/application/evidence_service.py` (new)
- `src/application/unavailable.py`
- `src/ports/inbound/evidence_use_cases.py` (new)
- `src/ports/inbound/__init__.py`
- `src/ports/outbound/session_store.py`
- `src/ports/outbound/event_store.py`
- `src/adapters/outbound/db/session_store.py`
- `src/adapters/outbound/sim/fixtures_adapter.py`
- `src/adapters/inbound/evidence.py` (new)
- `src/adapters/inbound/app.py`
- `src/bootstrap.py`
- `src/dto.py`
- `planning/detailed-design/schemas/dto.py`
- `planning/detailed-design/schemas/openapi.yaml`
- `planning/detailed-design/contracts.md`
- `tests/unit/test_citations.py` (new)
- `tests/unit/test_citation_binding_handlers.py` (new)
- `tests/unit/test_evidence_service.py` (new)
- `tests/unit/test_ports_query_only.py`
- `tests/unit/test_access_denial_handler.py`
- `tests/unit/test_evidence_assembler.py`
- `tests/api/test_evidence_api.py` (new)
- `tests/api/test_contract_routes.py`
- `tests/atdd/test_story_1_4.py` (new)
- `docs/evidence/impl2/flow-b-1-4-coverage.log` (new, tool output)
- `docs/ai-decision-log.md`
- `walkthrough-impl2.md`
- `implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Change Log

- 2026-11-07: Implemented story 1.4 (Flow B). Citation-binding guard with the `S_CNC` downgrade, `get_answer_evidence` / `get_citation` use cases and routes, `EventStorePort.get` (D3), clock citations (D4), ATDD citation coverage and 3x determinism. Contract docs amended (log I2-13). Status -> review.
- 2026-11-07: Code review (Blind Hunter, Edge Case Hunter, Acceptance Auditor). 6 patches applied: `is_bound` rejects uncited claims; 503 declared on `get_answer_evidence` (openapi + contracts.md); `get_citation` heading `Record | ClockRead`; read-only test asserts status; `{cid:path}` so an encoded `/` gets `S_ENF`; Task 1.2 / D2 note I2-13. 1 deferred (clock read ids across restarts). Gate: 1094 passed, branch coverage 96.84%, ruff clean, schema check passes (`docs/evidence/impl2/flow-b-1-4-review-coverage.log`). Status -> done.
- 2026-11-07: Test audit (Ice Cream Cone, Flaky Sleeper, Mocking Mirage, Blindly Green). The guard mutant (`bind_or_downgrade` never downgrades) fails 6 tests. Mutants M2-M5 survived the full suite; the tests were strengthened (no production code changed, no assertion loosened): each citation type resolves through its own port; D5 recency and tie-break cases where id order and scan order disagree with `created_at`; S1/S2 evidence order and claim citations pinned in the 3x determinism test; read-only service reads assert success; ATDD checks the record's identity field; `bend` forwards kwargs. M2, M3, M4 and M5 now each fail a story test. Gate: 1104 passed, branch coverage 96.84%, ruff clean, schema check passes (`docs/evidence/impl2/flow-b-1-4-test-audit-coverage.log`).
