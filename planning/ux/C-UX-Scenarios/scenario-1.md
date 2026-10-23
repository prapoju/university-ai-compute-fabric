# 01: Nadia's Access Denial Diagnosis (S1)

**Project:** plan-2-university-ai-fabric
**Created:** 2026-09-27
**Method:** Whiteport Design Studio (WDS)

---

## Transaction (Q1)

**What this scenario covers:**
Nadia answers "Why was Alex denied access to deepseek-coder?" by turning a natural-language complaint into a cited, evidence-level deterministic diagnosis she can relay to the student (Mateo) — or a clean `Entity Not Found in State` / `Cannot confirm (insufficient evidence)` when the evidence cannot support a diagnosis.

---

## Business Goal (Q2)

**Goal:** G-1 (turn a complaint into a cited deterministic diagnosis in seconds), G-2 (zero fabricated entities/policies/events).
**Objective:** UJ-1. Satisfies the mandatory scenario **S1** and edge case **EC** (hallucination prevention).

---

## User & Situation (Q3)

**Persona:** Nadia (Primary). Secondary subjects: Mateo (student, subject of the complaint), AI Ops Copilot Assistant (system protagonist).
**Situation:** Mid-shift, a student (Mateo) is upset at the counter claiming he was denied `deepseek-coder`. Nadia opens the console on the shared lab machine. She must not relay a wrong "reason" to the student.

---

## Driving Forces (Q4)

**Hope:** To get a citable, defensible reason she can point to and relay within seconds, without reading raw state files.
**Worry:** That the Copilot invents a plausible-but-wrong reason, or that she misstates a policy clause to the student and makes the situation worse.

---

## Device & Starting Point (Q5 + Q6)

**Device:** Desktop (three-pane ops console), mouse + keyboard.
**Entry:** Console open on shared lab machine, no auth friction (v1), fresh session — the session list is empty.

---

## Best Outcome (Q7)

**User Success:** Nadia reads a diagnosis stating role `student` is not on the `deepseek-coder` allowlist, clicks the citation card for `policy#catalog.4.2`, sees the exact clause, and relays it to Mateo with confidence.
**Business Success:** S1 fixture resolved 100% correct (NFR-1); zero fabricated detail (NFR-2); 100% of factual claims carry resolvable citations (NFR-3); diagnosis completes well under 30 s (SM-5).

---

## Shortest Path (Q8)

1. **Console (fresh session)** — Nadia types `why was alex denied deepseek-coder` and presses Enter.
2. **Console (answer render)** — Copilot resolves `alex` + `deepseek-coder`, renders answer chain `Observation → Evidence → Diagnosis`, diagnosis card + evidence strip with citation cards. ✓
3. **Inspector (citation click)** — Nadia clicks the `policy#catalog.4.2` citation card; the Inspector opens the exact policy clause text. ✓

---

## Trigger Map Connections

**Persona:** Nadia (Primary)

**Driving Forces Addressed:**
- ✅ **Want:** correct-first-time citable answers without reading raw state.
- ❌ **Fear:** inventing or misstating a reason she relays to a professor/student.

**Business Goal:** G-1, G-2; UJ-1.

---

## Scenario Steps

| Step | Surface spec | Purpose | Exit Action |
|------|--------------|---------|-------------|
| 01.1 | `SPECIFICATIONS.md §S-A` (Console) | Submit the query, render the diagnosis | Click citation card |
| 01.2 | `SPECIFICATIONS.md §S-B` (State Inspection Viewer) | Inspect raw policy clause + user record | Close / new query |

---

## Detailed Scenario Specification

### Actor / Persona

- **Primary:** Nadia, AI Lab Operations Engineer (helpdesk), `Nadia-class operator` (PRD §3, A-15).
- **Indirect subjects:** Mateo (student, subject of the denied-access complaint), Dr. Aris Thorne (course context CS101 — indirectly, per PRD §3 Aris is associated with UJ-1/UJ-2 only).

### Goal

Turn "why was Alex denied deepseek-coder?" into a cited, evidence-level deterministic diagnosis that Nadia can relay; produce the canonical `Entity Not Found in State` / `Cannot confirm (insufficient evidence)` responses when evidence cannot support a diagnosis (FR-03, FR-04).

### Preconditions / State

- Simulated state: user record `alex` (role `student`), model catalog record `deepseek-coder` (allowlist excludes `student`), catalog access policy clause `policy#catalog.4.2` applies to `deepseek-coder` (PRD §5 UJ-1, FR-04 fixture S1).
- Console open, fresh session, no auth friction (v1).
- Event log may contain a prior denial event for `alex`/`deepseek-coder` (retrospective grounding, FR-06).

### User Intent

- **Explicit query:** `why was alex denied deepseek-coder`
- **Intent classified:** `Access-denial diagnosis` (FR-01 intent taxonomy §7.1.1).
- **Entities to resolve:** user `alex`, model `deepseek-coder`, optional time reference.

### Conversation Flow

1. Nadia types the query; composer enforces ≤ 1,000 chars, non-empty.
2. Copilot routes to access-denial intent; resolves `alex`, `deepseek-coder` (FR-03).
3. Retrieves user role, catalog policy clause, and (if available) the denial event (FR-04, FR-06).
4. Composes diagnosis from the fixed evidence payload: role, reason class, policy clause ID + text, citations (FR-13, FR-14).
5. Renders answer anatomy: answer chain `Observation → Evidence → Diagnosis`; diagnosis card; evidence strip with citation cards.
6. Nadia clicks the citation card → Inspector opens the source record.

### Evidence / Tools Queried

| Tool / source | What it returns | FR |
|---|---|---|
| User store (read contract) | record for `alex`, role `student` | FR-03, FR-12 |
| Model catalog + access policy (read contract) | `deepseek-coder` record; allowlist/policy clause `policy#catalog.4.2` | FR-03, FR-04 |
| Event log (read contract) | prior denial event for `alex`/`deepseek-coder` (if present) | FR-06 |
| Clock (optional time reference) | event time / "now" | FR-04, FR-05 |

### Expected Diagnosis / Recommendation

- **Diagnosis:** reason class `not-in-allowlist`; role `student` is denied `deepseek-coder` by `policy#catalog.4.2`.
- **Recommendation stage:** not populated (diagnosis-only scenario); answer chain ends at `Diagnosis`.

### Citations

- `[S1:user#alex]` — role field.
- `[S1:policy#catalog.4.2]` — the governing clause.
- `[S1:model#deepseek-coder]` — catalog allowlist entry (where cited).
- `[S1:event#evt-4711]` — denial event (when the retrospective grounding is used).
- Every factual claim in the diagnosis carries ≥ 1 resolvable citation (FR-13).

### UI Surfaces Involved

- **Console** (conversation + answer anatomy) — primary.
- **State Inspection Viewer** (Inspector tab, right panel) — on citation/entity-chip click (FR-12).
- **Tool-Call Audit Log** (Audit tab) — shows the retrieval calls for this answer (FR-11).

### Normal Flow

1. Empty-state console prompts a sample query.
2. Nadia types the query; Enter submits.
3. Loading skeleton (answer-anatomy shape, `aria-busy`).
4. Answer renders: chain `Observation → Evidence → Diagnosis` (filled), diagnosis card, evidence strip, citation cards.
5. Nadia clicks `policy#catalog.4.2` citation → Inspector opens clause text.
6. Nadia relays the clause; closes session. Audit tab shows the retrieval calls.

### Loading State

- Skeleton shaped to answer anatomy (headline bar, evidence strip, citation placeholders); `aria-busy="true"`; no partial diagnosis; no auto-scroll until first render.

### Empty State

- Fresh session: `Ask a question about your fleet — e.g. "why was Alex denied deepseek-coder?"` with the composer focused; no celebratory copy.

### Entity-Not-Found State

- If `alex` or `deepseek-coder` does not exist in state: neutral (non-error) card titled verbatim `Entity Not Found in State`, listing each unresolved reference in mono (`"alex", "deepseek-coder"`), with an option to inspect raw state or correct the reference (FR-03, FR-12). The Diagnosis chip is **not** populated.
- **Non-existent policy reference (D19):** a query that references a policy that does not exist (e.g., a user cites `policy#catalog.9.9`) renders the same canonical `Entity Not Found in State` card naming the unresolved policy — `policy` is a resolvable entity under `FR-03`. This completes the mandatory EC trio: imaginary user (this scenario), non-existent policy (this variant), and event that never occurred (via `FR-06`/scenario 03 retrospective). The Diagnosis chip stays **unpopulated**; nothing is invented (FR-03, NFR-2).

### Insufficient-Evidence State

- If `alex` and `deepseek-coder` exist but no matching policy clause or no denial event establishes the reason: `Cannot confirm (insufficient evidence)` — the diagnosis stage stays **unpopulated**; the card states what was checked (e.g., `no denial event for Alex on 2026-09-25`) and what is therefore not claimed (FR-04, FR-06, S-3).

### Provider / Delegated-Service Failure

- State-provider or policy-source or LLM-runtime failure → `Provider unavailable — cannot answer.` banner at the top of the thread, query retained, Retry action; no invented explanation, no fabricated evidence (FR-16, S-8).
- Clock failure (if a time reference was needed) → safe-failure: no fabricated time-based claim (FR-05, FR-16).

### Rejection / Denial State

- Not applicable in the happy path; this scenario is diagnostic-only. If Nadia's query also contained a destructive verb, it routes to clarification (compound-with-destructive → clarification, FR-01/UX-04) rather than partial execution.

### Confirmation State

- Not applicable (no destructive/actionable intent in S1).

### Final / Audit State

- Answer rendered + readable; audit log (Audit tab) shows exactly the retrieval calls (user store, policy read, event lookup) in chronological order, append-only, parameter summaries only, no secrets (FR-11, NFR-11).

---

## Traceability to PRD

| Aspect | PRD reference |
|---|---|
| Capability / journey | UJ-1 |
| Scenario | S1 |
| Intent routing | FR-01 |
| Session context | FR-02 |
| Entity resolution / non-fabrication | FR-03, NFR-2 |
| Diagnosis correctness | FR-04, NFR-1 |
| Citation integrity | FR-13, NFR-3 |
| Determinism | FR-14, NFR-4 |
| Content data-hygiene | FR-15 |
| Safe failure | FR-16 |
| Latency | NFR-5, SM-5 |
| State inspection / audit | FR-12, FR-11, NFR-11 |
| Mandatory edge case (imaginary user / non-existent policy / event that never occurred) | EC, FR-03, FR-06, NFR-2 |