---
title: Module 12 — AI Operations Copilot — Epic Breakdown
status: draft
created: 2026-10-16
step: create-epics-and-stories
inputDocuments:
  - planning/prd.md
  - planning/ARCHITECTURE.md
  - planning/detailed-design/contracts.md
  - planning/detailed-design/ports-and-adapters.md
  - docs/module_profile.md
  - planning/ux/DESIGN.md
  - planning/ux/EXPERIENCE.md
---

# Module 12 — AI Operations Copilot: Epic Breakdown

## Overview

This document decomposes Module 12 into **4 epics / 16 stories**, each epic a vertical
slice that delivers user-visible value for a named protagonist. It is authored as a
**John (PM) + Amelia (Dev) implementability review**: every story is independently
completable in one dev session, depends only on earlier stories, and carries a
concrete Given/When/Then acceptance test drawn from the PRD (FR-01–FR-16, NFR-1–NFR-11)
and `planning/detailed-design/contracts.md`.

- **Stack:** Python 3.11 + FastAPI; React 19 + TypeScript + Vite; SQLite (WAL, append-only
  audit trigger); local Ollama (prose-only). One process, one SPA, standalone/offline.
- **Paradigm:** layered read-only intelligence layer over a deterministic evidence pipeline
  exposed as hexagonal ports/adapters. The Copilot **explains, diagnoses, retrieves and
  recommends** — it never enforces, schedules, or mutates.

## Named Protagonists

| Protagonist | Role | Drives |
|---|---|---|
| **Nadia** | AI Lab Operations Engineer (frontline helpdesk) — primary operator | Epics 1, 2, 4; all four UJ-1–UJ-4 through her console |
| **Dr. Aris Thorne** | NLP Professor (CS101) — secondary, reaches the Copilot through Nadia | Epic 3 (UJ-2 window for a held training job) |
| **Mateo** | Undergraduate student — secondary, subject of UJ-1 through Nadia | Epic 1 (UJ-1 access-denial reason) |
| **AI Ops Copilot Assistant** | The system protagonist: retrieves, explains, recommends; never a system of record, never an executor | All epics |

## Requirements Coverage Map

| FR | Epic · Story | | FR | Epic · Story |
|----|--------------|---|----|--------------|
| FR-01 Intent routing | 1.2 · 3.4 | | FR-09 Destructive refusal/dry-run/confirm | 2.1 · 2.2 · 2.3 |
| FR-02 Session context | 1.2 · 3.4 | | FR-10 Propose-only handoff | 2.4 |
| FR-03 Entity resolution | 1.3 · 4.1 | | FR-11 Tool-call audit | 1.5 |
| FR-04 Access-denial diagnosis | 1.3 | | FR-12 State inspection | 1.5 |
| FR-05 Schedule/window | 3.1 | | FR-13 Citation integrity | 1.4 |
| FR-06 Retrospective diagnosis | 3.2 · 4.1 | | FR-14 Determinism | 1.4 |
| FR-07 Node triage runbook | 3.3 | | FR-15 Content data-hygiene | 4.1 |
| FR-08 Runbook source rule | 3.3 | | FR-16 Safe failure | 2.4 · 4.2 · 4.3 |

**Mandatory scenarios:** S1 Access-Denial → Epic 1 · S2 Night Window → 3.1 · S3 Node Triage → 3.3
· S4 Safety Guardrail → Epic 2 · EC Hallucination → 4.1 · PT Prototype console → Epic 1.

### NFR Coverage Map

Every NFR resolves to at least one story; the story's `Requirements:` line and AC carry it.

| NFR | Theme | Epic · Story |
|-----|-------|--------------|
| NFR-1 Diagnosis accuracy | 100% on the four mandatory fixtures; ≥ 90% on the extension corpus (FR-04–06) | 1.3 · 3.1 · 3.3 |
| NFR-2 Anti-fabrication | 0 fabricated entities/policies/events; 100% Entity-Not-Found (FR-03, FR-06) | 1.3 · 3.2 · 4.1 |
| NFR-3 Citation integrity | 100% of factual claims cited; 100% of citations resolve (FR-13) | 1.4 |
| NFR-4 Determinism | 100% identity across 3 runs of each fixture (FR-14) | 1.4 |
| NFR-5 Latency | p95 ≤ 3 s submit→rendered answer / ≤ 5 s runbook; p99 ≤ 8 s (FR-01, FR-04–07) | 1.3 · 3.1 · 3.2 · 3.3 |
| NFR-6 Concurrency | ≥ 5 concurrent operator sessions; ≥ 50 queries/hour (all FRs) | 1.2 |
| NFR-7 Availability & robustness | ≥ 99% / 8 h; cold-start ≤ 60 s; 0 hard crashes (FR-01, FR-16) | 4.2 · 4.3 |
| NFR-8 Safety | 0 copilot-originated mutations; 100% refusal+dry-run+confirm; 100% audited (FR-09–11) | 2.1 · 2.2 · 2.3 · 2.4 |
| NFR-9 Usability | ≥ 90% of Nadia-class operators complete a diagnosis < 5 min (FR-01) | 1.3 |
| NFR-10 Extensibility | new entity type ≤ 1 dev-day, no console change; runbook template config-only (FR-08) | 1.1 · 3.3 |
| NFR-11 Security / privacy | audit fields, 0 secrets, retention cap, no state-mutating control (FR-09–13, FR-15) | 1.5 |

## Structure-Rule Compliance

| Rule | How it is met |
|---|---|
| 3–4 epics, vertical slices, named protagonist | 4 epics; each names its protagonist and states user-visible value in the goal |
| 3–5 stories per epic, 9–16 total | 5 · 4 · 4 · 3 = **16** stories |
| No forward dependencies | Every story lists `Depends on` referencing only earlier stories (see dependency table) |
| Epic 1 = walking skeleton | Epic 1 seeds fixtures (1.1), wires the simulated adapters (1.1), and runs one end-to-end happy path through all layers (1.3) |
| Mandatory Edge Case has a dedicated story | **4.1** (imaginary user / non-existent policy / event that never occurred) |
| ≥ 2 failure states have dedicated stories | **4.2** retrieval-dependency failure · **4.3** prose-runtime + malformed-input failure (executor failure additionally covered in **2.4**) |

## Epic List

1. **Epic 1 — Walking Skeleton: the first cited access-denial answer** (Nadia → Mateo)
2. **Epic 2 — Safety & Delegation: Nadia can never trigger a mutation by accident** (Nadia)
3. **Epic 3 — The Rest of the Operational Questions: window, history & runbooks** (Dr. Aris Thorne, via Nadia)
4. **Epic 4 — Trust & Safe Failure: Nadia is never misled** (Nadia / AI Ops Copilot)

---

## Epic 1 — Walking Skeleton: the first cited access-denial answer

**Protagonist:** Nadia, mid-shift, on behalf of Mateo (student denied `deepseek-coder`).
**Goal:** Nadia opens the Operations Console, asks "Why was Alex denied deepseek-coder?",
and receives a cited, evidence-level deterministic answer — proven end-to-end through every
layer (console → REST → orchestration → deterministic core → read-only simulated adapters →
simulated LLM prose) on seeded fixtures. This epic is the **walking skeleton**: seed fixtures
+ one happy path through all layers + the simulated adapters.

**FRs:** FR-01, FR-02, FR-03 (happy path), FR-04, FR-11, FR-12, FR-13, FR-14.
**Implementability notes (Amelia):** The only story carrying greenfield risk is 1.2 (scaffold + console
shell). 1.3 is deliberately the thinnest vertical slice: one intent, one fixture, real layers.
No story here introduces a port that later stories must change — later epics extend the taxonomy
and add diagnosers behind the same ports.

### Story 1.1: Seed the fixture estate and stand up the read-only adapter ring

**Depends on:** none.
**Requirements:** FR-03 (data), AD-1, AD-13, AD-12, NFR-10, C-5.
**Binding invariants:** AD-1 (read-only state boundary) → contracts §5 I18; AD-13 (no control-plane expansion) → contracts §5 I22; AD-12 (safe failure) → contracts §5 I17; every port method query-only (contracts §3 OP-1..OP-12).
**Files:** `fixtures/estate/*.json` (seed), `service/ports/out/*.py` (query-only interfaces), `service/adapters/sim/fixtures_adapter.py`, `service/adapters/sim/clock_adapter.py`.
**Schema/DTO:** entity DTOs (`UserDTO`, `JobDTO`, `NodeDTO`, `PolicyClauseDTO`, `EventDTO`); SQL seed tables `users/catalog/policy/groups/jobs/nodes/reservations/windows/events`.
**ATDD path:** `test/atdd/module12_contracts.test.py::test_browse_state_*`, `::test_get_state_record_*` (state-read surface).
**DoD:** nine stores load offline with a freezable clock; every port declares only query methods; each read returns typed `ok | failure`; no write path exists; adding a new entity type needs no console/port/pipeline change.

As Nadia (Frontline Lab Helpdesk Specialist),
I want the Copilot's simulated estate seeded with realistic users, catalog, nodes, jobs, groups, windows, policy and runbook content,
So that every later answer is grounded in real, inspectable records rather than invented data.

**Acceptance Criteria:**

**Given** the greenfield `module12/` workspace
**When** the fixture estate is authored and the simulated adapters are wired behind read-only ports
**Then** `fixtures/` seeds the nine stores `{users, catalog, policy, groups, jobs, nodes, reservations, windows, events}` plus policy content and runbook templates, including S1 (`user#alex` student, model `deepseek-coder`, clause `policy#catalog.4.2` reason_class `not-in-allowlist`, event `event#evt-4711`), S2 (`group-4` + Night Policy window `night`), S3 (`node#ws-gpu-11` cordoned `error_code ERR_THERMAL_88` + template), S4 (CS201 pending jobs incl. `job#job-8823`)
**And** each port (`users_port`, `catalog_port`, `policy_port`, `groups_port`, `jobs_port`, `nodes_port`, `reservations_port`, `windows_port`, `event_store_port`, `clock_port`, `policy_content_port`, `runbook_registry_port`) declares **query-only** methods; the mock adapter reads fixtures and holds no write path (AD-1, AD-13)
**And** the estate loads offline with a freezable clock and every read returns a typed `ok | failure` result (C-5, AD-12)
**And** adding a new entity type (a fixture set + one query-only port) requires no change to the console, the other ports, or the answer pipeline (NFR-10)

### Story 1.2: Console shell, session store and conversational intake

**Depends on:** 1.1.
**Requirements:** FR-01, FR-02, AD-5, NFR-6, UX-DR2, UX-DR4.
**Binding invariants:** AD-5 (confirmation is procedural; context never authorizes) → contracts §5 I13; NFR-6 concurrency → contracts §2 session-store clause; intent routing exact (FR-01).
**Files:** `service/app/session_registry.py`, `api/routes/sessions.py`, `console/src/App.tsx`, `console/src/AnswerChain.tsx`.
**Schema/DTO:** `SessionDTO`, `TurnDTO`, `SubmitQueryRequest`, `SessionWithTurns`; SQL `sessions`, `turns`.
**ATDD path:** `test/atdd/module12_contracts.test.py::test_create_session_*`, `::test_submit_query_*`, `::test_get_session_*`, `::test_reset_session_*`.
**DoD:** session lifecycle + reset; 100% routing of the S1 query, 100% clarification for out-of-domain and compound-destructive; composer capped at 1,000 chars; ≥ 5 concurrent sessions at ≥ 50 q/h with no cross-session leakage.

As Nadia,
I want to open the Operations Console, start a session, and ask a question that is routed to one registered intent,
So that my complaint becomes a tracked conversational turn instead of a dead-end text box.

**Acceptance Criteria:**

**Given** the FastAPI service and the React console run from the structural seed
**When** I `POST /api/v1/sessions`, submit a query to `POST /api/v1/sessions/{sid}/queries`, and see the turn render in the console
**Then** a session is created on first query; resolved entities, prior intents and active answer ids are retained server-side; `DELETE /api/v1/sessions/{sid}` clears context; a follow-up reference resolves from prior-turn context (FR-02)
**And** 100% of the S1 query `why was alex denied deepseek-coder` routes to the access-denial intent; 100% of out-of-domain queries (`what's the weather?`) return the clarification/not-supported response and are never force-routed; a compound query containing a destructive verb routes to clarification (FR-01)
**And** the turn renders through the fixed answer-chain envelope (6 stages, `Observation` first) with a loading skeleton and a composer capped at 1,000 chars (over-length blocked); the diagnosis content is a placeholder until 1.3 (UX-DR4)
**And** the session store serves ≥ 5 concurrent operator sessions at ≥ 50 queries/hour with no cross-session context leakage or degradation (NFR-6)

### Story 1.3: Entity resolution and access-denial diagnosis end-to-end (walking-skeleton happy path)

**Depends on:** 1.1, 1.2.
**Requirements:** FR-03, FR-04, FR-13 (citing), AD-2, AD-7, NFR-1, NFR-5, NFR-9.
**Binding invariants:** AD-7 (exact-match resolution) → contracts §5 I4; AD-2 (deterministic evidence; LLM contributes no facts) → contracts §5 I2, I5.
**Files:** `service/core/resolve.py`, `service/core/diagnose_access_denial.py`, `service/app/answer_query.py`, `service/ports/in/answer_query.py`.
**Schema/DTO:** `ResolvedEntity`, `Diagnosis`, `AnswerEnvelopeDTO`, `AnswerDTO`.
**ATDD path:** `test/atdd/module12_contracts.test.py::test_resolve_entities_*`, `::test_diagnose_access_denial_*`, `::test_answer_query_happy_*`.
**DoD:** S1 fixture resolved 100% correct; clause + reason class cited from evidence; LLM called exactly once as prose and contributes no facts; p95 ≤ 3 s / p99 ≤ 8 s; diagnosis < 5 min for a Nadia-class operator.

As Nadia,
I want the Copilot to resolve Alex and deepseek-coder against state and explain the exact policy reason, with citations,
So that I can point to the clause when I answer Mateo at the counter.

**Acceptance Criteria:**

**Given** the S1 fixture and the read-only provider ports from 1.1
**When** I ask `why was alex denied deepseek-coder`
**Then** the resolver canonicalizes each reference to `{type}#{id}` and matches exactly (case-folded, no fuzzy); every required reference resolves to exactly one record before diagnosis proceeds (FR-03, AD-7)
**And** the answer states Alex's role (`student`), the applicable clause `policy#catalog.4.2` with its text, and reason class `not-in-allowlist`, each grounded in retrieved evidence and the denial event `event#evt-4711` (FR-04)
**And** the deterministic core computes the diagnosis and claims; the local LLM is invoked exactly once as connective prose over the fixed evidence payload and contributes **no** facts (AD-2); 100% fixture accuracy on S1 (NFR-1)
**And** the submit→rendered cited answer path meets p95 ≤ 3 s / p99 ≤ 8 s on reference fixtures (NFR-5), and a Nadia-class operator completes the S1 diagnosis end-to-end in < 5 min after a 10-min walkthrough with no infrastructure expertise (NFR-9)

### Story 1.4: Structured claims, citation cards and evidence-level determinism

**Depends on:** 1.3.
**Requirements:** FR-13, FR-14, AD-8, AD-14, NFR-3, NFR-4.
**Binding invariants:** AD-8 (structured claims + citation binding) → contracts §5 I3; AD-14 (citation identity & ordering) → contracts §5 I5; determinism I2, I19.
**Files:** `service/core/assemble_evidence.py`, `service/core/claims.py`, `service/core/citations.py`.
**Schema/DTO:** `EvidenceSet`, `Claim`, `Citation`, `ExplanationDTO`; SQL `evidence`, `claims`, `claim_citations`.
**ATDD path:** `test/atdd/module12_contracts.test.py::test_assemble_evidence_*`, `::test_get_answer_evidence_*`, `::test_get_citation_*`, `::test_explainability_*`.
**DoD:** 100% of factual claims carry ≥ 1 resolvable citation, 0 uncited; unresolved citation downgrades to `S_CNC`; evidence positions contiguous; S1 × 3 runs identical (membership, positions, citations, class).

As Nadia,
I want every factual assertion backed by a resolvable citation and the same question to always give the same evidence,
So that I can trust and reproduce what I relay.

**Acceptance Criteria:**

**Given** the evidence pipeline emits a fixed, ordered `EvidenceSet` with a monotonic `position` and structured `Claim`s bound through a `claim_citations` join
**When** the answer is composed and rendered
**Then** 100% of factual claims carry ≥ 1 citation that resolves programmatically to a retrieved state record, policy clause, event or clock read; 0 uncited factual claims (FR-13, NFR-3, AD-8, AD-14)
**And** a citation whose source is not in the `EvidenceSet` never renders; the answer downgrades to `Cannot confirm (insufficient evidence): checked {checked_list}.` (FR-13, S-3)
**And** running S1 3× with a frozen clock yields 100% identity of evidence membership, `position` sequence, citation set and diagnosis class (prose may vary) (FR-14, NFR-4)

### Story 1.5: Tool-call audit log and state inspection viewer

**Depends on:** 1.3.
**Requirements:** FR-11, FR-12, AD-10, NFR-11.
**Binding invariants:** AD-10 (append-only audit + redaction/retention) → contracts §5 I14, I15, I20; AD-1 read-only inspection → I18.
**Files:** `service/app/audit_writer.py`, `service/adapters/db/audit_store.py`, `api/routes/audit.py`, `api/routes/state.py`.
**Schema/DTO:** `AuditRecordDTO`, `GetAuditPageResponse`, `StateRecordDTO`; SQL `audit_events` (append-only trigger), retention cap.
**ATDD path:** `test/atdd/module12_contracts.test.py::test_get_audit_page_*`, `::test_get_state_record_*`, `::test_browse_state_*`.
**DoD:** every tool call appears exactly once, chronological; 0 credentials/tokens/secrets; no edit/delete path; retention cap rotates oldest first; inspector renders field-for-field with a read-only marker; absent entity → `S_ENF`.

As Nadia,
I want an append-only record of every Copilot tool call and the ability to inspect raw state myself,
So that the answer is auditable and I can verify the evidence without trusting the prose.

**Acceptance Criteria:**

**Given** the Audit Writer + Audit Store (SQLite, append-only trigger denying update/delete, single writer, write-time secret redaction) and `GET /api/v1/state/{entity_type}/{id}` + browse
**When** I perform the S1 investigation and open the Audit and Inspector surfaces
**Then** 100% of tool calls appear exactly once in chronological order; entries carry operator id, session id and tool metadata with 0 credentials/tokens/secrets; no edit/delete path exists; the log honors the configured retention cap rotating oldest first (FR-11, NFR-11, AD-10)
**And** the Inspector renders the underlying record field-for-field (100% match on sampled records) in mono with a `read-only` marker; a non-existent entity renders `Entity Not Found in State` (FR-12)

---

## Epic 2 — Safety & Delegation: Nadia can never trigger a mutation by accident

**Protagonist:** Nadia, testing the console mid-hurry (UJ-4).
**Goal:** Nadia types "Delete all pending jobs for CS201" and the Copilot refuses direct
execution, shows a dry-run of every affected job, requires an explicit **procedural**
confirmation, and only then emits a propose-only handoff to the (simulated) executor — fully
audited, with the Copilot's proposal and the executor-applied mutation kept distinct.

**FRs:** FR-09, FR-10 (+ FR-16 executor failure).
**Implementability notes (Amelia):** Delivered risk-first, before Epic 3. The server-side state
machine (`refused → dry_run → confirmed → dispatched → executed/failed/superseded`) is the whole
point, so 2.1–2.3 build it one stage at a time and 2.4 freezes the executor contract (AD-15).
The gate token is generated in 2.2 and consumed in 2.3/2.4 — never earlier.

### Story 2.1: Destructive-intent classification and refusal

**Depends on:** Epic 1 (1.3).
**Requirements:** FR-09, NFR-8, AD-4.
**Binding invariants:** AD-4 (server-side safety state machine) → contracts §5 I9, I12; NFR-8 zero mutations.
**Files:** `service/core/safety.py` (destructive classifier), `api/routes/destructive.py`.
**Schema/DTO:** `ProposalDTO` (`state=refused`); SQL `proposals`.
**ATDD path:** `test/atdd/module12_contracts.test.py::test_propose_destructive_action_*`, `::test_explainability_destructive_refusal_cites_rule_and_scope`.
**DoD:** destructive intents refused with literal `Action refused.` (`ACTION_REFUSED`); 0 copilot-originated writes; compound-destructive → clarification; refusal turn recorded in session context.

As Nadia,
I want the Copilot to refuse any destructive request on the spot,
So that a slip of the keyboard can never mutate the estate.

**Acceptance Criteria:**

**Given** the safety guardrail classifies destructive/mutating intents (`delete`, `cancel`, `drain`, `cordon`) from the registered taxonomy
**When** I submit `delete all pending jobs for cs201`
**Then** the Copilot classifies the intent as destructive, refuses direct execution with the literal `Action refused.` (`ACTION_REFUSED`), and copilot-originated writes to simulated state = 0 (FR-09, NFR-8)
**And** a compound query containing any destructive verb routes to clarification, never decomposition; the refusal turn is recorded in session context like any other turn (FR-01, AD-4)
**And** the target resolves via `resolve_entities` before the refusal completes; an unresolved target returns `Entity Not Found in State` (AD-4)

### Story 2.2: Dry-run snapshot with selector predicate and affected items

**Depends on:** 2.1.
**Requirements:** FR-09, AD-4, AD-6.
**Binding invariants:** AD-4 (safety state machine) → contracts §5 I9; AD-6 (snapshot re-validation) → contracts §5 I12.
**Files:** `service/core/dry_run.py`, `api/routes/destructive.py`.
**Schema/DTO:** `DryRunSnapshotDTO`, `ProposalDTO`; SQL `proposals.selector`, `affected_items`.
**ATDD path:** `test/atdd/module12_contracts.test.py::test_post_dry_run_*`, `::test_propose_destructive_action_qfail_empty_affected_set_disables_confirm`.
**DoD:** 100% of pending CS201 jobs enumerated with per-item actionable status; selector + snapshot timestamp persisted and re-executable; empty set renders `0 affected items` with confirmation disabled (`DRY_RUN_EMPTY_SET`); unresolved target → `S_ENF` before dry-run.

As Nadia,
I want to see every item the action would touch before anything is proposed,
So that the full scope is visible before I decide.

**Acceptance Criteria:**

**Given** the Dry-Run Builder persists both the affected-item set (per item: id + actionable status) and the selector predicate (exact provider method + parameters) plus a snapshot timestamp, and issues a per-proposal opaque gate token
**When** a destructive intent is refused and I request the dry-run via `POST /api/v1/destructive/dry-runs`
**Then** the dry-run enumerates every pending CS201 job (100%) with per-item status, and the snapshot retains the selector so it can be re-executed at confirmation time — never re-derived from query text (FR-09, AD-6)
**And** an empty affected set renders `0 affected items` with confirmation disabled (`DRY_RUN_EMPTY_SET`); an unresolved target renders `Entity Not Found in State` before any dry-run (AD-4)

### Story 2.3: Procedural confirmation gate and snapshot re-validation

**Depends on:** 2.2.
**Requirements:** FR-09, AD-4, AD-5, AD-6, D9, C-8.
**Binding invariants:** AD-4 (safety state machine) → contracts §5 I9; AD-5 (confirmation is procedural) → I13; AD-6 (snapshot re-validation) → I12.
**Files:** `service/core/confirmation.py`, `api/routes/destructive.py`.
**Schema/DTO:** `ConfirmationDTO`, `ProposalDTO`; SQL `proposals.gate_token` (UNIQUE).
**ATDD path:** `test/atdd/module12_contracts.test.py::test_post_confirm_*`, `::test_confirm_and_dispatch_precondition_stale_token_is_409`, `::test_confirm_and_dispatch_precondition_empty_affected_set_is_409`.
**DoD:** confirmation is a distinct request carrying only `{proposal_id, gate_token}`; no identity/role claim; caption literal `S_CAP`; changed scope → `CONFIRMATION_STALE` + delta; provider failure → safe failure, no dispatch.

As Nadia,
I want an explicit, distinct confirmation that re-checks the state before anything leaves the Copilot,
So that the safety boundary is honest and stale scope can't slip through.

**Acceptance Criteria:**

**Given** the Confirmation Gate requires a distinct request (`POST /api/v1/destructive/proposals`) carrying only `{proposal_id, gate_token}` and re-executes the stored selector
**When** I confirm a proposal
**Then** confirmation is a distinct HTTP request from the original query; the server records no identity/role claim; session context is never consulted; and the caption reads `This confirms a proposal for delegation. It does not grant or assert authorization.` (FR-09, AD-5, D9, C-8)
**And** any change in the re-queried `(id, actionable status)` set returns `CONFIRMATION_STALE` and re-renders the dry-run with the delta surfaced and confirmation disabled (AD-6)
**And** if the provider is unavailable during re-validation, the safe-failure response returns and no dispatch occurs (AD-6, FR-16)

### Story 2.4: Propose-only handoff, simulated executor and executor-failure safety

**Depends on:** 2.2, 2.3.
**Requirements:** FR-10, FR-16 (executor failure), AD-1, AD-3, AD-15, PD-6.
**Binding invariants:** AD-1 (read-only boundary) → contracts §5 I18; AD-3 (propose-only / no execution path) → I10; AD-15 (frozen executor contract) → I21.
**Files:** `service/app/proposal_dispatcher.py`, `service/ports/out/executor_port.py` (OP-15), `service/adapters/sim/executor.py`.
**Schema/DTO:** `ExecutorRequest`, `ExecutorResultDTO`, `ProposalDTO`; SQL `proposals.executor_result`.
**ATDD path:** `test/atdd/module12_contracts.test.py::test_confirm_and_dispatch_*`, `::test_executor_post_proposal_*`, `::test_executor_get_proposal_*`, `::test_post_re_dispatch_*`.
**DoD:** exactly one executor call per confirmed proposal; copilot performs 0 writes; audit records `actor = executor` distinct from the proposal; duplicate dispatch → `EXECUTOR_DUPLICATE_APPLY`; unavailable executor → `EXECUTOR_UNAVAILABLE` + `state = failed`, no auto-retry; re-dispatch is a new proposal with `supersedes_proposal_id`.

As Nadia,
I want a confirmed proposal handed to the executor under a frozen contract while the Copilot stays mutation-free,
So that the Copilot never executes — and the difference is visible in the console.

**Acceptance Criteria:**

**Given** the frozen executor contract (`POST /executor/v1/proposals`: `proposal_id`, closed-verb `action`, persisted `selector`, `gate_token` forwarded verbatim, `dry_run_ref`) and the simulated executor as reference adapter
**When** a confirmed proposal is dispatched
**Then** exactly one executor call per confirmed proposal; the Copilot performs zero direct writes; the executor applies exactly the referenced snapshot's items once, post-confirmation, validating the gate token; the proposal advances `refused → dry_run → confirmed → dispatched → executed` (FR-10, AD-1, AD-3, AD-15)
**And** the audit log records the executor-applied mutation with `actor = executor` and null `tool_call_id`, distinct from the Copilot's proposal; the delegation card renders `Copilot proposal` and `Executor-applied mutation` as separate labeled lines (FR-10, UX-DR8)
**And** a second dispatch for the same proposal id is rejected (`EXECUTOR_DUPLICATE_APPLY`); an unavailable executor returns `EXECUTOR_UNAVAILABLE`, sets `state = failed`, preserves the proposal line and performs no auto-retry (FR-16); a re-dispatch is a **new** proposal with fresh dry-run + confirmation and `supersedes_proposal_id` (PD-6)
**And** an open confirmation dialog is `role="alertdialog"`, blocks session navigation, and `Esc` returns to the dry-run and never confirms (UX-DR8)

---

## Epic 3 — The Rest of the Operational Questions: window, history and runbooks

**Protagonist:** Dr. Aris Thorne (CS101), whose training job is held, reached through Nadia.
**Goal:** Nadia answers "Why can't Group 4 run their fine-tuning job right now?" with the exact
next open window; "Why was this job cancelled/denied/cordoned?" from the event log; and produces
a sanctioned, template-backed node-triage runbook for `ws-gpu-11` — building only on Epic 1's
pipeline.

**FRs:** FR-01, FR-02 (extension), FR-05, FR-06, FR-07, FR-08.
**Implementability notes (Amelia):** Independent of Epic 2 — no cross-dependency. Each diagnoser is a
pure function over the same `EvidenceSet` contract established in 1.4; the window calculator and
event window are the only new time-rule components and both take the Clock port (R2). 3.4 is the
taxonomy-extension + session-context story and depends only on 3.1–3.3.

### Story 3.1: Schedule and window diagnosis

**Depends on:** Epic 1 (1.3).
**Requirements:** FR-05, AD-14, NFR-1, NFR-5.
**Binding invariants:** AD-14 (citation identity & ordering) → contracts §5 I6; window boundary half-open `[start, end)`; Clock port read (no wall clock).
**Files:** `service/core/diagnose_window.py`, `service/ports/out/windows_port.py` + `clock_port.py`.
**Schema/DTO:** `Diagnosis`, `WindowDTO`; SQL `windows` (`CHECK start < end`).
**ATDD path:** `test/atdd/module12_contracts.test.py::test_diagnose_schedule_window_*`.
**DoD:** S2 fixture 100%, ≥ 95% over 10 variants; exact next open window with date + timezone, cited; half-open boundary asserted; no-constraint → explicit no-window; failed clock read → `CLOCK_UNAVAILABLE`, never a fabricated window.

As Dr. Aris Thorne (NLP Professor, CS101) — through Nadia,
I want to know why my group's fine-tuning job can't run now and when it next can,
So that I can plan the launch instead of retrying blindly.

**Acceptance Criteria:**

**Given** the S2 fixture (`group-4`, clock `15:00`, Night Policy window `night` `22:00–06:00` UTC as in Annex 12.2 and `fixtures/estate/windows.json` — hours are fixture content, A-10 — half-open interval)
**When** Nadia asks `why can't group 4 run their fine-tuning job right now`
**Then** the diagnosis states the governing policy restriction and renders the exact next open window with explicit date + timezone, each fact cited (FR-05, AD-14)
**And** 100% fixture match on S2 and ≥ 95% across 10 window variants (NFR-1); the window diagnosis renders within the p95 ≤ 3 s answer budget (NFR-5)
**And** a job with no scheduling constraint explicitly states no restriction applies and renders **no** window; a missing group/job returns `Entity Not Found in State`; a failed clock read returns `CLOCK_UNAVAILABLE` and never fabricates a window (FR-05, FR-16)

### Story 3.2: Retrospective event-log diagnosis

**Depends on:** Epic 1 (1.3).
**Requirements:** FR-06, NFR-2, NFR-5.
**Binding invariants:** AD-2 (deterministic evidence) → contracts §5 I7; NFR-2 anti-fabrication; half-open event window `[start, end)`.
**Files:** `service/core/diagnose_retrospective.py`, `service/ports/out/event_store_port.py`.
**Schema/DTO:** `EventQuery`, `Claim`, `Diagnosis`; SQL `events`.
**ATDD path:** `test/atdd/module12_contracts.test.py::test_diagnose_retrospective_*`, `::test_edge_ec_retrospective_zero_events_is_cannot_confirm`.
**DoD:** one claim per matched event, each cited; zero matches → `Cannot confirm (insufficient evidence): checked {checked_list}.` with 0 invented details; inverted window rejected; renders within p95 ≤ 3 s.

As Nadia,
I want to explain why something was cancelled, denied or cordoned in the past,
So that I can answer "why was my job cancelled?" from the record, not from a guess.

**Acceptance Criteria:**

**Given** the minimal event log (`access_denied`, `job_cancelled`, `node_cordoned` with timestamp, outcome, `recorded_reason`) queried through `event_store_port` on a half-open `[start, end)` window
**When** I ask a retrospective question referencing a past event
**Then** the diagnosis retrieves the matching event record(s) with timestamp, outcome and recorded reason, each cited (FR-06)
**And** for an event that never occurred the Copilot returns `Cannot confirm (insufficient evidence): checked {checked_list}.` with 0 invented details (FR-06, NFR-2)
**And** the retrospective diagnosis renders within the p95 ≤ 3 s answer budget (NFR-5)

### Story 3.3: Runbook registry and node-triage runbook

**Depends on:** Epic 1 (1.3).
**Requirements:** FR-07, FR-08, AD-9, NFR-1, NFR-5, NFR-10.
**Binding invariants:** AD-9 (runbook source rule) → contracts §5 I8; NFR-10 extensibility (config-only template add).
**Files:** `service/core/runbook.py`, `service/core/diagnose_node_triage.py`, `service/adapters/sim/runbook_registry.py`, `service/ports/out/runbook_registry_port.py`.
**Schema/DTO:** `RunbookDTO`, `Diagnosis`; runbook templates keyed by error code with provenance/version.
**ATDD path:** `test/atdd/module12_contracts.test.py::test_diagnose_node_triage_*`, `::test_lookup_runbook_*`, `::test_get_runbook_*`.
**DoD:** registered template rendered verbatim (100% step-match) with tools, safety warning and provenance; unknown/mismatched code → `no runbook available for code {code}.` (`RUNBOOK_NOT_FOUND`); unsourced-physical template → unavailability; empty-step template rejected at registration; p95 ≤ 5 s.

As Nadia,
I want a sanctioned, ordered remediation runbook for cordoned node ws-gpu-11,
So that I follow approved steps with safety warnings instead of inventing guidance.

**Acceptance Criteria:**

**Given** the runbook registry keyed by exact error code with provenance + version metadata, and the node-triage diagnoser confirming cordon status and recorded error code before lookup
**When** I ask about `node#ws-gpu-11` with `ERR_THERMAL_88` (S3)
**Then** the runbook renders the registered template's ordered fan/airflow inspection steps verbatim (100% step-match), with required tools, a safety warning, and the approved-source provenance/version line (FR-07, FR-08, AD-9)
**And** an unknown code returns the literal `no runbook available for code {code}.` (`RUNBOOK_NOT_FOUND`) with 0 fabricated steps; a code that does not match the node's recorded code routes to unavailability; a physical-intervention template lacking approved-source metadata renders unavailability, not the steps; an empty-step template is rejected at registration (FR-08, S-4)
**And** runbook generation meets p95 ≤ 5 s (NFR-5); adding a runbook template is a registry-config change with no code or console change (NFR-10)

### Story 3.4: Intent-taxonomy extension and session follow-up references

**Depends on:** 3.1, 3.2, 3.3.
**Requirements:** FR-01, FR-02, AD-7.
**Binding invariants:** AD-7 (exact-match resolution) → contracts §5 I4; session context never authorizes (AD-5 → I13).
**Files:** `service/core/intent.py`, `service/app/session_registry.py`.
**Schema/DTO:** `IntentCode`, `Intent`, `TurnDTO`.
**ATDD path:** `test/atdd/module12_contracts.test.py::test_assemble_evidence_precondition_rejects_unregistered_intent`, `::test_submit_query_*`.
**DoD:** 100% of the four mandatory scenario queries route to the correct registered handler; no force-routing; follow-up reference resolves from context then re-validates against state before citing; reset clears all context.

As Nadia,
I want the console to route the schedule, retrospective and runbook questions and to resolve follow-up references in context,
So that I can move between related questions without repeating full entity names.

**Acceptance Criteria:**

**Given** the V1 intent taxonomy now includes access-denial, schedule/window, retrospective and node-triage intents
**When** I submit each mandatory scenario query
**Then** 100% route to the correct registered handler; no intent is force-routed; out-of-domain queries still return clarification (FR-01)
**And** a follow-up reference (`and what about ws-gpu-12?`) resolves against session context first, then re-validates against current state before citing (FR-02, AD-7)
**And** reset clears all context and session context alone never authorizes a destructive action (FR-02)

---

## Epic 4 — Trust & Safe Failure: Nadia is never misled

**Protagonist:** Nadia, whose professional credibility depends on answers being *correct the first
time*; the AI Ops Copilot Assistant as the system protagonist.
**Goal:** when an entity does not exist, a dependency fails, or retrieved content is hostile, Nadia
sees an explicit canonical response instead of a plausible invention.

**FRs:** FR-03, FR-06 (edge case), FR-15, FR-16.
**Implementability notes (Amelia):** This epic carries the **Mandatory Edge Case (4.1)** and the two
**dedicated failure-state stories (4.2 retrieval-side, 4.3 prose/runtime-side)**. Executor failure
is already covered inside 2.4. Each failure story asserts the literal canonical string and that the
`EvidenceSet`/answer is unchanged — the negative space is as testable as the happy path.

### Story 4.1: Anti-fabrication guardrail and content data-hygiene (Mandatory Edge Case)

**Depends on:** Epic 1 (1.3).
**Requirements:** FR-03, FR-06, FR-15, NFR-2, AD-7, AD-11.
**Binding invariants:** AD-7 (exact-match resolution) → contracts §5 I4; AD-11 (content is data, never control) → contracts §5 I16; NFR-2 anti-fabrication. Enforcement: resolver exact-match lookup + content-hygiene guard returning `S_ENF` before diagnosis proceeds.
**Files:** `service/core/resolve.py` (exact-match), `service/core/content_hygiene.py` (data-not-control guard), `service/core/strings/canonical_strings.py` (`S_ENF`).
**Schema/DTO:** `ErrorBody`; `AnswerDTO`; `ResolvedEntitySet`. SQL: `evidence` unchanged on refusal (no partial write).
**ATDD path:** `test/atdd/module12_contracts.test.py::test_edge_ec_answer_query_imaginary_entity_is_canonical_not_fabricated`, `::test_edge_ec_resolve_entities_never_fabricates_an_imaginary_entity`, `::test_edge_ec_resolve_entities_names_only_the_unresolved_refs`, `::test_injection_corpus_*`.
**DoD:** ≥ 10 non-existent references → 100% `Entity Not Found in State`; fabricated-entity rate 0; defined injection corpus → 100% behavioural parity with clean fixtures and 0 destructive triggers; a red test for FR-15/AD-11 exists.

As Nadia,
I want a clean "Entity Not Found in State" whenever a referenced person, policy or event does not exist, and retrieved content to never steer the Copilot,
So that I never relay a plausible but invented operational narrative.

**Acceptance Criteria:**

**Given** the resolver and the diagnosis gate treat every reference as an exact-match lookup and retrieved content as data, never instructions
**When** I ask about an imaginary user, a non-existent policy, or an event that never occurred
**Then** each unresolved reference returns the literal `Entity Not Found in State: {ref_list}.` naming every unresolved reference, with 0 fabricated detail, and diagnosis never proceeds (FR-03, NFR-2)
**And** on a corpus of ≥ 10 non-existent references, 100% return Entity-Not-Found and the fabricated-entity rate across the defined corpus is 0 (FR-03, NFR-2)
**And** a defined injection corpus (instruction-like payloads embedded in query text and in retrieved records — job names, node descriptions, policy clause text, event reasons) yields 100% behavioral parity with the clean fixtures and never triggers a destructive dry-run/confirmation (FR-15, AD-11)

### Story 4.2: Safe failure on retrieval dependencies

**Depends on:** Epic 1 (1.3).
**Requirements:** FR-16, AD-12, NFR-7.
**Binding invariants:** AD-12 (safe failure) → contracts §5 I17; NFR-7 availability (0 hard crashes, cold-start ≤ 60 s).
**Files:** `service/app/failures.py`, `service/ports/out/*` (typed `ok | failure`).
**Schema/DTO:** `ErrorBody`; fault codes (`PROVIDER_UNAVAILABLE`, `CLOCK_UNAVAILABLE`).
**ATDD path:** `test/atdd/module12_contracts.test.py::test_assemble_evidence_fault_provider_down_returns_s_pua_no_partial_evidence`, `::test_diagnose_schedule_window_fault_clock_unavailable`.
**DoD:** state/policy/clock failure aborts before prose with literal `Provider unavailable — cannot answer.` (503) and 0 fabricated detail; no partial evidence/window/runbook emitted; 0 hard crashes; safe retry path rendered.

As Nadia,
I want an explicit degradation when state, policy or the clock is unavailable,
So that I get "cannot answer" instead of a confidently invented reason.

**Acceptance Criteria:**

**Given** every pipeline stage returns a typed `ok | failure` result
**When** the state provider, the policy source or the clock fails or times out mid-request
**Then** the request aborts before prose and returns the literal `Provider unavailable — cannot answer.` (`PROVIDER_UNAVAILABLE` / `CLOCK_UNAVAILABLE`, HTTP 503) with zero fabricated detail and 0 hard crashes (FR-16, AD-12, NFR-7)
**And** no partial evidence, window or runbook is emitted after a failure (AD-12)
**And** the console renders the provider-unavailable banner with the failure reason and a safe retry path (FR-16, UX-DR7)

### Story 4.3: Safe failure on the prose runtime and malformed input

**Depends on:** 1.4, 4.2.
**Requirements:** FR-16, AD-2, AD-8, AD-12, NFR-7.
**Binding invariants:** AD-2 (evidence determinism) → contracts §5 I2, I5; AD-8 (claims/citation) → I3; AD-12 (safe failure) → I17; NFR-7 (0 crashes, cold-start ≤ 60 s).
**Files:** `service/adapters/llm/ollama_prose.py`, `api/routes/*` (input validation).
**Schema/DTO:** `ErrorBody`; codes `LLM_UNAVAILABLE`, `LLM_PROSE_REJECTED`, `VALIDATION_MALFORMED_BODY`, `VALIDATION_EMPTY_QUERY`, `VALIDATION_QUERY_TOO_LONG`.
**ATDD path:** `test/atdd/module12_contracts.test.py::test_submit_query_precondition_rejects_empty_query`, `::test_answer_query_precondition_rejects_overlong_query`, `::test_submit_query_precondition_rejects_absent_session_is_404`.
**DoD:** prose timeout or evidence-vocabulary token on retry → `Provider unavailable — cannot answer.` (503) with 0 fabricated detail; malformed input → HTTP 400, 0 crashes; deterministic evidence/citations unaffected by prose rejection; cold-start recovery ≤ 60 s.

As Nadia,
I want the Copilot to survive a prose-runtime failure or a malformed request without inventing anything or crashing,
So that the console stays trustworthy and usable even when a dependency is down.

**Acceptance Criteria:**

**Given** the LLM prose port is invoked exactly once per answer and prose is token-scanned against the `EvidenceSet` vocabulary (reject-and-retry-once, never strip)
**When** the Ollama prose call times out, or its output is rejected for containing evidence-vocabulary tokens on the retry, or a request body is malformed
**Then** the request returns `Provider unavailable — cannot answer.` (`LLM_UNAVAILABLE` / `LLM_PROSE_REJECTED`, HTTP 503) with zero fabricated detail (FR-16, AD-2, AD-8, AD-12)
**And** malformed input returns HTTP 400 (`VALIDATION_MALFORMED_BODY` / `VALIDATION_EMPTY_QUERY` / `VALIDATION_QUERY_TOO_LONG`) with 0 hard crashes (FR-16, NFR-7)
**And** the deterministic evidence set and citations are unaffected by prose rejection (the LLM contributes no facts); cold-start recovery ≤ 60 s (NFR-7)

---

## Story Dependency & Sizing Table (John + Amelia)

Each story depends **only** on stories in earlier rows — no forward dependencies.

| Story | Title | Depends on | Est. size | Primary verification |
|---|---|---|---|---|
| 1.1 | Seed fixture estate + read-only adapter ring | — | M | fixtures load; ports query-only; typed `ok\|failure` |
| 1.2 | Console shell, session store, intake | 1.1 | M | FR-02 session/reset; FR-01 routing corpus |
| 1.3 | Entity resolution + access-denial (walking skeleton) | 1.1, 1.2 | L | S1 end-to-end fixture accuracy 100% |
| 1.4 | Claims, citations, determinism | 1.3 | M | citation-coverage + determinism (3×) tests |
| 1.5 | Audit log + state inspection | 1.3 | M | append-only; 0 secrets; field-for-field match |
| 2.1 | Destructive classification + refusal | 1.3 | S | 0 mutations; `ACTION_REFUSED` |
| 2.2 | Dry-run snapshot + selector | 2.1 | M | 100% affected items; snapshot re-executable |
| 2.3 | Confirmation gate + re-validation | 2.2 | M | distinct confirm; `CONFIRMATION_STALE` path |
| 2.4 | Propose-only handoff + executor failure | 2.2, 2.3 | M | exactly-once dispatch; `actor=executor`; `EXECUTOR_UNAVAILABLE` |
| 3.1 | Schedule + window diagnosis | 1.3 | M | S2 fixture match; no-constraint case |
| 3.2 | Retrospective event-log diagnosis | 1.3 | S | fixture events 100%; `CANNOT_CONFIRM` |
| 3.3 | Runbook registry + node triage | 1.3 | M | 100% step-match; `RUNBOOK_NOT_FOUND` |
| 3.4 | Taxonomy extension + follow-up context | 3.1, 3.2, 3.3 | S | routing 100%; follow-up resolution |
| 4.1 | Anti-fabrication + content hygiene (EC) | 1.3 | M | ≥10 refs → E-Not-Found; injection parity |
| 4.2 | Safe failure — retrieval deps | 1.3 | S | `PROVIDER_UNAVAILABLE`/`CLOCK_UNAVAILABLE` |
| 4.3 | Safe failure — prose runtime + malformed input | 1.4, 4.2 | S | `LLM_UNAVAILABLE`; HTTP 400; 0 crashes |

### Implementability review (John — PM)

- **User value is explicit in every epic**: S1 (Epic 1), S4 (Epic 2), S2+S3 (Epic 3), EC + safe
  failure (Epic 4). No "database layer" or "API layer" epics.
- **Epic 2 is sequenced before Epic 3** by risk: the safety state machine is the highest-risk,
  highest-value differentiator and must not be starved by diagnostic breadth.
- **Every mandatory scenario and the edge case has a home**, and the six prototype surfaces
  (console, inspector, audit, safety) are delivered across Epics 1–2.
- **Open scoping risk:** 1.3 is Large. If it overflows a session, split the LLM-prose call out
  behind the already-defined `llm_prose_port` (no story boundary changes needed).

### Implementability review (Amelia — Dev)

- **No forward dependencies** — the dependency table is acyclic and Epic 2/3/4 depend only on Epic 1.
- **Interfaces are frozen before they are consumed**: ports in 1.1, `EvidenceSet`/`Claim` in 1.4,
  the executor contract in 2.4. Later stories extend the taxonomy and add diagnosers without
  reopening earlier ports (AD-13).
- **Every AC is a runnable assertion** drawn from `contracts.md` (literal canonical strings, typed
  error codes, HTTP statuses), so each story is independently demoable and testable in one session.
- **Cross-cutting NFRs are asserted where the risk lives**: determinism in 1.4, audit/secret
  redaction in 1.5, safe failure in 4.2/4.3 — not deferred to a "hardening" epic.
