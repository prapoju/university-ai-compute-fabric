# 04: Nadia's Destructive-Action Safety Guardrail (S4)

**Project:** plan-2-university-ai-fabric
**Created:** 2026-09-27
**Method:** Whiteport Design Studio (WDS)

---

## Transaction (Q1)

**What this scenario covers:**
Nadia types "Delete all pending jobs for CS201." The Copilot refuses direct destructive execution, shows a dry-run of the affected jobs, requires explicit confirmation, and only then emits a propose-only handoff to the simulated executor — with the proposal and the executor-applied mutation kept visibly distinct and fully audited.

---

## Business Goal (Q2)

**Goal:** G-4 (safe and auditable behavior: no direct mutations, dry-run + confirmation, append-only audit), G-5 (module separation).
**Objective:** UJ-4. Satisfies mandatory scenario **S4**.

---

## User & Situation (Q3)

**Persona:** Nadia (Primary).
**Situation:** Mid-hurry, testing the console, Nadia types a destructive-sounding query. She must never trigger a destructive action by accident; the safety gate must make the scope visible before anything is proposed.

---

## Driving Forces (Q4)

**Hope:** To see the exact scope of any destructive action before it can happen, and to have the console refuse to act on her behalf.
**Worry:** That a single slip could delete jobs, or that the console implies it "authorizes" her to delete when it cannot.

---

## Device & Starting Point (Q5 + Q6)

**Device:** Desktop (three-pane ops console), mouse + keyboard.
**Entry:** Console open; Nadia types the query into the composer and presses Enter.

---

## Best Outcome (Q7)

**User Success:** Nadia sees `Action refused.` then a dry-run enumerating every pending CS201 job; she reviews the scope, deliberately confirms, and sees the handoff rendered as a `Copilot proposal` followed by an `Executor-applied mutation` — never as a Copilot action.
**Business Success:** S4 measured: 0 copilot-originated mutations; dry-run enumerates 100% of pending CS201 jobs; no handoff before explicit confirmation; exactly one handoff after; full sequence audited (FR-09, FR-10, FR-11, NFR-8).

---

## Shortest Path (Q8)

1. **Console** — Nadia types `delete all pending jobs for cs201`; Enter.
2. **Console → Safety flow** — Refusal banner (`Action refused.`), then dry-run panel listing every pending CS201 job. ✓
3. **Confirmation dialog** — Nadia reviews scope + count, presses `Confirm & propose to executor`.
4. **Console (delegation card)** — `Copilot proposal` then `Executor-applied mutation` with result + timestamp; Audit tab shows the full sequence. ✓

---

## Trigger Map Connections

**Persona:** Nadia (Primary)

**Driving Forces Addressed:**
- ✅ **Want:** full visibility of destructive scope before anything is proposed.
- ❌ **Fear:** accidental destructive execution, or a console that implies authorization it does not have.

**Business Goal:** G-4, G-5; UJ-4.

---

## Scenario Steps

| Step | Surface spec | Purpose | Exit Action |
|------|--------------|---------|-------------|
| 04.1 | `SPECIFICATIONS.md §S-A` (Console) | Submit the destructive query; refusal banner | Open dry-run |
| 04.2 | `SPECIFICATIONS.md §S-D` (Dry-run) | Review enumerated affected items | Open confirmation dialog |
| 04.3 | `SPECIFICATIONS.md §S-D` (Confirmation dialog) | Deliberate explicit confirm | Dispatch proposal |
| 04.4 | `SPECIFICATIONS.md §S-D` (Delegation card) | Render proposal + executor result | Review audit |

---

## Detailed Scenario Specification

### Actor / Persona

- **Primary:** Nadia (helpdesk operator).
- **System actors:** Copilot (propose-only) and the **simulated executor** (delegated component outside Module 12 that applies the mutation only after the confirmation gate — PRD FR-10).

### Goal

Detect the destructive intent, refuse direct execution, produce a dry-run enumerating every affected item, require explicit confirmation, and only then emit a propose-only handoff; keep the proposal and the executor-applied mutation visually distinct and fully audited (FR-09, FR-10, FR-11).

### Preconditions / State

- Simulated state: several pending jobs for course `CS201` (job IDs, status `pending`).
- Job-control subsystem (external/simulated executor) implements the propose-only handoff contract (DP-4, C-6).
- Console session open.

### User Intent

- **Explicit query:** `delete all pending jobs for cs201`
- **Intent classified:** `Destructive action` (delete verb) (FR-01 taxonomy §7.1.1).
- **Entities to resolve:** target jobs for course `CS201`.
- **Confirmation signal:** a distinct, explicit operator action (not the original query).

### Conversation Flow

1. Nadia types the query; composer validates.
2. Copilot classifies the intent destructive; refuses direct execution.
3. Entity resolution: resolve the CS201 target set (FR-03). If the target cannot be resolved → `Entity Not Found in State` **before** any dry-run (UX-01).
4. Dry-run: enumerate every pending CS201 job with per-item status. Header: `This is a proposal, not an action.`
5. Nadia reviews scope; opens the confirmation dialog.
6. Confirmation dialog restates count + scope; button `Confirm & propose to executor`; caption: `This confirms a proposal for delegation. It does not grant or assert authorization.`
7. On confirm, the propose-only handoff is dispatched to the executor contract (FR-10). The Copilot performs no mutation.
8. Delegation card renders `Copilot proposal` (payload), then `Executor-applied mutation` (result + timestamp) — visually distinct (FR-10).
9. Audit tab shows the full append-only sequence: refusal, dry-run, confirmation, handoff, executor result — proposal vs. mutation separately logged (FR-11).

### Evidence / Tools Queried

| Tool / source | What it returns | FR |
|---|---|---|
| Job/queue store (read contract) | pending jobs for CS201 (ids + status) | FR-03, FR-12 |
| Intent classifier | destructive intent class | FR-01 |
| Confirmation gate (procedural) | explicit operator confirmation | FR-09, D9, C-8 |
| Executor contract (dispatch) | propose-only handoff; result status | FR-10, C-6 |
| Audit store | append-only log of the whole sequence | FR-11 |

### Expected Diagnosis / Recommendation

- **Refusal:** `Action refused. The Copilot performs no mutations.` (S-1).
- **Dry-run:** enumerated pending CS201 jobs (each job ID + status).
- **Proposal:** propose-only handoff payload.
- **Executor result:** applied mutation with status + timestamp, logged executor-originated (FR-10).

### Citations

- The dry-run items are evidence-linked to the job records (`[S4:job#job-...]`).
- The delegation card distinguishes `Copilot proposal` from `Executor-applied mutation` (labels, not citations — FR-10).
- The audit log rows carry the tool-call parameters summary (no secrets, NFR-11).

### UI Surfaces Involved

- **Console** — refusal banner + dry-run panel + delegation card in the thread.
- **Safety / Confirmation surface** — the confirmation dialog (moves off the console surface per IA: the destructive flow never lives on the Console surface alone).
- **Tool-Call Audit Log** (Audit tab) — the full append-only sequence (FR-11).

### Normal Flow

1. Type the destructive query; Enter.
2. Loading skeleton; refusal banner renders: `Action refused.` + first-stage dry-run entry point.
3. Dry-run panel enumerates every pending CS201 job; per-item status; header `This is a proposal, not an action.`
4. Nadia reviews; triggers the confirmation dialog; it restates count + scope; she presses `Confirm & propose to executor`.
5. Delegation card: `Copilot proposal` line, then `Executor-applied mutation` line with success + timestamp.
6. Audit tab shows the full sequence; proposal vs. mutation separately logged (FR-11).

### Loading State

- Skeleton shaped to answer anatomy while the intent is classified and the dry-run is composed; `aria-busy`; no confirmation control during load.

### Empty State

- If the CS201 pending set is empty → dry-run shows `0 affected items` and **disables confirmation**: nothing to propose; Nadia dismisses it; no no-op handoff is ever dispatched (UX-02, FR-09).

### Entity-Not-Found State

- If the destructive target cannot be resolved → `Entity Not Found in State` renders **before** any dry-run; the dry-run never opens on an unresolved target (FR-03, FR-09, UX-01).

### Insufficient-Evidence State

- If the target exists but the affected set cannot be established (e.g., read failure) → safe-failure: `Provider unavailable — cannot answer.` or `Cannot confirm (insufficient evidence)`; the dry-run never renders a guessed scope (FR-16, S-8).

### Provider / Delegated-Service Failure

- **Executor unavailable at dispatch:** delegation card shows `Executor-applied mutation` with failure status + reason; the `Copilot proposal` line is preserved; no auto-retry fires; re-dispatch is a deliberate operator action (FR-10, FR-16, UX-05).
- **Confirm gate is provider-independent:** the procedural confirmation does not require the LLM/provider (UX-05).

### Rejection / Denial State

- Refusal banner is the rejection state: `Action refused.` (S-1). The console never exposes an execution control; a second confirm still cannot make the Copilot execute — it can only dispatch (UJ-4, FR-09).

### Confirmation State

- Confirmation dialog after dry-run review: restates count + scope; primary button `Confirm & propose to executor` (danger); caption `This confirms a proposal for delegation. It does not grant or assert authorization.` (D9, C-8, UX-20 rejected). Esc returns to dry-run; the dialog is never dismissible as "authorized". Stale dry-run snapshot re-validation re-opens the dry-run if scope changed (UX-03). Open dialog blocks session/rail switching (UX-07).

### Final / Audit State

- Audit tab shows the full append-only sequence with proposal vs. applied mutation separately logged, executor-originated mutation clearly marked, zero secrets (FR-11, NFR-11). The delegation card final state reads as executor success/failure, never as a Copilot action (FR-10).

---

## Traceability to PRD

| Aspect | PRD reference |
|---|---|
| Capability / journey | UJ-4 |
| Scenario | S4 |
| Intent routing / destructive verb | FR-01 |
| Entity resolution / unresolved target | FR-03 |
| Refusal, dry-run, confirmation | FR-09, NFR-8 |
| Propose-only handoff | FR-10 |
| Audit log / actor distinction | FR-11, NFR-11 |
| Content data-hygiene | FR-15 |
| Safe failure / executor unavailable | FR-16 |
| Procedural confirmation (not auth) | D9, A-13, C-8 |
| Ownership: never executes | PRD §2.3, §2.4, §16; S-1, S-6 |