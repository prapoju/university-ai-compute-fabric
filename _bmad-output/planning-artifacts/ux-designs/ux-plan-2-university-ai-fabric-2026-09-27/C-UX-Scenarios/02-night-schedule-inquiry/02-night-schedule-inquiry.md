# 02: Nadia's Night Schedule Inquiry (S2)

**Project:** plan-2-university-ai-fabric
**Created:** 2026-09-27
**Method:** Whiteport Design Studio (WDS)

---

## Transaction (Q1)

**What this scenario covers:**
Nadia answers "Why can't Group 4 run their fine-tuning job right now?" (clock 15:00) by producing a cited explanation of the Night Policy restriction plus the computed next open window — and explicitly stating when no constraint applies rather than implying one.

---

## Business Goal (Q2)

**Goal:** G-1 (cited deterministic diagnosis in seconds), G-2 (zero fabrication).
**Objective:** UJ-2. Satisfies mandatory scenario **S2**.

---

## User & Situation (Q3)

**Persona:** Nadia (Primary). Secondary subject: Dr. Aris Thorne (NLP Professor, CS101), who sent Nadia a screenshot of a failed launch.
**Situation:** 15:00. A professor's fine-tuning job won't start; he wants to know why and when it can run. Nadia must relay a window that is true and citable.

---

## Driving Forces (Q4)

**Hope:** To give Thorne a precise, citable reason and a real next-open-window time.
**Worry:** That she states a window that is not actually permitted by policy, or that the Copilot fabricates a scheduling answer from a failed clock/policy read.

---

## Device & Starting Point (Q5 + Q6)

**Device:** Desktop (three-pane ops console), mouse + keyboard.
**Entry:** Console open with the current session; Nadia continues the existing thread (session context retained, FR-02).

---

## Best Outcome (Q7)

**User Success:** Nadia relays `next open window: today 20:00–08:00` with the Night Policy clause citation and the clock-read evidence.
**Business Success:** S2 fixture resolved 100% correct (NFR-1); next-window computation matches the policy fixture reference (FR-05 test); zero fabricated windows (NFR-2); diagnosis < 30 s (SM-5).

---

## Shortest Path (Q8)

1. **Console (existing session)** — Nadia types `why can't group 4 run their fine-tuning job right now`.
2. **Console (answer render)** — Copilot resolves Group 4 + job, checks the clock (15:00) against the Night Policy, renders answer chain through `Recommendation` with the next open window. ✓
3. **Console (relay)** — Nadia reads the mono next-window value + citation and relays it; no further action. ✓

---

## Trigger Map Connections

**Persona:** Nadia (Primary)

**Driving Forces Addressed:**
- ✅ **Want:** a true, citable window she can relay without hesitation.
- ❌ **Fear:** stating a policy-violating window or implying a window that policy does not grant.

**Business Goal:** G-1, G-2; UJ-2.

---

## Scenario Steps

| Step | Surface spec | Purpose | Exit Action |
|------|--------------|---------|-------------|
| 02.1 | `SPECIFICATIONS.md §S-A` (Console) | Submit the query, render restriction + next window | Relay the window |

---

## Detailed Scenario Specification

### Actor / Persona

- **Primary:** Nadia (helpdesk operator).
- **Indirect subject:** Dr. Aris Thorne (NLP Professor, CS101) — the complaint originator (PRD §3; associated with UJ-1/UJ-2 only).

### Goal

Explain why Group 4's fine-tuning job cannot run at the current clock time and compute the next open window, citing the governing policy; when no scheduling constraint applies, say so explicitly and render **no** window (FR-05).

### Preconditions / State

- Simulated state: group `group-4`, a pending fine-tuning job bound to the Night Policy; clock reads **15:00** (PRD UJ-2; FR-05 fixture S2).
- Night Policy fixture content restricts fine-tuning/training to a defined night window (exact hours are fixture content, A-10; e.g., 20:00–08:00).
- Console session open; prior-turn context retained (FR-02).

### User Intent

- **Explicit query:** `why can't group 4 run their fine-tuning job right now`
- **Intent classified:** `Schedule/window inquiry` (FR-01 taxonomy §7.1.1).
- **Entities to resolve:** group/job id `group-4` (and its job), current clock time.

### Conversation Flow

1. Nadia types the query; composer validates (non-empty, ≤ 1,000 chars).
2. Copilot routes to schedule/window intent; resolves `group-4` + its pending job (FR-03).
3. Reads the clock (15:00) and loads the Night Policy (FR-05).
4. Determines the job has a scheduling constraint; the current time falls outside the window.
5. Computes the next open window deterministically from the policy fixture.
6. Renders answer chain `Observation → Evidence → Diagnosis → Recommendation`; the next-window value is a first-class mono fact with its own citation.

### Evidence / Tools Queried

| Tool / source | What it returns | FR |
|---|---|---|
| Group/job store (read contract) | `group-4` + pending fine-tuning job record | FR-03, FR-12 |
| Clock/time source | current time `15:00` | FR-05, FR-16 |
| Policy sources (Night Policy) | governing window clause | FR-05 |
| Window computation (deterministic) | `next open window: today 20:00–08:00` | FR-05, FR-14 |

### Expected Diagnosis / Recommendation

- **Diagnosis:** the job is restricted by the Night Policy (fine-tuning is only permitted in the defined night window); current time 15:00 is outside it.
- **Recommendation:** `next open window: today 20:00–08:00` (mono, cited). No scheduling action is offered — Module 12 explains, it never schedules (PRD §2.3, §2.4).

### Citations

- `[S2:policy#night.2]` — the governing window clause.
- `[S2:clock#2026-09-27T15:00]` — clock-read evidence.
- `[S2:job#job-8823]` / `[S2:group#group-4]` — entity records.
- Every factual claim (restriction, next-window start) carries ≥ 1 resolvable citation (FR-13).

### UI Surfaces Involved

- **Console** (conversation + answer anatomy) — primary; the next-window value rendered in mono as a first-class fact.
- **State Inspection Viewer** (Inspector tab) — group/job record and policy clause on click (FR-12).
- **Tool-Call Audit Log** (Audit tab) — clock read, policy read, window computation calls (FR-11).

### Normal Flow

1. Continue current session.
2. Type the query; Enter submits.
3. Loading skeleton (answer-anatomy shape).
4. Answer renders: chain `Observation → Evidence → Diagnosis → Recommendation`; diagnosis cites Night Policy clause; next open window shown as a mono first-class value with its own citation.
5. Nadia relays the window to Thorne. No further action.

### Loading State

- Skeleton shaped to answer anatomy; `aria-busy`; no partial window value shown during load; no auto-scroll until first render.

### Empty State

- If the session is fresh, the empty state is the same console guidance; the schedule inquiry itself is never routed on an empty session (it creates one, FR-02).

### Entity-Not-Found State

- If `group-4` or its job does not exist: neutral `Entity Not Found in State: "group-4"` card (mono), with inspect/correct options (FR-03). No window is computed.

### Insufficient-Evidence State

- If the group/job exists but the governing policy cannot be loaded or no constraint applies: **no constraint applies** is stated explicitly and **no window** is rendered (FR-05). If the policy loads but the window cannot be computed, `Cannot confirm (insufficient evidence)` with what was checked (S-3).

### Provider / Delegated-Service Failure

- Clock failure → safe-failure: `Provider unavailable — cannot answer.` banner (or `Cannot confirm (insufficient evidence)`); **a window is never fabricated from a failed clock read** (FR-05, FR-16, S-8). Policy-source failure → same banner with Retry; query retained.

### Rejection / Denial State

- Not applicable in the happy path (diagnostic-only). If the query also contained a destructive verb → clarification path (FR-01, UX-04).

### Confirmation State

- Not applicable; Module 12 does not schedule or reserve — no action is offered, so no confirmation is required (PRD §2.3, §2.4).

### Final / Audit State

- Answer rendered + readable; audit log shows clock read, policy read, window computation in chronological order, append-only, parameter summaries only (FR-11, NFR-11).

---

## Traceability to PRD

| Aspect | PRD reference |
|---|---|
| Capability / journey | UJ-2 |
| Scenario | S2 |
| Intent routing | FR-01 |
| Session context / follow-up | FR-02 |
| Entity resolution | FR-03, NFR-2 |
| Window inquiry correctness | FR-05, NFR-1 |
| Citation integrity | FR-13, NFR-3 |
| Determinism | FR-14, NFR-4 |
| Content data-hygiene | FR-15 |
| Safe failure (clock/policy) | FR-16 |
| Latency | NFR-5, SM-5 |
| State inspection / audit | FR-12, FR-11, NFR-11 |
| Ownership: never schedules | PRD §2.3, §2.4, §16 |