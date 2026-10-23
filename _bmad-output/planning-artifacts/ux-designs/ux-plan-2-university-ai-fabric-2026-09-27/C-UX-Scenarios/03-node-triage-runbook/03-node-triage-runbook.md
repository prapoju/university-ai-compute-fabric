# 03: Nadia's Node Triage Runbook (S3)

**Project:** plan-2-university-ai-fabric
**Created:** 2026-09-27
**Method:** Whiteport Design Studio (WDS)

---

## Transaction (Q1)

**What this scenario covers:**
Nadia asks what to do about node `ws-gpu-11` being cordoned with `ERR_THERMAL_88`. The Copilot retrieves the node state and the approved runbook template, and renders an ordered, cited, step-by-step remediation runbook with safety warnings and provenance — without uncordoning the node or authoring any step.

---

## Business Goal (Q2)

**Goal:** G-3 (actionable, template-backed runbooks), G-2 (zero fabrication), G-5 (boundaries).
**Objective:** UJ-3. Satisfies mandatory scenario **S3**.

---

## User & Situation (Q3)

**Persona:** Nadia (Primary).
**Situation:** A monitoring alert surfaces: `ws-gpu-11` cordoned with `ERR_THERMAL_88`. Nadia must decide what to do; she is moderately technical and follows runbooks but is not an infrastructure expert and will not improvise remediation.

---

## Driving Forces (Q4)

**Hope:** To get a sanctioned, ordered, safe remediation procedure she can follow without guessing.
**Worry:** That the Copilot invents steps for an unknown error code, or that she performs a physical intervention without the approved safety procedure.

---

## Device & Starting Point (Q5 + Q6)

**Device:** Desktop (three-pane ops console), mouse + keyboard.
**Entry:** Console open; Nadia types the alert text she sees on the monitor.

---

## Best Outcome (Q7)

**User Success:** Nadia sees a step-by-step fan/airflow inspection runbook in template order with required tools, a danger safety warning, and the approved-source provenance line.
**Business Success:** S3 fixture runbook 100% step-matches the template (FR-07); 100% of runbooks trace to a registered template with provenance/version (FR-08); 0 invented steps (NFR-2).

---

## Shortest Path (Q8)

1. **Console** — Nadia types `ws-gpu-11 is cordoned with ERR_THERMAL_88. what should i do`.
2. **Console (answer render)** — Copilot resolves the node, confirms cordon + code, pulls the ERR_THERMAL_88 template, renders answer chain `Observation → Evidence → Diagnosis → Recommendation` with the runbook card. ✓
3. **Console (follow)** — Nadia reads the safety warning + steps and follows them. ✓

---

## Trigger Map Connections

**Persona:** Nadia (Primary)

**Driving Forces Addressed:**
- ✅ **Want:** a sanctioned, ordered runbook with safety content she can trust.
- ❌ **Fear:** fabricated remediation steps or a physical action performed without the approved procedure.

**Business Goal:** G-3, G-2, G-5; UJ-3.

---

## Scenario Steps

| Step | Surface spec | Purpose | Exit Action |
|------|--------------|---------|-------------|
| 03.1 | `SPECIFICATIONS.md §S-A` (Console) | Submit the query, render the runbook card | Follow the runbook |

---

## Detailed Scenario Specification

### Actor / Persona

- **Primary:** Nadia (helpdesk operator).
- **System subject:** node `ws-gpu-11` (cordoned, `ERR_THERMAL_88`).

### Goal

Produce an ordered, step-by-step remediation runbook for a cordoned node with a known error code, including safety warnings, required tools, and template provenance/version; refuse to invent steps for unknown codes (FR-07, FR-08). Module 12 **recommends** the runbook; it does not uncordon or physically remediate the node (PRD §2.3, §2.4).

### Preconditions / State

- Simulated state: node `ws-gpu-11` exists, cordon status true, error code `ERR_THERMAL_88` (PRD UJ-3; FR-07 fixture S3).
- Runbook template registry contains an approved template bound to `ERR_THERMAL_88` with provenance + version metadata (FR-08, DP-2).
- Console session open.

### User Intent

- **Explicit query:** `ws-gpu-11 is cordoned with ERR_THERMAL_88. what should i do`
- **Intent classified:** `Node triage / runbook` (FR-01 taxonomy §7.1.1).
- **Entities to resolve:** node `ws-gpu-11`, error code `ERR_THERMAL_88`.

### Conversation Flow

1. Nadia types the query; composer validates.
2. Copilot routes to node-triage intent; resolves `ws-gpu-11` and the code (FR-03).
3. Confirms node exists and is cordoned with the stated code (FR-07).
4. Looks up the runbook template for `ERR_THERMAL_88` in the registry (FR-08).
5. Renders answer chain `Observation → Evidence → Diagnosis → Recommendation`; the runbook card shows steps in template order, required tools, safety warning, provenance + version.
6. If no template exists for the code → `no runbook available for code X`, never fabricated steps.

### Evidence / Tools Queried

| Tool / source | What it returns | FR |
|---|---|---|
| Node store (read contract) | `ws-gpu-11` record: cordon status, `ERR_THERMAL_88`, health | FR-03, FR-12 |
| Runbook template registry | `ERR_THERMAL_88` approved template + provenance/version | FR-07, FR-08 |
| Event log (where cited) | cordon event for `ws-gpu-11` | FR-06 |

### Expected Diagnosis / Recommendation

- **Diagnosis:** node `ws-gpu-11` is cordoned with `ERR_THERMAL_88` (citations to the node record).
- **Recommendation:** ordered fan/airflow inspection runbook steps, required tools/personnel, danger safety warning, approved-source provenance line. Uncordon remains node-management's job (PRD §2.3).

### Citations

- `[S3:node#ws-gpu-11]` — cordon + error-code fields.
- `[S3:runbook#rb-thermal-88]` — template provenance/version.
- `[S3:event#evt-...]` — cordon event (where used).
- Runbook steps are template content, not factual claims to re-cite; the provenance line substantiates the source (FR-08, FR-13).

### UI Surfaces Involved

- **Console** (conversation + answer anatomy; runbook card at the Recommendation stage).
- **State Inspection Viewer** (Inspector tab) — node record and runbook template on click (FR-12).
- **Tool-Call Audit Log** (Audit tab) — node read + template lookup calls (FR-11).

### Normal Flow

1. Type the query; Enter submits.
2. Loading skeleton (answer-anatomy shape).
3. Answer renders: chain `Observation → Evidence → Diagnosis → Recommendation`; runbook card with numbered steps, tools, safety warning, provenance line.
4. Nadia follows the runbook. Uncordon and physical remediation stay outside Module 12 (FR-07, §2.3). Physical-safety certification stays with the institutional content owner (OQ-11).

### Loading State

- Skeleton shaped to answer anatomy; `aria-busy`; no partial runbook steps; no auto-scroll until first render.

### Empty State

- Not applicable to the answer itself; fresh sessions show the standard console empty-state guidance.

### Entity-Not-Found State

- If `ws-gpu-11` does not exist in state: neutral `Entity Not Found in State: "ws-gpu-11"` card; **no runbook is offered** (FR-03).

### Insufficient-Evidence State

- If the node exists and is cordoned but the code has no template → `no runbook available for code ERR_THERMAL_88` (explicit unavailability; never invented steps — FR-07, FR-08, S-4).
- If a physical-intervention template lacks approved-source metadata → render unavailability, not the unvetted steps (FR-08, UX-14).

### Provider / Delegated-Service Failure

- Node-store or template-registry failure → `Provider unavailable — cannot answer.` banner, query retained, Retry; no fabricated runbook (FR-16, S-8).

### Rejection / Denial State

- Not applicable in the happy path. The console offers **no** "uncordon" or "remediate" control anywhere — cordon/uncordon is node-management's job (PRD §2.3; UX-22 rejected).

### Confirmation State

- Not applicable — the runbook is a recommendation, not an action Module 12 executes. No confirmation dialog appears for a runbook (PRD §2.3, §2.4).

### Final / Audit State

- Answer rendered + readable; audit log shows node read + template lookup in chronological order, append-only, parameter summaries only (FR-11, NFR-11).

---

## Traceability to PRD

| Aspect | PRD reference |
|---|---|
| Capability / journey | UJ-3 |
| Scenario | S3 |
| Intent routing | FR-01 |
| Entity resolution | FR-03, NFR-2 |
| Runbook correctness | FR-07, NFR-1 |
| Runbook source / provenance | FR-08 |
| Citation integrity | FR-13, NFR-3 |
| Determinism | FR-14, NFR-4 |
| Content data-hygiene | FR-15 |
| Safe failure | FR-16 |
| Latency | NFR-5, SM-5 |
| State inspection / audit | FR-12, FR-11, NFR-11 |
| Ownership: never uncordons / remediates | PRD §2.3, §2.4, §16; UX-22 |