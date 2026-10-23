---
title: Module 12 — AI Operations Copilot — Test Design (risk register · level allocation · coverage thresholds · testability feedback)
status: draft
created: 2026-10-16
updated: 2026-10-16
altitude: feature
paradigm: risk-based test design over a contract-first hexagonal architecture
binds: [PRD FR-01..FR-16, NFR-1..NFR-11, S1..S4, EC, PT, ARCHITECTURE AD-1..AD-15, contracts.md §0–§6, OP-1..OP-15, D1..D68]
sources:
  - planning/prd.md
  - planning/ARCHITECTURE.md
  - planning/detailed-design/contracts.md
  - planning/detailed-design/ports-and-adapters.md
  - planning/detailed-design/schemas/phase-2.3-cross-check.md
  - planning/reviews/review-detailed-design.md
  - planning/reviews/review-arch-implementability.md
  - planning/reviews/review-arch-adversarial.md
  - planning/reviews/review-arch-edge-cases.md
  - docs/module_profile.md
---

# Test Design — Module 12: AI Operations Copilot

**Purpose.** Turn the frozen contract (`contracts.md`), the architecture invariants (`AD-1..AD-15`, `I1..I22`), and the Phase-2.3 cross-check into a test plan that a builder can execute: a scored risk register, an explicit allocation of behaviour to test level, hard coverage thresholds, and the testability gaps that must be closed in Phase 0.

**Scope note on "every module".** This repository specifies exactly one module — Module 12 (`docs/module_profile.md`, `prd.md` §0). Its mandated **Mandatory Edge Case is the hallucination-prevention guardrail** ("imaginary user / non-existent policy / event that never occurred" → `Entity Not Found in State`, `EC` in `prd.md` §15). That edge case is held at **P0** below (R-01) and the priority rule that forces it is stated in §1.3. If further modules are added to the repository, their Mandatory Edge Case risks enter at P0 by the same rule.

**Priority rule.** `score = probability × impact`; `P0 = 9`, `P1 = 6`, `P2 = 3–4`, `P3 = 1–2`. **Override:** a risk that is a module's mandated Edge Case is `P0` regardless of score.

---

## 1. Risk Register

Each risk names the single most load-bearing mitigation. `Mitigating contract/AD-n` cites the invariant that is *supposed* to prevent the risk — the test obligation is to make that invariant red if it is removed (see §3).

### 1.1 Register

| ID | Risk | Probability (1–3) | Impact (1–3) | Score | Priority | Mitigating contract / AD-n |
|---|---|---|---|---|---|---|
| **R-01** | **Hallucination: a fabricated entity, policy clause, or event is emitted instead of `Entity Not Found in State` / `Cannot confirm` (mandated Edge Case — `EC`).** | 3 | 3 | 9 | **P0** | FR-03/FR-06; AD-7 (exact, case-folded, no fuzzy); AD-2; `contracts.md` §1 `resolve_entities` L1–L2, Q4; §5 I4; D61 (`RawRef` escaping), D68 (ref cap) |
| **R-02** | Copilot-originated write to operational state (the copilot becomes a system of record / executes mutations). | 3 | 3 | 9 | **P0** | AD-1 (read-only ports); AD-13; `contracts.md` §1 `answer_query` L2, `propose_destructive_action` L2; §5 I1; NFR-8 |
| **R-03** | Dispatch before/without confirmation, or **double dispatch** (a confirmed proposal yielding two executor calls; a double-apply rendered as a second success). | 3 | 3 | 9 | **P0** | AD-3; AD-4 (ordered server-side state machine); AD-15 (frozen executor contract); `contracts.md` §1 `confirm_and_dispatch` L1–L2, P5/Q2; §5 I9, I10; D32, D47 |
| **R-05** | An uncited factual claim is rendered, or a citation whose source is absent from the `EvidenceSet` renders as evidence. | 3 | 3 | 9 | **P0** | AD-8 (structured claims + citation binding); AD-14 (citation identity & ordering); `contracts.md` §1 `answer_query` L1, §5 I3; OP-14 prose token-scan; FR-13 |
| **R-04** | Stale dry-run snapshot is dispatched: operational state changed between dry-run and confirm, or the selector is re-derived from query text. | 2 | 3 | 6 | P1 | AD-6 (re-execute the stored selector, compare on `(id, actionable status)`); `contracts.md` §1 `confirm_and_dispatch` P3/L3, `propose_destructive_action` L1; §5 I11; X-12 |
| **R-06** | Prompt injection: query text or retrieved content steers routing, tools, or the destructive path (control flow driven by data). | 2 | 3 | 6 | P1 | AD-11 (content is data, never control); `contracts.md` §1 `answer_query` L1; §5 I16; FR-15; OP-11 (policy text as data) |
| **R-07** | Non-determinism: evidence membership, `position` sequence, citation set, diagnosis class, or runbook steps vary across identical runs. | 2 | 3 | 6 | P1 | AD-2 (evidence-level determinism); AD-14; `contracts.md` §1 `assemble_evidence` L2 / `answer_query` L3; §5 I2, I5, I6, I7; R2 (clock/idgen ports); FR-14 |
| **R-08** | Unsafe dependency failure: fabrication or partial evidence emitted after an LLM/provider/clock/executor failure instead of the degraded response. | 2 | 3 | 6 | P1 | AD-12 (typed `ok|failure`, abort before prose); `contracts.md` §1 `assemble_evidence` Q-fail, `confirm_and_dispatch` L3; §5 I17; FR-16 |
| **R-09** | Invented runbook step, wrong-template match on a code the node does not report, or unvetted physical-intervention content rendered as sanctioned. | 2 | 3 | 6 | P1 | AD-9 (registered templates only, verbatim; provenance separate); `contracts.md` §1 `diagnose_node_triage` P2/L1, `lookup_runbook` L1–L2; §5 I8; D43, D44; FR-07/08 |
| **R-10** | Audit defect: a missing/duplicated row per tool call, tampering (update/delete), a secret in an entry, or unbounded log growth. | 2 | 3 | 6 | P1 | AD-10 (append-only, redaction at write, retention cap); `contracts.md` §2 `get_audit_page`; §5 I14, I15, I20; D42, D45, D50; NFR-11 |
| **R-11** | Gate-token replay/forgery: a stale, foreign, or replayed `gate_token` is accepted and confirms another proposal. | 2 | 3 | 6 | P1 | AD-15; AD-3; `contracts.md` §0.1 `GateToken`, §1 `confirm_and_dispatch` P2; D47; §5 I21 |
| **R-12** | Control-plane expansion: a mutating route outside `/api/v1/destructive/*` + `/executor/v1/*`, or a non-allowlisted `selector.method` persisted and re-executed at confirm. | 2 | 3 | 6 | P1 | AD-13; `contracts.md` §2 L1, §3 OP-5/OP-6; §5 I18, I22; D46, D55, E39 (selector allowlist) |
| **R-13** | Window/interval off-by-one: half-open `[start, end)` mishandled at a boundary, or a midnight-crossing window rendered with the wrong day/timezone. | 2 | 2 | 4 | P2 | AD-2; `contracts.md` §1 `diagnose_schedule_window` L1–L2, `diagnose_retrospective` L1; §3 OP-8/OP-9; §5 I6, I7; D38, D39 |
| **R-14** | Concurrency corruption: an in-flight turn races a session reset, or ≥5 sessions contend on the single SQLite writer and produce torn/inconsistent context. | 2 | 2 | 4 | P2 | NFR-6; AD-10 (single writer, WAL); `contracts.md` §1 concurrency clause, §2 `reset_session` Q2; D51 (idle TTL, reset ordering) |
| **R-15** | Latency breach: the single LLM prose call is on the user-perceived critical path and pushes p95 > 3 s / p99 > 8 s. | 2 | 2 | 4 | P2 | NFR-5; §1 `answer_query` latency budget; OP-14 (p95 ≤ 3000 ms); D56 (one consistent budget) |
| **R-16** | Routing defect: intent misclassification, or a compound query silently collapsing to a single answer. | 2 | 2 | 4 | P2 | FR-01; AD-11 (rule-based routing); `contracts.md` §0.4 `AnswerEnvelope`, §1 `answer_query` Q1; D37, D54 |

### 1.2 Mandatory Edge Case → P0 binding

| Module | Mandated Edge Case (`docs/module_profile.md`) | Risk | Priority | Contract that must be shown red-if-removed |
|---|---|---|---|---|
| Module 12 | Hallucination prevention: imaginary user / non-existent policy / event that never occurred | R-01 | **P0** | `resolve_entities` Q4 (`S_ENF` naming every unresolved ref) + `diagnose_retrospective` Q4 (`S_CNC` on zero events) + §5 I4 (`fabricated rate == 0`) |

### 1.3 Priority derivation

- `score = probability × impact`.
- `P0 = 9` (any 3×3). `P1 = 6`. `P2 = 3–4`. `P3 = 1–2`.
- **Override:** the module's Mandatory Edge Case is `P0` irrespective of score (R-01 is both 9 *and* the EC, so it is doubly pinned).
- P0 risks (R-01, R-02, R-03, R-05) are the **release blockers**: §3 requires 100% of their guarding contracts to have at least one red test.

---

## 2. Test Level Allocation

Four levels, matching the hexagonal rings (`ports-and-adapters.md` §1) so that a failure localizes to exactly one ring:

| Level | Target under test | Test doubles allowed | Failure meaning |
|---|---|---|---|
| **Unit — pure domain** | `service/core/` (intent, evidence, diagnose, runbooks, strings) and the pure steps of `propose_destructive_action` / `confirm_and_dispatch` | none (pure functions; provider *interface* fakes only at the seam) | a deterministic rule is wrong |
| **Contract / integration — adapter + DB** | `service/adapters/sim/`, `adapters/db/`, `adapters/llm/` behind their outbound ports (OP-1..OP-15) | real SQLite, real fixtures, fake clock/idgen/LLM/executor | an adapter or schema violates a port/DB contract |
| **API — HTTP** | `service/api/v1/`, `service/api/executor/` (driving adapters) | a wired test app over in-process adapters | the wire contract (status, body, error code, pagination) is wrong |
| **E2E — UI scenario** | the console SPA driving the full stack | full stack incl. simulated executor | a user journey or a UX/safety invariant breaks end-to-end |

### 2.1 Behaviour → level mapping

| Behaviour / contract | Level | Governing ref |
|---|---|---|
| Exact, case-folded entity resolution; no fuzzy; unresolved → `S_ENF` naming refs | **Unit** | AD-7; `resolve_entities` L1–L2; I4; D61, D68 |
| `EvidenceSet` uniqueness + monotonic `position` starting at 0 | **Unit** | AD-14; `assemble_evidence` L1; I2, I5; X-07 |
| Access-denial classes; multi-clause precedence `not-in-allowlist > quota > window` | **Unit** | AD-2; `diagnose_access_denial` Q1; E10 |
| Window calculator half-open `[start, end)`; `schedule_no_constraint`; `next_open_window == null` on no future window | **Unit** | D38, D39, D55; `diagnose_schedule_window` L1–L2; I6; E2, E3 |
| Retrospective event match half-open; multi-type precedence `event_denied > event_cancelled > event_cordoned`; zero events → `S_CNC` | **Unit** | D40, D25, E9; `diagnose_retrospective` Q1/Q4; I7 |
| Node-triage code match/mismatch; template verbatim; unsourced physical template → unavailability; unknown code → `S_RBX` | **Unit** | AD-9; D43, D44; I8; E46 |
| Destructive dry-run: selector build, `(action, entity_type)` compatibility, terminal items `actionable == false`, empty set disables confirm | **Unit** | AD-4, AD-6; D55; E11, E12 |
| Proposal state machine (`dry_run→confirmed→dispatched→executed/failed/superseded`), exactly-once per proposal, idempotent identical confirm, `CONFIRMATION_CONFLICT` on differing confirm | **Unit** | AD-3, AD-4; `confirm_and_dispatch` L1–L2, P1–P6; I9, I10, I13; D32, D47 |
| Re-validation compare on `(id, actionable status)`; delta → refuse with delta; provider-down → safe failure | **Unit** | AD-6; `confirm_and_dispatch` P3/L3; I11; X-12 |
| `applied_count != len(affected_items)` → `failed`/`partial`, never a larger-than-scope success | **Unit** | AD-15; `confirm_and_dispatch` Q2; E5 |
| Canonical strings byte-exact; `answer_chain` contiguous prefix; `Claim` non-empty + ≥1 citation | **Unit** | D57, D60; §0.4; I3 |
| Gate-token TTL/freshness and format | **Unit** | AD-3; D47; `confirm_and_dispatch` P2; E32 |
| Mock providers load fixtures; id uniqueness; case-fold browse; record field sets exact | **Contract** | OP-1..OP-12; `ports-and-adapters.md` R4; §0.3 |
| Clock adapter freeze/advance + `read_id` format | **Contract** | OP-10; DP-5; I19; R2 |
| Seeded idgen fixed sequence + counter persists across restart | **Contract** | OP-13 Q2; E43; X-09 |
| LLM prose token-scan: reject whole prose and retry once (never strip); timeout → `LLM_UNAVAILABLE` | **Contract** | OP-14; AD-8; D48; X-10 |
| Simulated executor: frozen `ExecutorRequest`, exactly-once, duplicate-apply surfaces failure, own clock read | **Contract** | AD-15; OP-15; E16, E35, E44; X-11 |
| SQLite schema: enums, `NOT NULL`/`CHECK`, `UNIQUE(answer_id,citation_id)`, audit append-only + rotation gate, state-machine trigger | **Contract** | I14, I20; D42, D66; X-01, X-07, X-17 |
| Route status mapping (200 canonical vs 400/403/404/409/410/502/503) and `ErrorBody` wire shape | **API** | §2 preamble; §4; D58; E8, E15 |
| Id-shape + body-schema validation before lookup; `SESSION_EXPIRED`/`SESSION_NOT_FOUND` | **API** | §2; D52, D64; E15, E48 |
| Browse/audit pagination caps; out-of-range page; `page_size ≤ 100`; retention cap depth | **API** | AD-13; I22; D46, D50, D64; E13, E14 |
| One audit row per tool call at the API boundary; audit read not audited | **API** | AD-10; I14; `get_audit_page` Q3 |
| Executor routes (`POST`/`GET /executor/v1/proposals`) conformance | **API** | AD-15; §2; X-11 |
| S1 access-denial journey (citation card click resolves) | **E2E** | UJ-1; FR-04/13 |
| S2 night-schedule journey (next open window rendered with date+timezone) | **E2E** | UJ-2; FR-05 |
| S3 node-triage journey (steps + safety warnings + provenance) | **E2E** | UJ-3; FR-07/08 |
| S4 safety journey (refusal → dry-run → confirm → delegation card; server-side state machine authority) | **E2E** | UJ-4; AD-4; FR-09/10 |
| EC journey (imaginary entity, then cold-start safe response) | **E2E** | `EC`; FR-03/6/16 |
| PT prototype surfaces (inspection viewer, audit log, session context) | **E2E** | `PT`; FR-02/11/12 |

### 2.2 Share (planned test-case inventory)

Pure domain logic carries the **highest share**. Counts are a representative budget for the first implementation cycle; percentages are the allocation the plan defends.

| Level | Planned cases | Share | Rationale |
|---|---:|---:|---|
| **Unit — pure domain** | 120 | **54.5%** | every `diagnose_*`, the resolver, the evidence assembler, the safety state machine, canonical strings, and window math are pure and cheap to exhaust; this is where the deterministic spine is proven |
| Contract / integration (adapter + DB) | 52 | 23.6% | ports, adapters, and DDL constraints; slow but must cover the invariant-bearing schema |
| API (HTTP) | 30 | 13.6% | wire contract, status/error mapping, pagination, audit boundary |
| E2E (UI scenario) | 18 | 8.2% | the six journeys (S1–S4, EC, PT) and their safety/rendering invariants |
| **Total** | **220** | 100% | unit share (54.5%) is the single largest and exceeds the sum of API + E2E |

**Hard rule:** no behaviour defined in `service/core/` may be tested *only* at API or E2E level. Every core contract appears at least once as a unit test.

---

## 3. Coverage Thresholds

### 3.1 Contract-level (gate)

| Threshold | Target | How measured |
|---|---|---|
| P0 contracts have ≥ 1 red test | **100%** of the guards for R-01/R-02/R-03/R-05 | each listed in §3.4; test fails against the unguarded build |
| Architecture invariants exercised | **22 / 22** (`I1..I22`) each with the "RED if removed" test named in `contracts.md` §5 | suite naming maps 1:1 to §5 |
| AD blocks covered | **15 / 15** (`AD-1..AD-15`) each with ≥ 1 test | trace table |
| FR covered | **16 / 16** (`FR-01..FR-16`) each mapped to ≥ 1 test | trace table |
| Error catalog exercised | **100%** of §4 codes, each observed at least once | `ErrorCode` enum swept by a meta-test |
| Canonical strings | **6 / 6** byte-exact golden tests (`S_ENF`, `S_CNC`, `S_PUA`, `S_ARF`, `S_RBX`, `S_CAP`) | golden fixtures vs `strings/canonical_strings.py` |
| Port signatures (R4/AD-15) | **15 / 15** `OP-1..OP-15` schema-conformance tests | port-schema contract test |
| Phase-2.3 cross-check rows | every `X-nn` with a "Phase 2.3 action" has its named test | `phase-2.3-cross-check.md` |

### 3.2 Line / branch coverage

| Area | Line coverage | Branch coverage | Notes |
|---|---:|---:|---|
| `service/core/` (domain — pure) | **≥ 90%** | ≥ 85% | the enforced floor; the target is 95%+ on `diagnose/`, `evidence/`, `strings/` |
| `service/application/` | ≥ 85% | ≥ 80% | orchestration incl. safety + dispatch + audit |
| `service/adapters/` | ≥ 80% | ≥ 75% | incl. SQLite triggers exercised via integration tests |
| `service/api/` | ≥ 80% | ≥ 70% | route + middleware |
| **Whole backend** | **≥ 85%** | ≥ 80% | aggregate gate |
| `console/` (SPA) | ≥ 70% | — | E2E covers the safety/rendering invariants regardless |

Coverage is a floor, not the objective: line coverage below the floor fails the build; the P0 red-test rule (§3.1) is a *mutation* requirement and is not satisfied by line coverage.

### 3.3 Scenario-suite targets (from PRD NFRs)

| Suite | Target | Ref |
|---|---|---|
| Determinism — 3× runs per fixture | 100% identity of evidence membership, position sequence, citation set, diagnosis class, runbook steps | FR-14 / NFR-4 |
| Anti-fabrication — ≥ 10 negatives | 100% `S_ENF`; fabricated rate `== 0` | FR-03 / NFR-2 |
| Citation coverage | 0 uncited claims; 100% of citations resolve | FR-13 / NFR-3 |
| Fault injection — every failure class | 100% explicit degradation, 0 fabricated detail, 0 hard crashes | FR-16 / NFR-7 |
| Injection corpus | 100% behavioural parity clean vs injected; 0 destructive triggers | FR-15 |
| Safety instrumentation | copilot-originated mutations `== 0`; exactly one dispatch + one applied mutation per confirmed proposal | FR-10 / NFR-8 |
| Retention | cap honored, oldest-first eviction, rotation logged | NFR-11 / D50 |

### 3.4 P0 red-test requirements (release blockers)

A "red test" is one written to **fail against the unguarded build** (guard removed / mutation applied), not merely to execute the happy path.

| P0 risk | Guard that must have a red test | Named test suite |
|---|---|---|
| R-01 (EC) | `resolve_entities` exact/case-fold; `S_ENF` on any unresolved ref; `S_CNC` on zero events; fabricated rate `== 0` | `tests/anti_fabrication`, `tests/determinism` |
| R-02 | Provider ports declare no mutating method; zero operational-state writes over the scenario suite | `tests/safety_instrumentation` (I1) |
| R-03 | dispatch only from `confirmed`; exactly one executor call per proposal; double-apply surfaces failure | `tests/safety_instrumentation`, `tests/executor_contract` (I9, I10, I21) |
| R-05 | every `Claim` cites ≥ 1 resolved `EvidenceSet` entry; prose token-scan rejects | `tests/citation_coverage` (I3) |

---

## 4. Testability Gaps → Phase 0 Feedback

These are places where the architecture/contract is correct by design but the **test harness cannot currently observe or control the behaviour**. Each row feeds back into the Phase 0 gap register (infrastructure and fixture decisions). "Cloaked by contract" means the contract already mandates the shape — Phase 0 only has to build the harness; "Open" means a decision is genuinely missing.

| Gap | Testability problem | Why it blocks a test | Contract status | Phase 0 feedback |
|---|---|---|---|---|
| **T-1 Injectable, freezable clock** | `service/core/` must not read wall time (`I19`, R1), and `ClockRead` must be reproducible | FR-14 determinism is vacuous unless the clock can be **frozen** and **advanced** (gate-token 15 min TTL, session 30 min idle, executor 5 s timeout) | Cloaked by contract (OP-10, DP-5, R2, I19) | Phase 0 must decide the fake-clock adapter API: `freeze(instant)`, `advance(delta)`, deterministic `read_id` sequence |
| **T-2 Hidden global state** | the SQLite DB is a single process-global writer; the Audit Writer is a process-global single writer; `m12.*` metrics have no sink | tests cannot run in parallel or in isolation; metrics assertions (`Q3`) are impossible | Partly open (metrics sink undefined) | Phase 0 must add: per-test DB factory/DI (never a module-level connection), an injectable metrics-recorder port, and a rule banning import-time singletons |
| **T-3 No seed fixtures / versioned snapshots** | `fixtures/` exists but values are deferred (PD-5, OQ-2: Night Policy hours, catalog-policy schema, `ERR_THERMAL_88` steps, error-code semantics); no snapshot version; seeded idgen sequence undefined | determinism, anti-fabrication, and window/runbook fixtures cannot be golden-tested without frozen, versioned seeds | Open (fixture-authoring time) | Phase 0 must produce: a versioned seed fixture set under `fixtures/`, a frozen snapshot per fixture, and a seeded `idgen_port` + clock sequence so 3× runs reproduce ids (X-09) |
| **T-4 LLM nondeterminism on the answer path** | `answer_query` calls `llm_prose_port`; Ollama is external and variable | tests must be hermetic and cannot depend on a local model | Cloaked by contract (OP-14) | Phase 0 must provide a **fake `llm_prose_port`** (deterministic prose, injectable rejection and timeout) used by unit/contract/API tests; the Ollama adapter is exercised only in a tagged, non-gating lane |
| **T-5 Time-based behaviour not controllable** | gate-token TTL, session idle expiry, executor timeout, LLM timeout, retention/rotation are all clock-driven | expiry/staleness/safe-failure tests cannot be written without clock advance + a controllable executor delay | Cloaked by contract (T-1 + OP-15) | Phase 0 must pair T-1 with a fake executor exposing `delay(ms)` and a `late_response` hook |
| **T-6 No metrics/telemetry test sink** | `answer_query` Q3 and safety Q3 require `m12.*` counters incremented once | counters cannot be asserted | Open | Phase 0 must define an injectable metrics sink/port asserted by tests |
| **T-7 Concurrency harness absent** | NFR-6 ≥ 5 sessions; single SQLite writer queues turns; reset-vs-in-flight ordering (D51) | race/ordering tests have no harness | Cloaked by contract (NFR-6, AD-10, D51) | Phase 0 must define a concurrency harness and a reset-vs-in-flight test fixture |
| **T-8 Environment pin not enforced** | AD-10 asserts `sqlite3.sqlite_version ≥ 3.35`; SQLite `GLOB` cannot express the normative regex (X-02, X-03) | append-only trigger and id-format behaviour vary by engine version | Cloaked by contract (AD-10) | Phase 0 must pin SQLite/Python (and Node/Vite for E2E) and fail the build on a version mismatch |
| **T-9 Query POST is intentionally non-idempotent** | no idempotency key on `POST /sessions/{sid}/queries` (implementability gap #3) | double-submit tests must pin *expected* duplicates (new `answer_id`, new turn, extra audit rows) rather than dedupe | Clarified by contract (§1 concurrency: not idempotent by design) | Phase 0 should record the "duplicate submit is expected, not a bug" convention in the test charter |
| **T-10 Unbounded Session/Answer growth** | retention applies to the audit log only; sessions/answers are uncapped in the prototype | long-run and fixture-reset tests lack a bounded reset story | Open (OQ-13 deferred) | Phase 0 must define the fixture-reset/teardown contract and a per-test DB snapshot |
| **T-11 Clock citation not addressable** | `clock#<read_id>` is citable (AD-14) but there is no `GET /api/v1/state/clock/{id}` route | the S2 E2E "citation click resolves" assertion cannot pass for the clock fact | Open (route absent in §2) | Phase 0/Phase 2.3 must either add the clock inspection route or mark the clock citation as non-clickable in UX; captured as a test dependency |
| **T-12 Frozen-schema drift** | R4/AD-15 require `ExecutorRequest` and every port signature to match §0 exactly | without a generated-schema comparison, drift is invisible | Cloaked by contract (R4, AD-15) | Phase 0 must add a port-schema contract test that diffs generated schemas against §0 field sets |

### 4.1 Proposed Phase 0 gap-register additions

The following entries are proposed for the Phase 0 gap register (append; do not overwrite). They are ordered by blocking severity for the test plan.

| New ID | Gap to close in Phase 0 | Blocks | Owner |
|---|---|---|---|
| **P0-G1** | Versioned seed fixtures + frozen snapshots + seeded clock/idgen sequences | T-3, R-01, R-07 | Fixtures / Test-lead |
| **P0-G2** | Test-double strategy: fake `llm_prose_port`, fake executor (with `delay`/`late_response`), fake clock, in-process adapters | T-1, T-4, T-5 | Test-lead |
| **P0-G3** | Isolation strategy: per-test DB factory / DI, no import-time singletons (Audit Writer, provider index) | T-2, T-7, T-10 | Application-lead |
| **P0-G4** | Environment pin: Python 3.11, `sqlite_version ≥ 3.35`, Node/Vite for E2E, CI version gate | T-8 | Build/CI |
| **P0-G5** | Injectable metrics-recorder port for `m12.*` assertions | T-6, R-15 | Application-lead |
| **P0-G6** | Concurrency + clock-advance test harness | T-5, T-7, R-14 | Test-lead |
| **P0-G7** | Golden fixtures for the 6 canonical strings and the full §4 error catalog | §3.1 | Test-lead |
| **P0-G8** | Red-test / mutation gate in CI for P0 guards | §3.4 | Build/CI |
| **P0-G9** | Clock-citation addressability decision (route or UX non-clickable) | T-11 | Architect / UX |
| **P0-G10** | Port-schema contract-test generator diffing generated schemas vs `contracts.md` §0 | T-12, R-11, R-12 | Test-lead |

---

## 5. Traceability Summary

| Required suite | FR / AD | Level | P0? |
|---|---|---|---|
| `tests/determinism` | FR-14 / AD-2, AD-14 | Unit + Contract | yes (R-07) |
| `tests/citation_coverage` | FR-13 / AD-8, AD-14 | Unit + Contract + E2E | yes (R-05) |
| `tests/fault_injection` | FR-16 / AD-12 | Contract + API | yes (R-08) |
| `tests/injection_corpus` | FR-15 / AD-11 | Unit + API + E2E | yes (R-06) |
| `tests/anti_fabrication` | FR-03 / AD-7 | Unit + E2E | **P0 (EC)** |
| `tests/safety_instrumentation` | FR-09/10 / AD-1, AD-3, AD-4 | Unit + Contract + E2E | yes (R-02, R-03) |
| `tests/dryrun_revalidation` | FR-09 / AD-6 | Unit | yes (R-04) |
| `tests/executor_contract` | FR-10 / AD-15 | Contract + API | yes (R-03, R-11) |
| `tests/confirmation_semantics` | FR-09 / AD-5 | Unit + API | yes (R-02) |
| `tests/re_dispatch` | FR-10 / AD-3 | Unit | no (P1) |
| `tests/audit` / `tests/audit_redaction` / `tests/retention` | FR-11 / AD-10 | Contract + API | no (P1) |
| `tests/runbook` | FR-07/08 / AD-9 | Unit + API + E2E | no (P1) |
| `tests/window_boundary` / `tests/event_window` | FR-05/06 / AD-2 | Unit | no (P2) |
| `tests/browse_cap` / `tests/route_audit` | FR-12 / AD-13 | API | no (P1, R-12) |

---

*Companion to `planning/detailed-design/contracts.md` and `planning/ARCHITECTURE.md`. Risk scoring, level allocation, coverage gates, and Phase 0 feedback authored 2026-10-16. The Phase 0 gap-register additions (§4.1) are proposed for append to the Phase 0 register once that register is materialized.*
