# UX Scenarios: Module 12 — AI Operations Copilot

> Scenario outlines connecting Module 12 PRD protagonists to concrete operator journeys in the Conversational Operations Console.

**Created:** 2026-09-27
**Author:** Julio with the WDS facilitator (Freya / UX Scenario Facilitator)
**Method:** Whiteport Design Studio (WDS)
**Sources:** PRD `_bmad-output/planning-artifacts/prds/prd-plan-2-university-ai-fabric-2026-09-27/prd.md`; `docs/module_profile.md`; experience spine `EXPERIENCE.md`; visual spine `DESIGN.md`.

---

## Scenario Summary

| ID | Scenario | Persona | Pages / Surfaces | Priority | Status |
|----|----------|---------|------------------|----------|--------|
| 01 | Access Denial Diagnosis | Nadia (Primary) | Console, Inspector, Audit | ⭐ P1 (mandatory S1) | ✅ Outlined |
| 02 | Night Schedule Inquiry | Nadia (Primary) | Console, Inspector, Audit | ⭐ P1 (mandatory S2) | ✅ Outlined |
| 03 | Node Triage Runbook | Nadia (Primary) | Console, Inspector, Audit | ⭐ P1 (mandatory S3) | ✅ Outlined |
| 04 | Destructive-Action Safety Guardrail | Nadia (Primary) | Console, Safety/Confirmation, Audit | ⭐ P1 (mandatory S4) | ✅ Outlined |

---

## Scenarios

### [01: Nadia's Access Denial Diagnosis](01-access-denial-diagnosis/01-access-denial-diagnosis.md)
**Persona:** Nadia — needs correct-first-time citable answers without reading raw state.
**Pages:** Console (submit + render) → Inspector (citation/entity click) → Audit.
**User Value:** A citable, defensible reason she can relay to the student.
**Business Value:** S1 fixture 100% correct; zero fabricated detail; cited explanation end-to-end.

### [02: Nadia's Night Schedule Inquiry](02-night-schedule-inquiry/02-night-schedule-inquiry.md)
**Persona:** Nadia — needs a true, citable window to relay without hesitation.
**Pages:** Console (submit + render next window) → Inspector → Audit.
**User Value:** A real next-open-window value with policy citation.
**Business Value:** S2 fixture 100% correct; window computation matches policy fixture reference.

### [03: Nadia's Node Triage Runbook](03-node-triage-runbook/03-node-triage-runbook.md)
**Persona:** Nadia — needs a sanctioned, ordered runbook with safety content.
**Pages:** Console (submit + render runbook card) → Inspector → Audit.
**User Value:** A template-backed runbook with safety warning + provenance.
**Business Value:** S3 fixture 100% step-match to template; 0 invented steps; provenance traced.

### [04: Nadia's Destructive-Action Safety Guardrail](04-destructive-action-safety-guardrail/04-destructive-action-safety-guardrail.md)
**Persona:** Nadia — needs destructive scope fully visible before anything is proposed.
**Pages:** Console (refusal + dry-run + delegation) → Safety/Confirmation → Audit.
**User Value:** Full visibility of destructive scope; safe, auditable handoff.
**Business Value:** S4 measured: 0 copilot mutations; 100% dry-run; no pre-confirm handoff; full audit.

---

## Page / Surface Coverage Matrix

| Surface | Scenario | Purpose in Flow |
|---------|----------|-----------------|
| Console (conversation + answer anatomy) | 01, 02, 03, 04 | Submit query, render answer chain, diagnosis card, runbook, refusal/dry-run/delegation |
| State Inspection Viewer (Inspector tab) | 01, 02, 03 | Inspect raw records/policy clauses from citations and entity chips (FR-12) |
| Tool-Call Audit Log (Audit tab) | 01, 02, 03, 04 | Append-only record of every tool call; proposal vs. mutation distinct (FR-11) |
| Safety / Confirmation surface | 04 | Refusal → dry-run → explicit confirmation → proposed delegated action → executor result → audit |

**Coverage:** 4/4 core surfaces assigned to scenarios; the four mandatory scenarios (S1–S4) plus the mandatory edge case (EC) are covered within scenario 01 (access-denial) and the console behavior spine.

---

## Next Phase

These scenario outlines feed into **Phase 4: UX Design** where each surface gets:
- Wireframes / conceptual layouts (`wireframes/`)
- Page specifications (`SPECIFICATIONS.md`)
- Validation against error states, boundaries, and accessibility (`VALIDATION.md`)

---

_Generated with Whiteport Design Studio framework_