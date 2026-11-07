---
title: Sprint Change Proposal — Impl-2 scope addition (Annex 12.5, 12.6)
date: 2026-11-06
status: approved 2026-11-06 (Q1: no; Q2: keep consistency edits) — applied
mode: batch
trigger: docs/task-impl2.md (Module 12 Annex) + docs/impl2-rules.md
scope: Minor (direct adjustment, Developer agent)
---

# Sprint Change Proposal — Impl-2 scope addition

## 1. Issue summary

Impl-2 (`docs/task-impl2.md`) requires the three Module 12 Annex stories 12.4–12.6, each with a set
testing flow. 12.4 is already in the plan (Epic 2, stories 2-1..2-4, Flow A). There is no story
for **12.5** (k6 latency budget, Flow D) and none for the browser half of **12.6** (Playwright E2E
with POM, Flow E). The Annex token rules (60 s, single-use) also conflict with
`contracts.md confirm_and_dispatch` P2 (15 min). `docs/impl2-rules.md` has already decided how
each conflict is resolved. This proposal only writes those decisions into the plan.

## 2. Impact analysis

| Area | Impact |
|---|---|
| Epic 1 | +3 stories (1.6, 1.7, 1.8 optional). Epic goal unchanged. |
| Epics 2–4 | Content unchanged. 1.7 depends on 3.3 and 1.8 on 2.3/2.4 (see §3, exception). |
| PRD | No change. 1.6's p95 < 800 ms is stricter than NFR-5 (p95 ≤ 3 s), so it is compatible. |
| Architecture | No change. Synchronous HTTP is kept, with no SSE (rules: Streaming output). |
| contracts.md | `confirm_and_dispatch` P2, P5, Time clause (token TTL 60 s, configurable, single-use, replay). |
| openapi.yaml | No change in this proposal. `/api/v1/copilot/query` already exists. `/copilot/chat` belongs to the Epic 2 stories. |
| sprint-status.yaml | Header comment block only (both copies, kept identical). |
| _bmad-output mirror | `planning/epics.md` copied to `_bmad-output/planning-artifacts/epics.md` (byte-identical). |
| Code | None. This proposal writes no production code. |

**Risks the stories must carry (noted, not solved here):**

- **R1 — single SQLite writer vs. 800 ms.** `POST /api/v1/copilot/query` opens a session and writes
  turns and audit rows. contracts.md §submit_query says concurrent writes *queue* on the one WAL
  writer. With 50 concurrent requests, that queueing counts against p95. Story 1.6 states this
  instead of hiding it.
- **R2 — no React console exists yet.** There is no `console/` directory in the repo, although
  story 1.2's Files lists `console/src/App.tsx`. Story 1.7 therefore includes the Vite/React
  scaffold. Its size is L.
- **R3 — no Playwright config yet.** The root `package.json` has `@playwright/test`, but there is
  no `playwright.config.ts`. Story 1.7 adds it with `trace: 'on-first-retry'`.

## 3. Recommended approach

**Direct adjustment.** Add the three stories to Epic 1 as requested and amend one contract
operation. Effort: planning-only edits, about 1 session. Risk: low. Timeline: no re-plan.

**Structure-rule exceptions (recorded, not re-litigated):** with these stories Epic 1 has 8 stories
(the rule says 3–5) and the plan has 19 (the rule says 9–16). Stories 1.7 and 1.8 depend on later
epics. The proposal records all of this as an explicit Impl-2 exception in the Structure-Rule
Compliance table, so the table stays truthful.

## 4. Detailed change proposals

### 4.1 `planning/epics.md`

**(a) Overview, first paragraph**

OLD: `This document decomposes Module 12 into **4 epics / 16 stories**, each epic a vertical`
NEW: `This document decomposes Module 12 into **4 epics / 19 stories** (16 planned + 3 added for Impl-2, Annex 12.5/12.6; 1.8 optional), each epic a vertical`

**(b) NFR Coverage Map:** append `1.6` to NFR-3, NFR-5 and NFR-6. Append `1.7` to NFR-9 and NFR-10.

**(c) Structure-Rule Compliance:** add one row.

NEW row:
`| Impl-2 exception (Annex 12.5/12.6) | Epic 1 carries 8 stories (1.6–1.8 added) and the plan 19; 1.7 depends on 3.3 and 1.8 on 2.3/2.4. Accepted deliberately per docs/impl2-rules.md story map; every other rule above still holds. |`

**(d) New stories, inserted after Story 1.5 and before the `---` that closes Epic 1:**

```markdown
### Story 1.6: Concurrent multi-tool diagnostics under a k6 latency budget

**Depends on:** 1.3, 1.4.
**Requirements:** FR-04, FR-13, NFR-3, NFR-5, NFR-6, AD-1, AD-2, AD-12. Annex 12.5 · **Flow D** (Quality Gate / NFR).
**Binding invariants:** AD-1 (every tool call is a read-only port query) → contracts §5 I18; AD-12 (safe failure, never a crash) → contracts §5 I17; AD-2/AD-8 (the LLM states no fact) → contracts §5 I2, I3.
**Files:** `src/application/` (parallel read-only tool dispatcher over the existing ports, `asyncio.gather`), `tests/nfr/copilot-load.js` (k6), `tests/atdd/test_story_1_6.py`; evidence `docs/evidence/impl2/`.
**Schema/DTO:** no new DTO; reuses `AnswerEnvelopeDTO`, `Claim`, `Citation`.
**ATDD path:** `tests/atdd/test_story_1_6.py` (real app); k6 thresholds in `tests/nfr/copilot-load.js`.
**DoD:** independent tool calls run concurrently; 50 VUs → 100% HTTP 200 with the expected citations; p95 < 800 ms; 0 unhandled tool-timeout exceptions; k6 summary (p95, p99, error rate) saved to `docs/evidence/impl2/`.

As Nadia (and every other operator on shift),
I want a multi-tool diagnostic query to answer quickly even when 50 colleagues ask at once,
So that the Copilot stays usable at the busiest moment of the day.

**Acceptance Criteria:**

**Given** the S1 fixture estate and `POST /api/v1/copilot/query`
**When** the orchestrator needs policy, state (`users_port`, `jobs_port`, `nodes_port`) and catalog reads for one query
**Then** the independent read-only tool calls are dispatched concurrently with `asyncio.gather`, results are assembled in the fixed `EvidenceSet` order (positions unchanged vs. the sequential path, FR-14), and no tool call writes (AD-1)
**And** a tool call that exceeds its budget (measured on the Clock port) or fails returns the typed safe-failure answer (`PROVIDER_UNAVAILABLE`, HTTP 503), never an unhandled exception or HTTP 500 (AD-12)

**Given** 50 concurrent operators each sending `Why was student Alex denied access to model deepseek-coder?`
**When** k6 runs `tests/nfr/copilot-load.js`
**Then** 100% of responses are HTTP 200 and cite `RULE-CAT-04`, `policy#catalog.4.2` and catalog entry `deepseek-coder` (100% cited accuracy, NFR-3)
**And** the measured p95 latency is strictly < 800 ms, including queued single-writer latency (R1), and the run records 0 unhandled tool-timeout exceptions

### Story 1.7: React diagnostic console with cited state cards and runbook copy

**Depends on:** 1.2, 1.4, 3.3 (Impl-2 exception: 3.3 supplies the runbook registry; see Structure-Rule Compliance).
**Requirements:** FR-01, FR-07, FR-08, FR-13, NFR-9, NFR-10, AD-9, UX-DR4. Annex 12.6 · **Flow E** (Playwright E2E + POM).
**Binding invariants:** AD-9 (runbook rendered verbatim from the registry) ; AD-2/AD-8 (badges and cards render only cited evidence); synchronous HTTP — no SSE, a pending state until the response arrives (impl2-rules: Streaming output).
**Files:** `console/` (Vite + React 19 + TS scaffold; route `/helpdesk/copilot`), `playwright.config.ts` (`trace: 'on-first-retry'`), `tests/e2e/pages/CopilotConsolePage.ts`, `tests/e2e/copilot-console.spec.ts`; evidence `docs/evidence/impl2/`.
**Schema/DTO:** no new DTO; consumes `AnswerEnvelopeDTO`, `Citation`; access-denial runbook template added as registry config only (NFR-10).
**ATDD path:** `tests/e2e/copilot-console.spec.ts` through `CopilotConsolePage` only; no `waitForTimeout`, web-first assertions only.
**DoD:** spec passes against the real app; every selector lives in `CopilotConsolePage`; trace captured on retry; Copy Runbook verified via clipboard.

As Nadia (Frontline Lab Helpdesk Specialist),
I want to type a student's complaint into a console and get a cited state card and a runbook I can copy,
So that I can close the ticket at the counter without reading raw state.

**Acceptance Criteria:**

**Given** Nadia is on `/helpdesk/copilot`
**When** she inputs `Student Alex was denied model deepseek-coder. Diagnose and provide runbook.` and clicks `Submit Inquiry`
**Then** a pending state shows until the response arrives (no stream), and the answer renders the cited badge `Verified via Policy Engine [RULE-CAT-04]`
**And** a troubleshooting runbook card renders the registry template's steps verbatim, as formatted step-by-step markdown (AD-9)
**When** Nadia clicks `Copy Runbook to Clipboard`
**Then** a success checkmark badge confirms the copy, and the clipboard text equals the rendered runbook

### Story 1.8 (optional): Inspector, Audit and Safety console surfaces

**Depends on:** 1.5, 1.7, 2.3, 2.4 (Impl-2 exception; see Structure-Rule Compliance).
**Requirements:** FR-09, FR-10, FR-11, FR-12, NFR-11, UX-DR8. UX surfaces S-B, S-C, S-D (`SPECIFICATIONS.md`). Flow E. **Optional — outside the Annex minimum.**
**Binding invariants:** AD-1 (inspector is read-only) → I18; AD-10 (audit has no edit/delete path) → I14; AD-5 (confirmation is procedural) → I13.
**Files:** `console/` views for S-B, S-C, S-D; page objects under `tests/e2e/pages/`; specs under `tests/e2e/`.
**Schema/DTO:** none new; consumes `StateRecordDTO`, `GetAuditPageResponse`, `ProposalDTO`.
**ATDD path:** Playwright specs through page objects only.
**DoD:** each surface renders from its existing API with no state-mutating control outside S-D's confirm; specs pass with web-first assertions.

As Nadia,
I want to inspect raw state, read the audit log and walk the dry-run/confirm flow in the console,
So that every prototype surface from the UX plan is usable from the browser.

**Acceptance Criteria:**

**Given** the console from 1.7
**When** Nadia opens S-B for `user#alex`
**Then** the record renders field-for-field with a `read-only` marker; an unknown entity renders `Entity Not Found in State` (FR-12)
**When** she opens S-C after the S1 investigation
**Then** each tool call appears once in chronological order with no edit/delete control (FR-11)
**When** she submits a destructive request and opens S-D
**Then** the dry-run lists every affected item, the confirmation dialog is `role="alertdialog"`, `Esc` never confirms, and the delegation card shows `Copilot proposal` and `Executor-applied mutation` as separate lines (FR-09, FR-10, UX-DR8)
```

**(e) Story Dependency & Sizing Table:** append three rows.

```markdown
| 1.6 | Concurrent multi-tool diagnostics (k6) | 1.3, 1.4 | M | k6 50 VU: p95 < 800 ms; 100% cited; 0 unhandled timeouts |
| 1.7 | React diagnostic console + runbook copy | 1.2, 1.4, 3.3 * | L | Playwright POM spec; trace on retry |
| 1.8 | Inspector / Audit / Safety surfaces (optional) | 1.5, 1.7, 2.3, 2.4 * | M | Playwright specs for S-B, S-C, S-D |
```
and a footnote under the table: `\* Impl-2 exception to the no-forward-dependency rule (docs/impl2-rules.md story map).`

Rationale: the Annex requires a Flow D and a Flow E story. The rules file places them as 1-6 and 1-7.

### 4.2 `planning/detailed-design/contracts.md` — `confirm_and_dispatch`

**P2**

OLD: `` - P2: `gate_token == proposal.gate_token` and the snapshot is fresh (`now.instant - dry_run_snapshot.snapshot_timestamp <= 15 min`, the token TTL) -> violation: `GATE_TOKEN_INVALID` (HTTP 403) on mismatch; `CONFIRMATION_STALE` (HTTP 409) on an expired token (AD-3, D47). ``

NEW: `` - P2: `gate_token == proposal.gate_token` and the snapshot is fresh (`now.instant - dry_run_snapshot.snapshot_timestamp <= GATE_TOKEN_TTL`, default **60 s**, configurable; Annex 12.4, impl2-rules) -> violation: `GATE_TOKEN_INVALID` (HTTP 403) on mismatch; `CONFIRMATION_STALE` (HTTP 409) on an expired token (AD-3, D47). ``

**P5**

OLD: `` - P5: idempotency and conflict: if a prior dispatch exists for `proposal_id`, an **identical** `(proposal_id, gate_token)` is idempotent — it returns the persisted `Proposal` state with no second executor call; any **differing** confirm against an already-dispatched proposal is -> violation: `CONFIRMATION_CONFLICT` (HTTP 409) (D47). This clause is evaluated before P1's state-invalid branch so the idempotent path is reachable. ``

NEW: `` - P5: single-use token, replay and conflict: a `gate_token` is consumed by the first successful confirm and authorizes at most one dispatch. If a prior dispatch exists for `proposal_id`, a replay of the **identical** `(proposal_id, gate_token)` returns the persisted `Proposal` state and never dispatches again (no second executor call); any **differing** confirm against an already-dispatched proposal is -> violation: `CONFIRMATION_CONFLICT` (HTTP 409) (D47, Annex 12.4 single-use). This clause is evaluated before P1's state-invalid branch so the replay path is reachable. ``

**Concurrency / idempotency:** change `identical (proposal_id, gate_token) confirm is idempotent` to `an identical (proposal_id, gate_token) replay returns the persisted state and never dispatches again (single-use token)`.

**Time:** append `; the GATE_TOKEN_TTL freshness check in P2 is measured on the clock adapter (tests advance the fake clock past 60 s).`

Rationale: impl2-rules rows "Token lifetime" and "Single-use token". The *cryptographic token*
row (`secrets.token_hex(16)`) is an adapter decision with no contract text to change, so this
proposal leaves it out.

### 4.3 `sprint-status.yaml` — both copies (`implementation-artifacts/` and `_bmad-output/implementation-artifacts/`)

Insert at the top of the file, above `# generated:`:

```yaml
# ==== IMPL-2 SCOPE (course task impl-2, Module 12; docs/task-impl2.md, docs/impl2-rules.md) ====
# Annex -> stories -> testing flow
#   12.1        : 1-3 (scaffold 1-1, 1-2)       done
#   12.2        : 3-1                            Flow C (test-after)
#   12.3        : 4-1                            Flow C (test-after)
#   foundations : 1-4, 1-5, 4-2                  Flow B (test-along)
#   12.4        : 2-1, 2-2, 2-3, 2-4             Flow A (ATDD-first)
#   12.5        : 1-6                            Flow D (k6 NFR, tests/nfr/copilot-load.js)
#   12.6        : 3-3 (B), 1-7 (E)               Flow B + Flow E (Playwright POM)
#   optional    : 1-8 (S-B, S-C, S-D surfaces)   Flow E
# epics_source is now 4 epics / 19 stories (Sprint Change Proposal 2026-11-06).
# ===============================================================================================
```

No `development_status` keys change (see open question Q1).

### 4.4 Mirror

`cp planning/epics.md _bmad-output/planning-artifacts/epics.md`, then check with `diff -q` that the files are identical.

## 5. Implementation handoff

- **Scope:** Minor. The Developer agent (Amelia) applies §4.1–4.4 after approval.
- **Next:** `bmad-create-story` for 1-6 and 1-7 (1-8 only if time allows); then `bmad-testarch-nfr` (1-6) and Playwright framework setup (1-7).
- **Success criteria:** both epics.md copies and both sprint-status copies are identical (`diff -q`);
  contracts.md contains no `15 min` token TTL; no file under `src/` changed; the decision log gets
  an `I2-NN` entry for this correction.

## Open questions

- **Q1.** Should `development_status` also get the three backlog keys
  (`1-6-concurrent-multi-tool-diagnostics-under-a-k6-latency-budget`,
  `1-7-react-diagnostic-console-with-cited-state-cards-and-runbook-copy`,
  `1-8-inspector-audit-and-safety-console-surfaces`)? You asked only for the comment block, so they are not included.
- **Q2.** The structure-rule edits in §4.1 (a), (b), (c) and (e) go beyond your list. Without them,
  epics.md contradicts itself ("16 stories", "no forward dependencies"). Keep them or drop them?
