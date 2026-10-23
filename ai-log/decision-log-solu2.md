# AI Decision Log — Solu-2 (Module 12: AI Operations Copilot)

## S-01 — Core operations

**OP-A — `answerQuery(queryText, sessionId, now)`**
Turns a complaint into a cited, explainable diagnosis.

**OP-B — `proposeDestructiveAction(...)` → `confirmAndDispatch(...)`**
The only mutation path, and the one that can be raced or repeated.

**OP-C — `resolveEntities(references, sessionId)`**
Resolves every entity to a real record, or returns `Entity Not Found in State`.

---

## Pair attribution

The unit is a **pair** submission; roles swap in Phase 3.

| Tag | Partner | Led |
|---|---|---|
| **JL** | Julio — **Architect-lead** | Phases 0–2 (contracts, ports/adapters, schemas); **Reviewer** in Phase 3 |
| **TL** | Test-lead partner | Phase 3 (TEA test preparation); Reviewer of the Phase 0–2 artifacts |

Every entry below names the owning partner; where a call was joint it is written `JL+TL`.

---

## D52–D68 — Phase 1–2 gate: dual-lens review corrections

**Provenance:** Human judgment (**JL** — Architect-lead), 2026-10-16. The two-lens adversarial/edge-case review of the
detailed design (`planning/reviews/review-detailed-design.md`) produced 80 findings; 74 were
**Accepted**, 5 **Deferred** (A13 `refused` reserved, A29 FK path unexercised, E27/E28 covered by
runtime tests, E49 cosmetic), and 1 **Rejected** (E29 — the `Instant` ms-or-none pattern is
intentional). Accepted fixes are owned by the decisions below (plus amendments to
AD-2/3/5/7/10/11/13/15 and D31/D33/D46/D47/D51). Each decision was folded into the artifacts before
the Phase 2.3 gate.

### D52 — Input normalization and the `diagnose_node_triage` inversion (A1, E1, E15)
**Decision.** `QueryText` is trimmed once and the empty/length tests run on the same trimmed value
(E1). `diagnose_node_triage` P3 is corrected: a *present matching* `error_code` is accepted; the miss
case is a `null` or non-matching code (A1). `get_state_record` validates `{id}` against the
`{type}#{id}` shape before lookup (E15).
**Rationale.** The original P3 rejected a present code — a logic inversion; the length test ran on
raw vs trimmed input inconsistently; a malformed id otherwise fell through to an unspecified 404/500.
**Artifact changed.** `contracts.md` §0.1 `QueryText`, §1 `diagnose_node_triage` P2/P3, §2
`get_state_record` P1b.

### D53 — `answer_query` layer reclassification (A3)
**Decision.** `answer_query` is labeled an **Application orchestrator**, not a pure Core Domain
function, because it performs I/O and calls `llm_prose_port`, which contradicts §0.6's "Core Domain =
no I/O, no LLM".
**Artifact changed.** `contracts.md` §1 header/`answer_query` Layer, §6 coverage row.

### D54 — `CanonicalCode` reconciliation and compound enforcement (A4, A5, E17)
**Decision.** `CanonicalCode = {ENTITY_NOT_FOUND, CANNOT_CONFIRM, CLARIFICATION,
INTENT_NOT_SUPPORTED, ACTION_REFUSED}`. `PROVIDER_UNAVAILABLE`/`VALIDATION_ERROR` are removed (a
provider failure produces no `Answer`; validation errors are HTTP 400). `INTENT_NOT_SUPPORTED` is
added. `AnswerEnvelope` with a compound classification requires `len(answers) >= 2`.
**Artifact changed.** `contracts.md` §0.4, §2 `submit_query` Q4; `dto.py`, `openapi.yaml`,
`events.schema.json`, `001_module12_copilot_schema.sql` `answers.canonical`.

### D55 — Destructive dry-run: selector source, node actions, terminal/empty handling (A7, E2, E3, E11, E12, E39)
**Decision.** Job actions enumerate via `jobs_port.select`; node actions via a new
`nodes_port.select` (OP-6) with `target_refs` populating `Selector.params.node_ids`. `(action,
entity_type)` compatibility is validated pre-dry-run (`VALIDATION_BAD_ACTION`). Terminal-status items
are enumerated with `actionable == false`; a zero-actionable dry-run disables confirmation and is not
re-dispatchable. Empty/no-future policy windows yield `schedule_no_constraint` / `next_open_window =
null`. SQL allowlists `selector.method`.
**Artifact changed.** `contracts.md` §1 `propose_destructive_action`, §1 `diagnose_schedule_window`,
§3 OP-6, §2 `post_re_dispatch`; `001_module12_copilot_schema.sql` `proposals.selector`.

### D56 — One LLM-prose / runbook latency budget (A8, A9)
**Decision.** The single LLM prose call is `p95 <= 3000 ms` everywhere (was `1500` in one place,
`3000` in another). `get_runbook` is a pure registry read budgeted `< 50 ms`, not the 5000 ms
end-to-end generation budget.
**Artifact changed.** `contracts.md` §1 `answer_query` latency, §2 `get_runbook`, §3.1 OP-14.

### D57 — Canonical-string single source of truth (A10)
**Decision.** The canonical-strings table owns the exact literals (with `{...}` slots); §4 templates
are byte-identical to them. `S_ENF` → `Entity Not Found in State: {ref_list}.`; `S_RBX` → `no
runbook available for code {code}.`
**Artifact changed.** `contracts.md` canonical table, §1 `lookup_runbook` Q4, §2 `get_runbook`, §4.

### D58 — Canonical 200 wire shape and audit-page total (A14, E36)
**Decision.** A 200 canonical response is an `ErrorBody` whose `message` is the canonical literal
(never a bare string). `GetAuditPageResponse` carries `total` + `has_more`.
**Artifact changed.** `contracts.md` §2 preamble/`submit_query`; `openapi.yaml`; `dto.py`.

### D59 — Event id minting and event-log guards (A20, E23, E24, E37, E43)
**Decision.** `IdKind` gains `event`; event ids are minted by `idgen_port` as
`evt-[0-9a-f]{16}` (or an injected estate key), never a random ULID. `answer_chain` on
`answer_produced` has `minItems: 1`. `claim_count >= 1 ⇒ evidence_count >= 1`. `proposal_lifecycle`
admits only the legal transition set. The seeded idgen persists its counter across restarts.
**Artifact changed.** `contracts.md` §0.1, §3.1 OP-13; `events.schema.json`, `events.md`, `dto.py`.

### D60 — Invariant scoping and `answer_chain` contiguity (A21, E18, E50)
**Decision.** Operation/route/port-local invariants are written `L…`; the global table keeps `I1…I22`
(no bare-`I1` ambiguity). `answer_chain` is validated as a contiguous prefix (DTOS + event schema).
**Artifact changed.** `contracts.md` §1 scope note and all local `I→L` labels; `dto.py`
`AnswerDTO`; `events.schema.json`.

### D61 — Vocabulary closure, `RawRef` escaping, group-member typing (A22, E31, E45)
**Decision.** Define `ResolvedEntity`, `ResolvedEntitySet`, `Diagnosis`, `IntentCode`, `EventQuery`,
`Session`, `Turn`, `ToolCall`, `Intent`. A literal `#` in operator text is escaped `\#`. `groups_port`
`members` must be `user` keys.
**Artifact changed.** `contracts.md` §0.1/§0.4/§0.5, §3 OP-4.

### D62 — Ports-and-adapters naming and diagram direction (A23, A25)
**Decision.** R1 heading renamed to `service/core/` (the component that exists). Diagram arrows for
the driven adapters point **at** the outbound port (`ADB/ASIM/ALLM → PORTSOUT`), matching
dependency inversion.
**Artifact changed.** `ports-and-adapters.md` R1, §3 diagram.

### D63 — `executor_port` gets a number and signature (A24)
**Decision.** `executor_port` is **OP-15** (`dispatch(request: ExecutorRequest) -> ExecutorResult`,
`get(proposal_id)`) in `contracts.md` §3.1; its wire form remains §2.
**Artifact changed.** `contracts.md` §3.1, §6; `ports-and-adapters.md` §1/§4.

### D64 — Path/body separation and pagination bounds (A26, E13, E48)
**Decision.** `SubmitQueryRequest` is body-only `{query_text}` (the path `{sid}` is supplied by the
route; a body `session_id` mismatch is rejected). GET request DTOs model path/query parameters, not a
body. `browse_state` bounds `page` (`page <= 10_000 / page_size`) and defines out-of-range pages as
empty items + total.
**Artifact changed.** `dto.py`; `openapi.yaml`; `contracts.md` §2 `browse_state`.

### D65 — `SessionWithTurns` composition (A27)
**Decision.** `SessionWithTurns` is a standalone `additionalProperties:false` object (Session fields
+ `turns`), not `allOf` over `Session` (whose `additionalProperties:false` rejected `turns`).
**Artifact changed.** `openapi.yaml`.

### D66 — Schema hardening (A12, A28, E7, E14, E19, E20, E21, E22, E26, E38, E40, E41, E42, E47)
**Decision.** Persist session expiry (`expired_at`); idle age uses `coalesce(last_turn_at,
created_at)`. `audit_events.session_id` is required for session-scoped types. `operator_role`
requires a 1..32 suffix. `claims.text` is non-empty. Evidence positions are contiguous (composer
assertion + UNIQUE backstop). `proposals.gate_token` is UNIQUE. Rotation is single-writer inside
`BEGIN IMMEDIATE`. `context_*` elements are strings (trigger). `affected_items` is a JSON array.
Reservation/policy windows require `start < end`. Audit chronology sorts by `(timestamp, audit_id)`.
Out-of-cap audits return an empty page with the retained total.
**Artifact changed.** `001_module12_copilot_schema.sql`; `contracts.md` §0.3/§2.

### D67 — Cross-check X-02 / X-16 resolution (A30)
**Decision.** `evidence` is removed from `IdKind` (no independent evidence id; `citation_id` is a
provider key). `VALIDATION_BAD_ID_KIND` is marked **internal-only** (raised by OP-13; no ingress route
returns it). Both cross-check rows are closed so the frozen contract has no open decisions.
**Artifact changed.** `contracts.md` §0.1; `dto.py`; `001_module12_copilot_schema.sql` header;
`openapi.yaml` `x-error-catalog`; `phase-2.3-cross-check.md` X-02/X-16.

### D68 — `resolve_entities` reference cap (E30)
**Decision.** `references` is capped at 32 elements (`VALIDATION_MALFORMED_BODY` beyond) to bound
per-request resolution work.
**Artifact changed.** `contracts.md` §1 `resolve_entities` P1.

**Status:** All Accepted Phase 1–2 gate findings folded in; Deferred/Rejected items remain recorded in
`planning/reviews/review-detailed-design.md`. Gate open.

---

## D69 — Plan-2 readiness reconciliation (epics · NFR coverage · UX-state coverage · prior-review triage)

**Provenance:** **JL+TL** (joint), 2026-10-16 — six-check implementation-readiness audit.

**Decision.**
- **Canonical epics.** `planning/epics.md` (4 epics / 16 stories, Story 1.1–4.3) is the single source
  of truth for this unit. The Phase-4 BMad output `_bmad-output/planning-artifacts/epics.md`
  (3 epics / 23 stories) is marked **superseded**; every story binding in
  `test/traceability-matrix.md` now points at `planning/epics.md`.
- **NFR traceability.** An explicit **NFR Coverage Map** (NFR-1..NFR-11 → story) was added to
  `planning/epics.md`; NFR-5/6/9/10 gained story `Requirements:` lines and AC clauses (previously
  orphaned).
- **UX-state coverage.** A **state → contract → DTO** table was added to
  `test/traceability-matrix.md` §4b, covering all fifteen states in
  `planning/ux/EXPERIENCE.md` §State Patterns (`Loading`/`Empty` are client-only by design).
- **Prior-review triage.** Triage records now exist for **every** review: `review-arch-implementability`
  (24 Accept / 1 Defer / 1 Reject — 23 folded in) and the previously untriaged
  `review-arch-adversarial` (18 findings) and `review-arch-edge-cases` (19 findings) were triaged
  against the current artifacts.

**Artifact changed.** `planning/epics.md`; `test/traceability-matrix.md`;
`_bmad-output/planning-artifacts/epics.md` (superseded banner);
`planning/reviews/review-arch-implementability.md`, `review-arch-adversarial.md`,
`review-arch-edge-cases.md` (triage records).

**Residual (one item, explicitly open).** Review finding 21a / adversarial finding 5 — the clock
citation `clock#<read_id>` (AD-14) is not addressable: no `GET /api/v1/state/clock/{id}` route exists
and no UX non-clickable decision has been taken. This is an Architect/UX Phase-0 decision, tracked as
gap **P0-G9 / T-11** in `test/test-design.md`. It cannot be closed by a Phase-1–2 document edit and is
the only Accepted prior-review finding not yet fixed.

---

## D70 — Sprint-status validation gate: 2 orphan story keys corrected

**Provenance:** Workflow gate run (`bmad-sprint-planning`), 2026-10-16 (~21:28–21:32). Owner **JL** (Architect-lead). Human-prompted.

**Trigger.** Running the `bmad-sprint-planning` validation gate against the freshly generated
`_bmad-output/implementation-artifacts/sprint-status.yaml` (source `planning/epics.md`, 4 epics /
16 stories).

**What the gate reported.** The checklist (`checklist.md`) **FAILED** the "no development_status items
that don't exist in epic files" check: a bidirectional set comparison flagged 2 orphan keys, both
caused by the prior generation trimming a trailing parenthetical from the story title:

- `1-3-entity-resolution-and-access-denial-diagnosis-end-to-end` (epic title carries
  `…(walking-skeleton happy path)`)
- `4-1-anti-fabrication-guardrail-and-content-data-hygiene` (epic title carries
  `…(Mandatory Edge Case)`)

All other checks passed (every epic/story/retrospective present, counts match, statuses legal, valid
YAML).

**Fix applied.** The `bmad-sprint-planning` skill normalized both keys to the strict kebab-case
derivation of the full epic titles:

- `1-3-entity-resolution-and-access-denial-diagnosis-end-to-end-walking-skeleton-happy-path`
- `4-1-anti-fabrication-guardrail-and-content-data-hygiene-mandatory-edge-case`

Statuses were preserved (`backlog`; no downgrade). Re-run of the gate: **6/6 checks PASSED** —
4 epics · 16 stories · 4 retrospectives · no orphans/missing items · all statuses legal.

**Artifact changed.** `_bmad-output/implementation-artifacts/sprint-status.yaml`.

**Duration.** ~4 minutes wall-clock (21:28 refresh → 21:32 gate pass).

**Note.** Only the canonical `planning/epics.md` was used; the superseded
`_bmad-output/planning-artifacts/epics.md` (3 epics / 23 stories) was deliberately excluded (see D69).

---

## D71 — Phase 3 test preparation (TEA): risk-based ATDD, red phase, CI gate

**Provenance:** **TL** (Test-lead) with Murat (test-architect persona) as AI assistant, 2026-10-16; reviewed by **JL** (Architect-lead, Reviewer role).

**Prompt (abridged).** "Turn the frozen contracts into a risk-based test design and a runnable
red baseline for Phase 4. Cover the mandatory edge case first. No production logic."

**Decision (adopted).**
- **Risk-first ordering.** The mandatory edge case (hallucination prevention, R-01) is graded **P0**
  and tested first; every P0 requirement (FR-03, FR-06, FR-09, FR-10, FR-13, FR-14, NFR-2, NFR-8)
  gets at least one red test → P0 traceability 8/8.
- **Red phase is the deliverable.** `test/atdd/module12_contracts.test.py` holds **123** contract
  tests that call the interface stub and fail only with `NotImplementedError` ("red for the right
  reason"), enforced mechanically by `test/ci/red_phase_check.py` (123/123).
- **Mandatory fixtures** live in `test/fixtures/` (fake clock, fleet seed, telemetry simulator, DB
  harness, explainability assert); no wall-clock, no `random`, no network.
- **Traceability gate.** No `AD-n` architectural driver may pass without a red test; this closed the
  FR-15/AD-11 content-hygiene gap (see R3).
- **CI quality gate** at `test/ci/quality-gate.yml` runs schema check + red-phase check + coverage
  so the red baseline cannot silently rot into a green (green = someone wrote logic, red = correct).

**Artifacts changed.** `test/test-design.md`, `test/atdd/*`, `test/fixtures/*`, `test/ci/*`,
`tests/*`, `pytest.ini`, `test/nfr-evidence.md`, `test/traceability-matrix.md`,
`test/test-review.md`.

---

## R1 (rejected AI proposal) — tautological ATDD tests

**Provenance:** **TL**. Prompt: "Generate ATDD tests for these contracts."

**AI proposal.** For the harder scenarios (concurrency race, idempotent re-confirm) emit tests that
re-assert the mock's own configured return value — e.g. `mock.execute.return_value = R;
assert service.execute(...) is R`, and a few `assert result is not None` bodies. This "passes"
trivially and inflates the test count.

**Human decision: REJECT.**

**Rationale.** A test that restates its own setup proves nothing; it cannot go red when the
behaviour is wrong, so it is worthless as a red baseline and corrupts the traceability evidence.

**Adopted text.** Replace with tests that assert an **observable effect**: exactly one executor call
on a lost race (`test_confirm_*_lost_race_*`), the same `proposal_id`/snapshot across an idempotent
re-confirm, and canonical-code equality on the wire — never the mock's return value (ADR: R2/R3 of
`test/test-review.md`).

---

## R2 (rejected AI proposal) — wall-clock and `random` in fixtures

**Provenance:** **TL**. Prompt: "Build the shared test fixtures."

**AI proposal.** Seed ids with `uuid4()` and capture timestamps with `datetime.now()` inside the
fixture helpers; use `time.time()` for snapshot ordering.

**Human decision: REJECT.**

**Rationale.** Nondeterministic fixtures make the red baseline flaky and make the clock-availability
class (NFR-7, `CLOCK_UNAVAILABLE`) untestable; `datetime.now()`/`random` are banned in the service
core by NFR (AD-14 clock is an outbound port).

**Adopted text.** `test/fixtures/fake_clock.py` (monotonic, settable `FakeClock`) and a seeded
`IdFactory`; the DB harness opens the real schema in a temp file. Deterministic across runs
(`test/fixtures/README.md`).

---

## R3 (rejected AI proposal) — treat FR-15 as covered by AD-7

**Provenance:** **JL**. Prompt: "Map every architectural driver to a test and list the gaps."

**AI proposal.** Mark `AD-11` (content data-hygiene) as "covered — see AD-7 explainability tests",
so no dedicated red test is written for FR-15; report the matrix as complete.

**Human decision: REJECT.**

**Rationale.** AD-7 tests citations/explanations; they do not exercise instruction-like payloads in
query text or retrieved records. Claiming coverage would be a false pass on a P1 safety control and
would leave `I16` unverified.

**Adopted text.** Keep the gap open, then close it with a dedicated injection corpus
(`test_injection_corpus_query_text_is_data_not_control`,
`test_injection_corpus_retrieved_content_is_data_not_control`) asserting behavioural parity with the
clean fixture plus zero destructive triggers; `AD-11` now traces `RED` and gap `G-1` is closed
(`test/traceability-matrix.md`).
