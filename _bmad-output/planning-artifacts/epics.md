---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - prds/prd-plan-2-university-ai-fabric-2026-09-27/prd.md
  - prds/prd-plan-2-university-ai-fabric-2026-09-27/ai-decision-log.md
  - architecture/architecture-plan-2-university-ai-fabric-2026-09-27/ARCHITECTURE.md
  - ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/DESIGN.md
  - ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/EXPERIENCE.md
  - ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/SPECIFICATIONS.md
  - ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/VALIDATION.md
  - ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/C-UX-Scenarios/00-ux-scenarios.md
  - ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/wireframes/01-primary-operations-console.md
  - ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/wireframes/02-safety-proposed-action.md
---

> **⚠️ SUPERSEDED (2026-10-16).** This is the Phase-4 BMad output (3 epics / 23 stories,
> Story 1.1–3.5). It has been **superseded by `planning/epics.md`** (4 epics / 16 stories,
> Story 1.1–4.3), which is the canonical epic breakdown for this unit. All story bindings in
> `test/traceability-matrix.md` now point at `planning/epics.md`. Retained for history only —
> do not bind new work to the story IDs in this file.

# plan-2-university-ai-fabric - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for plan-2-university-ai-fabric, decomposing the requirements from the PRD, UX Design, and Architecture requirements into implementable stories. Module 12: AI Operations Copilot — an agentic conversational assistant that lets lab helpdesk operators diagnose operational complaints against simulated system state and institutional policy files, with cited, evidence-level deterministic explanations and operational runbooks.

## Requirements Inventory

### Functional Requirements

- **FR-01:** Conversational intake and intent routing — accept NL operational inquiries, route each to exactly one registered intent (or clarify, or decompose compound queries safely); never force-route.
- **FR-02:** Minimal session and conversation context — session creation, context retention across turns, follow-up entity reference resolution, explicit reset; session context never authorizes destructive action.
- **FR-03:** Entity resolution with Entity-Not-Found guardrail — resolve every referenced entity against simulated state; never invent; unresolved → canonical "Entity Not Found in State".
- **FR-04:** Access denial diagnosis — explain why a user was denied a model (role, policy clause, reason class), grounded in event log when the denial occurred.
- **FR-05:** Schedule and window inquiry — explain why a job cannot run now and compute the next open window, citing the governing policy; no-constraint case explicit.
- **FR-06:** Event-log-backed retrospective diagnosis — answer "why was X cancelled/denied/cordoned?" from event-log records; no match → "Cannot confirm (insufficient evidence)".
- **FR-07:** Node triage runbook — produce ordered, template-backed remediation runbook for a cordoned node with a known error code, incl. safety warnings and tools; refuse to invent steps.
- **FR-08:** Runbook source rule — every runbook originates from a registered, curated template bound to an error code, with provenance and version metadata; never from general knowledge.
- **FR-09:** Destructive-action refusal, dry-run & confirmation — detect destructive intents, refuse direct execution, dry-run, require explicit procedural confirmation, then propose-only handoff.
- **FR-10:** Propose-only executor handoff — dispatch confirmed proposals to an external/simulated executor via a defined contract; copilot performs no mutation; proposal vs. applied mutation logged distinctly.
- **FR-11:** Tool-call audit log — append-only, immutable, complete log of every tool call, with retention/rotation and secret redaction; no edit/delete path.
- **FR-12:** State inspection viewer — operator inspects raw simulated state of any entity field-for-field; absent → "Entity Not Found in State".
- **FR-13:** Citation and evidence integrity — every factual claim carries ≥ 1 resolvable citation card; 0 uncited factual claims under the reproducible rubric.
- **FR-14:** Deterministic reproducibility — identical query + state + policy + config → identical evidence set, citations, diagnosis class, runbook steps (prose may vary).
- **FR-15:** Untrusted input & retrieved-content handling — query text and retrieved content are data, never instructions; injection payloads have no control effect.
- **FR-16:** Safe failure on degraded dependencies — on any dependency failure, explicit degradation/cannot-answer response with no invented explanation or fabricated evidence.

### NonFunctional Requirements

- **NFR-1:** Diagnosis accuracy — 100% on the four mandatory fixtures; ≥ 90% on a 20-query extension corpus.
- **NFR-2:** Anti-fabrication — 0 fabricated entities/policies/events over the defined corpus; 100% Entity-Not-Found for non-existent references.
- **NFR-3:** Citation integrity — 100% of factual claims carry citations; 100% of citations resolve to existing records.
- **NFR-4:** Determinism — 100% identity of evidence set, citation set, diagnosis class, runbook steps across 3 runs of each fixture.
- **NFR-5:** Latency — p95 ≤ 3 s submit→rendered cited answer; p95 ≤ 5 s runbook generation; p99 ≤ 8 s; measured on prototype hardware.
- **NFR-6:** Concurrency — ≥ 5 concurrent operator sessions; ≥ 50 queries/hour sustained with no degradation.
- **NFR-7:** Availability & robustness — ≥ 99% over a continuous 8-hour evaluation window; cold-start recovery ≤ 60 s; 0 hard crashes on malformed input.
- **NFR-8:** Safety — 0 copilot-originated mutations; 100% destructive intents trigger refusal + dry-run; 100% require confirmation before handoff; 100% of tool calls audited.
- **NFR-9:** Usability — ≥ 90% of Nadia-class operators complete a diagnosis end-to-end in < 5 min after a 10-min walkthrough; no infra expertise required.
- **NFR-10:** Extensibility — adding a new entity type ≤ 1 dev-day with no console change; adding a runbook template is config-only.
- **NFR-11:** Security / privacy (prototype logging) — audit entries carry operator id (synthetic role id), session id, tool metadata, query-derived entity ids only; no credentials/tokens/secrets; log capped with rotation; no state-mutating console control; no PII beyond simulated identifiers.

### Additional Requirements

**Stack (ARCHITECTURE.md §Stack):** Python 3.11 (3.11.16+); FastAPI 0.141.x; Uvicorn (fastapi[standard]); React 19.x; TypeScript 6.x; Vite 8.x; Ollama 0.34.x (local, prose-only); SQLite (stdlib, assert `sqlite3.sqlite_version` ≥ 3.35 at startup). No ORM or agent framework; thin HTTP adapter to Ollama local API; single FastAPI process + single Vite-served SPA; no queue/broker/cache product.

**Starter template / greenfield seed:** Architecture defines the structural seed (`module12/` with `console/`, `service/api/`, `service/application/`, `service/core/` incl. `intent/`, `evidence/`, `strings/` (canonical_strings constant module), `diagnose/`, `runbooks/`, `service/ports/`, `service/adapters/`, `fixtures/`, `tests/`). Epic 1 Story 1 must scaffold this structure.

**Architecture invariants (AD-1…AD-15, all machine-enforceable):** read-only state boundary; evidence-level determinism via retrieval-composition; propose-only action model; server-side ordered safety state machine; confirmation as procedural gate (not auth); dry-run snapshot re-validation; deterministic exact-match entity resolution; structured claims with citation binding; runbook output only from registered templates; append-only audit with redaction + retention; content data-hygiene; safe failure on any dependency; never expand into the platform control plane; citation identity + evidence ordering; frozen executor contract with adapter as replacement point.

**API contracts:** `POST/GET/DELETE /api/v1/sessions…`; `POST /api/v1/sessions/{sid}/queries`; `GET /api/v1/state/{entity_type}/{id}` + `?q=` browse; `GET /api/v1/answers/{aid}/evidence`; `GET /api/v1/citations/{cid}`; `GET /api/v1/runbooks/{error_code}`; `GET /api/v1/sessions/{sid}/audit?page=&page_size=`; `POST /api/v1/destructive/dry-runs`; `POST /api/v1/destructive/proposals`; `GET /api/v1/destructive/proposals/{pid}`; `POST /api/v1/destructive/proposals/{pid}/re-dispatches`; executor contract `POST/GET /executor/v1/proposals`. All synchronous request/response HTTP.

**Data model (SQLite Module-12-owned):** Session, Answer, Evidence, Claim, ToolCall, AuditRecord, Proposal (state machine `refused → dry_run → confirmed → dispatched → executed/failed/superseded`). Read/consume entities: User, Group, ModelCatalogEntry, AccessPolicyClause, Job, Node, Reservation, PolicyWindow, OperationalEvent. IDs stable `{type}#{id}`.

**Fixture content:** state snapshots (S1 Alex/deepseek-coder, S2 Group 4/night window, S3 ws-gpu-11/ERR_THERMAL_88, S4 CS201 pending jobs), policy content files, runbook templates with provenance/version.

**Deployment (prototype envelope):** one FastAPI process serving REST API + Vite-built console assets; one SQLite file; Ollama daemon local with `OLLAMA_KEEP_ALIVE=-1`; standalone offline (C-5, A-12); SQLite WAL mode for concurrency.

**Tests required:** determinism (FR-14), citation coverage (FR-13), fault-injection (FR-16), injection corpus (FR-15), plus FR-09/FR-10 safety instrumentation.

**Open decisions to honor during planning:** PD-6 (re-dispatch = new proposal with fresh dry-run/confirmation — resolved in architecture); OQ-2/PD-5 fixture values set at fixture-authoring time; remaining OQs (OQ-5, OQ-6, OQ-9, OQ-12, OQ-13) carried as config/lean defaults per decision log.

### UX Design Requirements

- **UX-DR1: Design token system (light + dark).** Implement the full token set from DESIGN.md: cool-gray neutrals; operational status colors (available/reserved/active/fault); semantic colors (warning/danger/evidence-accent/proposal-accent/focus-ring); state surface tints; typography roles (display, headline, title, body, body-emphasis, caption, label, technical, technical-sm, technical-label); spacing scale 4/8/12/16/24/32 (rail 240px, inspector 380px); radii (sm 2px, md 4px, lg 6px, full); elevation rule (shadows only for confirmation dialog + scrolled tab bar). **Include D18 fix:** recompute `ink-muted`/`ink-muted-dark`/`status-reserved` to pass WCAG 2.1 AA 4.5:1 and record ratios in the token table.
- **UX-DR2: Three-pane instrument layout.** Left rail 240px (sessions + entity quick-nav), fluid center thread, right inspector 380px with Evidence/Inspector/Audit tabs; 12-column grid above 1200px; flat 1px-border anchoring, no ambient shadows.
- **UX-DR3: Reusable components (from DESIGN.md).** Implement each: status badge (dot + text + icon, never color alone), citation card, evidence chip, diagnosis card, answer chain, runbook card, refusal banner, dry-run panel, confirmation dialog (`role="alertdialog"`, gravity shadow, non-authorizing caption), delegation card (Copilot proposal / Executor-applied mutation lines), audit row, inspection field, entity chip (mono, labeled copy control), composer (≤1,000 chars, live used/limit counter per D16 — never a value above the cap), provider-unavailable banner, loading skeleton (answer-anatomy shaped), empty state, Entity-Not-Found card (neutral), entity chips.
- **UX-DR4: Answer anatomy.** Render every copilot answer as labeled top-down layers: answer chain (6 fixed stages `Observation → Evidence → Diagnosis → Recommendation → Proposal → Execution`, never skipped/reordered, per D22 label `Observation`), diagnosis card (only component allowed to state a diagnosis; unpopulated on canonical responses), evidence strip with citation cards, recommendation (runbook card / next-window), proposal→execution (S-D only).
- **UX-DR5: Keyboard-first interaction primitives.** Enter submit / Shift+Enter newline; `[`/`]` prev/next session; `e`/`i`/`a` Evidence/Inspector/Audit tabs; `g u/m/n/j/r` entity quick-nav; `c` focus composer; `Esc` close dialog (never confirms); visible focus ring; DOM-order tabbing.
- **UX-DR6: Accessibility floor (WCAG 2.1 AA).** Text ≥ 12px (11.5px only for non-critical metadata); status never communicated by color alone; `aria-live="polite"` on answer region with stage announcements; `aria-busy` on skeletons; confirmation dialog `role="alertdialog"` + `aria-describedby`; focus order = reading order; Reduce Motion respected; labeled (non-icon-only) copy controls; touch/click targets ≥ 24px, interactive rows ≥ 32px; mono values readable ≥ 13px for copyable values.
- **UX-DR7: State patterns (13-state matrix).** Implement treatments for: loading, empty, valid diagnosis, Entity Not Found in State, Cannot confirm (insufficient evidence), provider unavailable, malformed input, delegated/executor failure, rejected/destructive action, confirmation required, proposed action, successful delegated execution, audit result; plus clock-source failure and empty-audit variants. Canonical strings verbatim.
- **UX-DR8: Safety / Confirmation flow (S-D).** Server-side-viewed state machine: refusal banner → dry-run panel → confirmation dialog → delegation card → audit. Dry-run enumerates affected items with per-item status; `0 affected items` disables confirmation; stale-snapshot re-validation re-opens dry-run with delta; unresolved target → Entity Not Found before dry-run; procedural-gate caption; proposal vs. mutation visually distinct; no auto-retry on executor failure; re-dispatch as deliberate operator action.
- **UX-DR9: Responsive behavior.** ≥1280px full instrument; 1024–1279px inspector becomes bottom sheet; 768–1023px rail collapses to icons; <768px single column, top-bar menus, full-screen modal confirmation, horizontally scrollable dense tables with sticky first column. Conversation stays the center of gravity.
- **UX-DR10: Content data-hygiene rendering.** Retrieved content (policy text, names, event reasons, payloads) rendered mono, bounded, un-styled, non-executable, never auto-linked (FR-15). Audit rows show params summary only — no credentials/tokens/secrets.
- **UX-DR11: Four scenario surface coverage.** Wireframe-level implementation of the Console (S-A), State Inspection Viewer (S-B), Tool-Call Audit Log (S-C), Safety/Confirmation (S-D) per SPECIFICATIONS.md, covering the four scenarios S1–S4 + EC (incl. the D19 policy-reference Entity-Not-Found variant in scenario 01) and the mandatory edge case.
- **UX-DR12: Pending UX decisions (carry-forward).** D20: re-run VALIDATION.md with a cross-artifact contradiction sweep after D16–D22 fixes (0-failure claim is not credible). D21: resolve scenario step-folder dead references (create per-step page-spec files or reference SPECIFICATIONS.md). PD-7: add a retrospective-diagnosis scenario/traceability for FR-06. PD-8: add a follow-up reference turn demonstrating session-context resolution (FR-02). PD-9: specify the positive schedule-case rendering ("job can run now" — no restriction, no window).

### FR Coverage Map

| FR | Epic | Brief |
|----|------|-------|
| FR-01 | Epic 1 | Conversational intake and intent routing |
| FR-02 | Epic 1 | Minimal session and conversation context |
| FR-03 | Epic 1 | Entity resolution with Entity-Not-Found guardrail |
| FR-04 | Epic 1 | Access denial diagnosis |
| FR-09 | Epic 2 | Destructive-action refusal, dry-run & confirmation |
| FR-10 | Epic 2 | Propose-only executor handoff |
| FR-05 | Epic 3 | Schedule and window inquiry |
| FR-06 | Epic 3 | Event-log-backed retrospective diagnosis |
| FR-07 | Epic 3 | Node triage runbook |
| FR-08 | Epic 3 | Runbook source rule |
| FR-11 | Epic 1 | Tool-call audit log |
| FR-12 | Epic 1 | State inspection viewer |
| FR-13 | Epic 1 | Citation and evidence integrity |
| FR-14 | Epic 1 | Deterministic reproducibility |
| FR-15 | Epic 1 | Untrusted input & retrieved-content handling |
| FR-16 | Epic 1 | Safe failure on degraded dependencies |

## Epic List

### Epic 1: Operational Console & Access-Denial Diagnosis

Nadia can open the Conversational Operations Console, ask "why was Alex denied deepseek-coder?", and receive a cited, evidence-level deterministic answer with a policy citation she can relay to the student — backed by the read-only spine (routing, session, entity resolution, citations, determinism, audit, state inspection, content hygiene, safe failure).

**FRs covered:** FR-01, FR-02, FR-03, FR-04, FR-11, FR-12, FR-13, FR-14, FR-15, FR-16

**Implementation notes:** Greenfield scaffold from the architecture structural seed (console + service + core + ports + adapters + fixtures + tests). Design tokens (light+dark, incl. D18 contrast fix), three-pane console (S-A/S-B/S-C), answer anatomy (6-stage chain, D22 label), keyboard-first + WCAG 2.1 AA accessibility, 13-state matrix with canonical strings, content data-hygiene rendering, responsive breakpoints. Fixture S1 (Alex / deepseek-coder). Risk: story sizing — this epic is the largest; stories must remain single-dev-agent-sized.

### Epic 2: Destructive-Action Safety & Delegation

Nadia can safely type "delete all pending jobs for CS201" and get refusal → dry-run → explicit procedural confirmation → propose-only handoff to the (simulated) executor, fully audited with proposal vs. applied mutation kept distinct. Delivered risk-first (before Epic 3).

**FRs covered:** FR-09, FR-10

**Implementation notes:** Server-side safety state machine (`refused → dry_run → confirmed → dispatched → executed/failed/superseded`), dry-run snapshot re-validation, procedural-gate semantics (D9/C-8), frozen executor contract (AD-15), S-D surface + Wireframe 02, proposal-vs-mutation audit rows (extends Epic 1 audit). Re-dispatch per PD-6 = new proposal with fresh dry-run + confirmation. Fixture S4 (CS201 pending jobs).

### Epic 3: Schedule, Retrospective & Runbook Diagnostics

Nadia can answer "why can't Group 4 run right now?" with the next open window, "why was this cancelled/denied?" from the event log, and get a sanctioned template-backed node-triage runbook for a cordoned node.

**FRs covered:** FR-05, FR-06, FR-07, FR-08

**Implementation notes:** Builds on Epic 1's pipeline only — window calculator (half-open interval, timezone-aware), event-log retrospective diagnoser, runbook registry with provenance/version (AD-9). Fixtures S2 (Group 4 / Night Policy) and S3 (ws-gpu-11 / ERR_THERMAL_88). Carry-forwards: PD-7 (retrospective scenario UX target), PD-8 (follow-up reference turn), PD-9 (positive schedule-case rendering). Independent of Epic 2 — no cross-dependency.

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic 1: Operational Console & Access-Denial Diagnosis

Nadia can open the Conversational Operations Console, ask "why was Alex denied deepseek-coder?", and receive a cited, evidence-level deterministic answer with a policy citation she can relay to the student — backed by the read-only spine (routing, session, entity resolution, citations, determinism, audit, state inspection, content hygiene, safe failure).

### Story 1.1: Scaffold project from structural seed

As a developer,
I want the project scaffolded from the architecture structural seed with the full stack pinned,
So that all subsequent stories build on a consistent, runnable foundation.

**Acceptance Criteria:**

**Given** an empty `module12/` workspace
**When** the project scaffold runs from the architecture structural seed
**Then** the `console/`, `service/api/`, `service/application/`, `service/core/` (intent/, evidence/, strings/, diagnose/, runbooks/), `service/ports/`, `service/adapters/`, `fixtures/`, and `tests/` directories exist
**And** the backend is a single FastAPI process that starts with `uvicorn` serving a health endpoint, the console is a Vite-served React 19 + TypeScript SPA that builds, and startup asserts `sqlite3.sqlite_version >= 3.35`
**And** a `canonical_strings` constant module exists in the deterministic core as the single owner of the literal strings `Entity Not Found in State`, `Cannot confirm (insufficient evidence)`, `Provider unavailable — cannot answer.`, `Action refused.`, `no runbook available for code X`

### Story 1.2: Design tokens and console shell

As a Nadia-class operator,
I want a three-pane console instrument with the full light/dark token system,
So that the console reads as a data-dense ops instrument, not a chat app.

**Acceptance Criteria:**

**Given** the console SPA is scaffolded
**When** the design tokens from DESIGN.md are implemented
**Then** light and dark modes are equal and complete: cool-gray neutrals, operational status colors (available/reserved/active/fault), semantic colors (warning/danger/evidence-accent/proposal-accent/focus-ring), surface tints, typography roles (Inter + JetBrains Mono), spacing scale (rail 240px, inspector 380px), radii, and the no-ambient-shadow elevation rule
**And** the three-pane shell renders (left rail sessions + entity quick-nav, center thread, right inspector with Evidence/Inspector/Audit tabs) with a 12-column grid above 1200px and a correct empty state ("Ask a question about your fleet…" + composer focus)
**And** `ink-muted`, `ink-muted-dark`, and `status-reserved` meet WCAG 2.1 AA 4.5:1 on their surfaces (D18 fix), with the contrast ratios recorded in the token table

### Story 1.3: Session store and session API

As a Nadia-class operator,
I want sessions created, resumed, and reset with minimal per-session context,
So that follow-up questions stay in context and I can start clean.

**Acceptance Criteria:**

**Given** the FastAPI service is running
**When** I `POST /api/v1/sessions`, submit queries to `POST /api/v1/sessions/{sid}/queries`, read `GET /api/v1/sessions/{sid}`, and `DELETE /api/v1/sessions/{sid}`
**Then** a session is created on first query; resolved entities, prior intents, and active answer ids are retained in the server-side Session store; reset clears all context (FR-02)
**And** a 100% pass on the follow-up test set (≥ 95% of follow-up entity references resolve from prior-turn context), reset clears context 100%, and no session-context path can trigger a destructive dry-run or confirmation without an explicit FR-09 intent (0 occurrences)

### Story 1.4: Intent classifier, taxonomy, and clarification

As a Nadia-class operator,
I want every query routed to exactly one registered intent (or clarified, or safely decomposed),
So that my question is never guessed at or silently truncated.

**Acceptance Criteria:**

**Given** the V1 intent taxonomy is registered (access-denial diagnosis first; others register in later epics)
**When** I submit a query in the console
**Then** 100% of the S1 query routes to the access-denial handler; 100% of out-of-domain queries return the clarification/not-supported response and are never force-routed (FR-01)
**And** a compound query spanning two supported intents either yields two independently validated, cited answers or a clarification prompt (100%), and a compound query for which decomposition is unsafe triggers clarification (100%)
**And** ≥ 95% of a 20-query variant corpus routes correctly, and query text over 1,000 chars is blocked with a validation state

### Story 1.5: Read-only provider ports, mock providers, and entity resolution

As a Nadia-class operator,
I want the Copilot to resolve referenced entities against real simulated state and never invent one,
So that a fabricated reason can never be relayed to a student.

**Acceptance Criteria:**

**Given** the read-only provider ports (users, model catalog + access policy, groups, jobs, nodes, reservations, policy windows, event log, clock, policy content) with in-process mock adapters seeded from fixtures
**When** the entity resolver canonicalizes each reference to `{type}#{id}` and compares exactly (case-folded, no fuzzy)
**Then** unresolved references produce the literal canonical `Entity Not Found in State` naming each unresolved reference, and no diagnosis proceeds (FR-03, AD-7)
**And** on a corpus of ≥ 10 non-existent references, 100% return "Entity Not Found in State" with zero fabricated detail, and the fabricated-entity rate across the defined corpus is 0 (NFR-2)

### Story 1.6: Access-denial diagnosis with S1 fixture

As a Nadia-class operator,
I want a cited explanation of why a user was denied a model,
So that I can point to the exact policy clause when I answer the student.

**Acceptance Criteria:**

**Given** the S1 fixture (Alex / deepseek-coder, policy clause `policy#catalog.4.2`, reason class `not-in-allowlist`, denial event `event#evt-4711`)
**When** I ask "why was alex denied deepseek-coder"
**Then** the diagnosis states the user role, the applicable policy clause with its text, and the reason class, cited to the retrieved records (FR-04)
**And** 100% fixture accuracy on S1, ≥ 90% accuracy across 10 variant denial scenarios, an absent user/model returns "Entity Not Found in State", and a missing rule/event returns "Cannot confirm (insufficient evidence)" (NFR-1)

### Story 1.7: Evidence assembly, claims, citations, and determinism

As a Nadia-class operator,
I want every factual claim bound to resolvable citations and reproducible answers,
So that the same question always yields the same evidence and I can trust what I relay.

**Acceptance Criteria:**

**Given** the evidence pipeline produces a fixed, ordered EvidenceSet with a monotonic `position` per entry and structured Claims bound via a `claim_citations` join
**When** a diagnosis is composed and the LLM renders connective prose over the fixed payload
**Then** 100% of factual claims (per the FR-13 rubric) carry ≥ 1 citation that resolves programmatically, 0 uncited factual claims across the corpus, and the LLM contributes no diagnosis/claim/citation content (FR-13, FR-14, AD-2, AD-8)
**And** running each of the four fixtures 3× yields 100% identity of evidence membership, position sequence, citation set, diagnosis class, and runbook steps (prose may vary) (NFR-4)

### Story 1.8: State inspection viewer

As a Nadia-class operator,
I want to inspect the raw simulated state of any entity directly from the console,
So that I can verify the evidence myself without trusting the answer.

**Acceptance Criteria:**

**Given** `GET /api/v1/state/{entity_type}/{id}` and `GET /api/v1/state/{entity_type}?q=` (browse, case-folded exact-id normalization)
**When** I open an entity chip or citation card in the Inspector surface (S-B)
**Then** the viewer renders the underlying state record field-for-field, 100% match on sampled records, in mono with a `read-only` marker (FR-12)
**And** a non-existent entity renders `Entity Not Found in State` as a neutral card, and the browse result is capped/paginated (AD-13, PD-25)

### Story 1.9: Tool-call audit log

As a Nadia-class operator,
I want an append-only, secret-free audit record of every Copilot tool call,
So that the conversation is auditable without leaking credentials.

**Acceptance Criteria:**

**Given** the Audit Writer + Audit Store (SQLite, append-only via delete/update-denying trigger, single writer)
**When** the Copilot makes tool calls and I open the Audit surface (S-C)
**Then** 100% of tool calls in a 50-call session appear exactly once in chronological order, no UI/API edit or delete path exists, and sampled entries contain 0 credentials/tokens/secrets (redaction filter at write) (FR-11, NFR-11, AD-10)
**And** the log honors a configured retention cap rotating the oldest entries first, and paging never exceeds the cap

### Story 1.10: Cited answer rendering, answer anatomy, and console behavior

As a Nadia-class operator,
I want answers rendered as labeled evidence-first layers with keyboard-first interactions,
So that I can see the diagnosis, its support, and the audit trail at a glance mid-shift.

**Acceptance Criteria:**

**Given** the console surfaces S-A/S-B/S-C and DESIGN.md components are implemented
**When** an answer is rendered
**Then** the six-stage answer chain (`Observation → Evidence → Diagnosis → Recommendation → Proposal → Execution`) is shown in fixed order, never skipped/reordered, with the diagnosis stage populated only when a diagnosis is established (UX-DR4, D22)
**And** the components render with status never communicated by color alone, keyboard shortcuts work (`Enter`, `Shift+Enter`, `[`/`]`, `e`/`i`/`a`, `g u/m/n/j/r`, `c`, `Esc`), loading uses an answer-anatomy skeleton with `aria-busy`, and responsive behavior matches the four breakpoints (UX-DR3, UX-DR5, UX-DR7, UX-DR9)
**And** a broken citation never renders; the answer downgrades to `Cannot confirm (insufficient evidence)` (FR-13)

### Story 1.11: Content data-hygiene and safe failure

As a Nadia-class operator,
I want retrieved content treated as data and any dependency failure to fail safely,
So that injected content can't steer the Copilot and I never get a fabricated answer.

**Acceptance Criteria:**

**Given** the content data-hygiene rules and typed pipeline results
**When** injection-like payloads arrive through query text or retrieved records, and when a dependency (LLM runtime, state provider, policy source, clock, executor) fails
**Then** the injection corpus yields 100% behavioral parity with the clean fixtures (routing, evidence, citations, safety identical) and never triggers a destructive dry-run/confirmation (FR-15, AD-11)
**And** fault-injection for each failure class returns the literal degraded response (`Provider unavailable — cannot answer.` or `Cannot confirm (insufficient evidence)`) with zero fabricated detail and 0 hard crashes (FR-16, AD-12, NFR-7)

### Story 1.12: Accessibility pass and S1 end-to-end verification

As a Nadia-class operator,
I want a WCAG 2.1 AA console and the full S1 journey verified end-to-end,
So that I can complete a diagnosis reliably and the mandatory scenario is demonstrably correct.

**Acceptance Criteria:**

**Given** the console is built
**When** an accessibility audit runs and the S1 scenario is executed end-to-end
**Then** text ≥ 12px, no color-alone status, `aria-live="polite"` with stage announcements, `role="alertdialog"` + `aria-describedby` on dialogs, focus order = reading order, Reduce Motion respected, labeled copy controls, targets ≥ 24px (UX-DR6)
**And** S1 produces the cited answer, the Entity-Not-Found variant ("alexx" / nonexistent model) and insufficient-evidence variant render the canonical responses with the Diagnosis stage unpopulated, and the audit tab shows the retrieval calls (UX-DR11, D19 policy-reference variant)

<!-- End story repeat -->

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic 2: Destructive-Action Safety & Delegation

Nadia can safely type "delete all pending jobs for CS201" and get refusal → dry-run → explicit procedural confirmation → propose-only handoff to the (simulated) executor, fully audited with proposal vs. applied mutation kept distinct. Delivered risk-first.

### Story 2.1: Destructive intent classification and refusal

As a Nadia-class operator,
I want the Copilot to refuse any destructive request on the spot,
So that I can never trigger a mutation by accident.

**Acceptance Criteria:**

**Given** the safety guardrail classifies destructive/mutating intents (delete, cancel, drain, cordon) via the registered taxonomy
**When** I submit a destructive query such as "delete all pending jobs for cs201"
**Then** the Copilot refuses direct execution with the literal `Action refused.` and performs zero mutations; copilot-originated writes to simulated state = 0 (FR-09, NFR-8)
**And** a compound query containing any destructive verb routes to clarification, never to decomposition (FR-01), and the refusal turn is recorded in session context like any other turn

### Story 2.2: Dry-run builder with snapshot and selector predicate

As a Nadia-class operator,
I want to see every affected item before anything is proposed,
So that the full scope of the action is visible before I decide.

**Acceptance Criteria:**

**Given** the Dry-Run Builder persists the affected-item set AND the selector predicate (the exact provider query method + parameters) plus a snapshot timestamp, and issues a per-proposal opaque gate token
**When** a destructive intent is refused
**Then** the dry-run enumerates every pending CS201 job (100%) with per-item status, an unresolved target renders `Entity Not Found in State` before any dry-run (UX-01), and an empty affected set renders `0 affected items` with confirmation disabled (FR-09, AD-4, AD-6)
**And** the dry-run snapshot is re-executable at confirmation time via the stored selector — never re-derived from query text

### Story 2.3: Confirmation gate

As a Nadia-class operator,
I want an explicit, distinct procedural confirmation before anything is handed off,
So that the safety boundary is honest and never reads as authorization.

**Acceptance Criteria:**

**Given** the Confirmation Gate requires a distinct confirmation request echoing the gate token, and re-executes the stored selector to re-validate the snapshot
**When** I confirm a proposal
**Then** confirmation is a distinct HTTP request from the original query; the server records no identity/role claim; session context is never consulted; and the caption reads "This confirms a proposal for delegation. It does not grant or assert authorization." (FR-09, D9, C-8, AD-5)
**And** any change in the re-queried `(id, actionable status)` set refuses dispatch and re-renders the dry-run with the delta surfaced and confirmation disabled (AD-6); if the provider is unavailable during re-validation, the safe-failure response returns and no dispatch occurs

### Story 2.4: Propose-only executor handoff and simulated executor

As a Nadia-class operator,
I want confirmed proposals dispatched to the executor under a frozen contract,
So that the Copilot never executes — only proposes.

**Acceptance Criteria:**

**Given** the frozen executor contract `POST /executor/v1/proposals` (payload: proposal_id, closed-verb action, persisted selector, gate token forwarded verbatim, dry-run reference; response: status, applied_records[], applied_count, timestamp) and the simulated executor as reference adapter
**When** a confirmed proposal is dispatched
**Then** exactly one executor call per confirmed proposal; the Copilot performs zero direct state writes; the executor applies exactly the referenced snapshot's items once, post-confirmation, validating the gate token (FR-10, AD-1, AD-3, AD-15)
**And** a second dispatch attempt for the same proposal id is rejected; the audit log records the executor-applied mutation with `actor = executor`, and a re-dispatch is a NEW proposal with fresh dry-run + confirmation and `supersedes_proposal_id` linkage (PD-6)

### Story 2.5: Safety/Confirmation surface and audit distinction

As a Nadia-class operator,
I want the destructive flow rendered as a fixed, visible state machine with proposal vs. mutation kept distinct,
So that the scope is fully visible and nothing reads as a Copilot action.

**Acceptance Criteria:**

**Given** the Safety/Confirmation surface (S-D) implements the flow `Request → Refusal → Dry-run → Explicit confirmation → Proposed delegated action → Executor result → Audit result`
**When** I traverse a destructive action
**Then** the refusal banner, dry-run panel, confirmation dialog (`role="alertdialog"`, Esc returns to dry-run and never confirms, confirm never auto-focused), and delegation card render per Wireframe 02, with `Copilot proposal` and `Executor-applied mutation` as distinct labeled lines (UX-DR8, D17, FR-10)
**And** an open confirmation dialog blocks session/rail navigation; the audit tab shows the full append-only sequence with proposal vs. applied mutation separately logged; no console control on any surface mutates state directly (FR-11, S-6)

### Story 2.6: Safety instrumentation tests

As a developer,
I want instrumented verification of the safety invariants,
So that 0 copilot mutations, exactly-once dispatch, and auditable attribution are provable.

**Acceptance Criteria:**

**Given** the scenario suite for "delete all pending jobs for CS201" (S4)
**When** instrumented tests run
**Then** (1) copilot-initiated mutations in simulated state = 0; (2) the dry-run enumerates every pending CS201 job; (3) no handoff is dispatched before explicit confirmation; (4) exactly one handoff dispatch after confirmation; (5) the full sequence is present in the audit log; (6) a double-applied record surfaces as executor-failure, never a second success (FR-09, FR-10, NFR-8, UX-06)
**And** executor-unavailable renders the delegation card failure status with the proposal line preserved and no auto-retry (FR-16)

<!-- End story repeat -->

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic 3: Schedule, Retrospective & Runbook Diagnostics

Nadia can answer "why can't Group 4 run right now?" with the next open window, "why was this cancelled/denied?" from the event log, and get a sanctioned template-backed node-triage runbook for a cordoned node. Builds on Epic 1's pipeline only; independent of Epic 2.

### Story 3.1: Schedule and window diagnosis

As a Nadia-class operator,
I want to know why a job can't run right now and when it next can,
So that I can relay a true, citable window to a professor.

**Acceptance Criteria:**

**Given** the S2 fixture (Group 4, clock 15:00, Night Policy window `night`, half-open interval `start <= t < end`, timezone-aware)
**When** I ask "why can't group 4 run their fine-tuning job right now"
**Then** the diagnosis states the governing policy restriction and renders the exact next open window (e.g., `2026-09-28T20:00:00Z`–`2026-09-29T08:00:00Z`, explicit date + timezone), each fact cited (FR-05, AD-14, PD-17, PD-18)
**And** 100% fixture match on S2 and ≥ 95% across 10 window variants; a job with no scheduling constraint explicitly states no constraint applies and renders NO window; a missing group/job returns `Entity Not Found in State`; a failed clock read never fabricates a window (FR-05, FR-16, PD-9)

### Story 3.2: Event-log retrospective diagnosis

As a Nadia-class operator,
I want to know why something was cancelled, denied, or cordoned in the past,
So that I can answer "why was my job cancelled?" without inventing a reason.

**Acceptance Criteria:**

**Given** the minimal event log (access_denied, job_cancelled, node_cordoned events with timestamp, outcome, recorded reason) queried via a read-only contract on a half-open `[start, end)` time window
**When** I ask a retrospective question referencing a past event
**Then** the diagnosis retrieves the matching event record(s) with timestamp, outcome, and recorded reason, cited; each fixture event resolves 100% (FR-06, AD-14, PD-19)
**And** a question about an event that never occurred returns the literal `Cannot confirm (insufficient evidence)` with 0 invented details (FR-06, NFR-2)

### Story 3.3: Runbook registry and node-triage diagnosis

As a Nadia-class operator,
I want a sanctioned, ordered remediation runbook for a cordoned node,
So that I follow approved steps with safety content, not invented guidance.

**Acceptance Criteria:**

**Given** the runbook registry keyed by exact error code with provenance + version metadata, and the node-triage diagnoser confirming cordon status and recorded error code before lookup
**When** I ask about `ws-gpu-11` with `ERR_THERMAL_88` (S3 fixture)
**Then** the runbook renders the registered template's ordered fan/airflow inspection steps verbatim, with required tools, a safety warning, and the approved-source provenance line (FR-07, FR-08, AD-9)
**And** 100% step-match to the template; an unknown code returns the literal `no runbook available for code X` with 0 fabricated steps; a code/node mismatch routes to unavailability for the recorded code; a physical-intervention template lacking approved-source metadata renders unavailability, not the steps; a template with an empty step list is rejected at registration (FR-07, FR-08, PD-22, PD-23)

### Story 3.4: Retrospective, follow-up, and positive-schedule UX targets

As a Nadia-class operator,
I want the retrospective diagnosis, follow-up entity references, and the positive schedule case rendered explicitly in the console,
So that every diagnostic capability has a demonstrable end-to-end UI path.

**Acceptance Criteria:**

**Given** the new diagnostic capabilities from stories 3.1–3.3
**When** a retrospective query renders, a follow-up reference ("and what about ws-gpu-12?") resolves against session context, and a job that CAN run now is diagnosed
**Then** the retrospective answer renders the event evidence with the Diagnosis stage populated (or the canonical response when insufficient), the follow-up turn resolves prior-turn context first then re-validates against current state before citing (FR-02, PD-14), and the positive schedule case renders "no restriction applies" with no window (PD-9)
**And** each of these three cases is covered in VALIDATION.md with a cross-artifact contradiction sweep (PD-7, PD-8, PD-9, D20)

### Story 3.5: S2 and S3 end-to-end verification

As a developer,
I want the schedule and runbook scenarios verified end-to-end against their fixtures,
So that the mandatory scenarios are demonstrably correct and cited.

**Acceptance Criteria:**

**Given** the full pipeline for S2 and S3
**When** the scenarios run end-to-end in the console
**Then** S2 renders the restriction + next open window with citations (100% fixture match), S3 renders the runbook card with provenance (100% step-match), and the audit tab logs the clock/policy reads and node/template lookups (FR-05, FR-07, FR-11)
**And** 3× determinism runs yield identical evidence/citation/diagnosis/step output (FR-14, NFR-4), and the p95 latency targets (≤ 3 s cited answer, ≤ 5 s runbook) are measured and recorded (NFR-5)

<!-- End story repeat -->