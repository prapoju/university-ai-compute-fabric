# Module 12 — UX Validation ([V])

**Validates:** the four scenario outlines (`C-UX-Scenarios/01–04`), the two wireframes (`wireframes/01`, `wireframes/02`), and the surface specifications (`SPECIFICATIONS.md`) against the PRD, the experience/visual spines, and the Module 12 ownership boundaries.

**Method:** every mandatory validation dimension is walked **per scenario**. Verdicts: ✅ pass · ⚠ pass-with-note · ❌ fail (none below). Boundary contradictions are **flagged, not expanded** — they feed the UX edge-case review (`review-ux-edge-cases.md`).

---

## S1 — Access Denial Diagnosis

| Dimension | Verdict | Evidence / note |
|---|---|---|
| Missing entities | ✅ | `Entity Not Found in State: "alex", "deepseek-coder"` neutral card, mono refs, Diagnosis chip unpopulated (FR-03; scenario 01; wireframe 01 §3) |
| Edge case — non-existent policy (D19) | ✅ | A query referencing a non-existent policy (e.g., `policy#catalog.9.9`) renders the canonical `Entity Not Found in State` naming the unresolved policy; Diagnosis chip unpopulated; completes the EC trio (imaginary user + non-existent policy + event never occurred via FR-06) (FR-03, NFR-2; scenario 01 Entity-Not-Found State) |
| Insufficient evidence | ✅ | `Cannot confirm (insufficient evidence)`; states what was checked, what is not claimed (FR-04/FR-06; S-3) |
| Provider failure | ✅ | `Provider unavailable — cannot answer.` banner + Retry, query retained, zero fabricated detail (FR-16) |
| Malformed input | ✅ | Clarification prompt; never force-routed (FR-01; S-A Empty/error) |
| Rejected actions | ✅ | N/A for diagnostic intent; destructive verb in a compound query → clarification (FR-01, UX-04) |
| Confirmation requirements | ✅ | N/A — no action proposed (S1 has no Proposal/Execution stages) |
| Delegated execution failure | ✅ | N/A — S1 never reaches a delegation card |
| Auditability | ✅ | Audit tab shows the retrieval calls, append-only, params summary only (FR-11, NFR-11; scenario 01 Final/Audit) |
| Accessibility / WCAG 2.1 AA | ✅ | `aria-live`, verbatim canonical strings, never color alone, ≥24px targets (S-A Accessibility; EXPERIENCE.md Accessibility Floor) |
| Ownership boundaries | ✅ | Console explains only; no enforcement, no mutation control anywhere (PRD §2.3, §2.4) |
| Evidence/citation visibility | ✅ | Every factual claim ≥ 1 citation; broken citation downgrades the answer (FR-13; UX-12) |
| Hallucination prevention | ✅ | Canonical Entity-Not-Found; zero fabricated entities/policies/events (FR-03, EC, NFR-2) |
| **UI never implies Module 12 mutates** | ✅ | Inspector read-only marker; no job/node/model controls on this surface |

## S2 — Night Schedule Inquiry

| Dimension | Verdict | Evidence / note |
|---|---|---|
| Missing entities | ✅ | `Entity Not Found in State: "group-4"`; no window computed (FR-03; scenario 02) |
| Insufficient evidence | ✅ | No governing constraint → explicit "no constraint applies", **no window rendered**; or `Cannot confirm` (FR-05) |
| Provider failure | ✅ | Clock/policy failure → banner or cannot-confirm; **a window is never fabricated from a failed clock read** (FR-05, FR-16; UX-11) |
| Malformed input | ✅ | Clarification path (FR-01) |
| Rejected actions | ✅ | N/A — schedule inquiry is diagnostic; no scheduling action offered |
| Confirmation requirements | ✅ | N/A — Module 12 never schedules/reserves (PRD §2.3, §2.4) |
| Delegated execution failure | ✅ | N/A — no delegation in S2 |
| Auditability | ✅ | Clock read + policy read + window computation logged (FR-11) |
| Accessibility / WCAG 2.1 AA | ✅ | Next-window value rendered as first-class mono fact with citation; screen-reader announcement (EXPERIENCE.md Flow 2) |
| Ownership boundaries | ✅ | Explains the restriction; the scheduler owns window enforcement; no schedule control in UI (PRD §2.3) |
| Evidence/citation visibility | ✅ | Restriction + next-window start each carry resolvable citations (FR-13) |
| Hallucination prevention | ✅ | Window value is policy-derived and clock-cited; never inferred (FR-05, FR-14) |
| **UI never implies Module 12 mutates** | ✅ | No scheduling/reservation action control exists |

## S3 — Node Triage Runbook

| Dimension | Verdict | Evidence / note |
|---|---|---|
| Missing entities | ✅ | `Entity Not Found in State: "ws-gpu-11"`; no runbook offered (FR-03; scenario 03) |
| Insufficient evidence | ✅ | Unknown code → `no runbook available for code X`; provenance-missing → unavailability (FR-07, FR-08, S-4; UX-14) |
| Provider failure | ✅ | Node-store/template-registry failure → banner + Retry; no fabricated steps (FR-16) |
| Malformed input | ✅ | Clarification path (FR-01) |
| Rejected actions | ✅ | No "uncordon"/"remediate" control exists on any surface (UX-22 rejected) |
| Confirmation requirements | ✅ | N/A — runbook is a recommendation; no action Module 12 executes (FR-07, §2.3) |
| Delegated execution failure | ✅ | N/A — S3 never reaches delegation |
| Auditability | ✅ | Node read + template lookup logged; template provenance/version shown (FR-08, FR-11) |
| Accessibility / WCAG 2.1 AA | ✅ | Danger warning strip text+icon; steps in template order; focusable steps (S-A Runbook card) |
| Ownership boundaries | ✅ | Recommends runbook; uncordon + physical remediation are node-management's; safety certification stays institutional (FR-08, OQ-11) |
| Evidence/citation visibility | ✅ | Cordon + error-code claims cited to node record; runbook traceable to template ID (FR-08, FR-13) |
| Hallucination prevention | ✅ | Steps come only from the registered template; 0 invented steps (FR-07, FR-08) |
| **UI never implies Module 12 mutates** | ✅ | Runbook card carries no uncordon/execute control; provenance makes it a recommendation |

## S4 — Destructive-Action Safety Guardrail

| Dimension | Verdict | Evidence / note |
|---|---|---|
| Missing entities | ✅ | Unresolved destructive target → `Entity Not Found in State` **before** any dry-run (UX-01; wireframe 02 §3) |
| Insufficient evidence | ✅ | Affected set unestablishable → safe-failure; dry-run never shows a guessed scope (FR-16) |
| Provider failure | ✅ | Executor unavailable → delegation card failure, proposal preserved, no auto-retry (FR-10, FR-16; UX-05) |
| Malformed input | ✅ | Clarification for compound-with-destructive; destructive verb never decomposed (FR-01, UX-04) |
| Rejected actions | ✅ | `Action refused.` banner; the console exposes **no execution control**; double-confirm can only dispatch (FR-09, UJ-4) |
| Confirmation requirements | ✅ | Explicit, distinct confirm; procedural gate, provider-independent; non-authorizing caption (FR-09, D9, C-8, UX-20) |
| Delegated execution failure | ✅ | Exactly-once invariant; double-apply surfaces as executor-failure, never second success (FR-10, UX-06) |
| Auditability | ✅ | Full append-only sequence; proposal vs. applied mutation separately logged; zero secrets (FR-11, NFR-11; wireframe 02 Audit) |
| Accessibility / WCAG 2.1 AA | ✅ | `role="alertdialog"` + `aria-describedby`; Esc returns to dry-run; confirm never auto-focused; full keyboard operation |
| Ownership boundaries | ✅ | Copilot performs no mutation; executor applies post-gate; UI renders executor-originated result (FR-10, C-1, S-6) |
| Evidence/citation visibility | ✅ | Dry-run items linked to job records; proposal vs. mutation labeled distinctly (FR-10) |
| Hallucination prevention | ✅ | Dry-run enumerates only real pending jobs from state (FR-09, FR-03) |
| **UI never implies Module 12 mutates** | ✅ | Every success reads as `Executor-applied mutation`; the delegation card never renders a Copilot action (FR-10; wireframe 02 §4) |

---

## Cross-scenario / console-wide checks

| Dimension | Verdict | Evidence / note |
|---|---|---|
| All required error states present | ✅ | 13-state matrix covered in EXPERIENCE.md State Patterns; wireframes annotate each |
| State never communicated by color alone | ✅ | Every status = dot + text + icon (DESIGN.md; SPECIFICATIONS S-A) |
| Retrieved content is data, never instructions | ✅ | Mono, bounded, un-styled; injection payloads have no control effect (FR-15, S-7, UX-13) |
| Compound queries | ✅ | Decompose when safe or clarify; destructive-included → clarification (FR-01, UX-04) |
| Session context / reset | ✅ | Follow-up entity resolution; reset cancels in-flight, never auto-continues a destructive flow (FR-02, UX-08) |
| Deterministic evidence/citations | ✅ | Fixed evidence payload; prose may vary (FR-14, NFR-4) |
| Latency budget | ✅ | p95 ≤ 3s cited answer / ≤ 5s runbook (NFR-5) — UI shows no partial content while waiting |
| Concurrency | ✅ | ≥ 5 sessions; session-level scoping (NFR-6, A-15) |
| Open confirmation blocks navigation | ✅ | UX-07 enforced in SPECIFICATIONS S-D Navigation |
| Empty dry-run no-op | ✅ | `0 affected items` disables confirmation (UX-02; wireframe 02 §3) |
| Stale dry-run snapshot | ✅ | Re-validation re-opens the dry-run on scope delta (UX-03; wireframe 02 §3) |

---

## Validation summary

**Re-run (D20):** this validation was re-run **after** the D16–D22 fixes were applied, with a **cross-artifact contradiction sweep** added to the method (the prior pass returned "0 failures" while known contradictions existed and was declared not credible). The sweep checks the artifact set against itself and the decision log, not just against the PRD.

**Cross-artifact contradiction sweep result:**

| Previously-flagged contradiction | Decision | Status after fix |
|---|---|---|
| Composer counter `1180/1000` in DESIGN.md:318 / wireframe 01 | D16 | ✅ Fixed — reads used/limit `180/1000`, never above the cap |
| EXPERIENCE.md:33 destructive-flow surface ownership | D17 | ✅ Fixed — flow inline in thread; only the confirmation dialog is a distinct surface |
| Contrast-failing tokens `ink-muted`/`ink-muted-dark`/`status-reserved` | D18 | ✅ Fixed — tokens darkened; ratios recorded in DESIGN.md token table (all ≥ 4.5:1) |
| Missing non-existent-policy EC variant | D19 | ✅ Fixed — scenario 01 Entity-Not-Found State + this S1 row |
| Zero-failure claim produced by a defect-blind checklist | D20 | ✅ This re-run |
| Dead scenario step-folder references (`01-console/`, `02-dry-run/`, …) | D21 | ✅ Fixed — step tables now reference `SPECIFICATIONS.md` surfaces |
| Answer-chain stage label `OBSERVED` in wireframe 01 | D22 | ✅ Fixed — standardized to `Observation` |

- **❌ Failures:** 0 (after D16–D22 applied; cross-artifact sweep passed).
- **⚠ Pass-with-note:** 0.
- **Boundary contradictions flagged (not expanded):** 5 carried from `review-ux-edge-cases.md` UX-18–UX-22 (direct cancellation on Inspector, Module 12 as system of record, confirmation as authorization, reservation management, uncordon from console). The designs hold the read-only, propose-only line; no contradiction was silently absorbed.

**Explicit ownership verification:** across S1–S4, no surface, wireframe, or spec places a mutating control on Module 12's hands. Access enforcement, scheduling, node cordon/remediation, and job deletion are either (a) not surfaced as controls at all, or (b) surfaced only as a cited explanation / template-backed recommendation / propose-only delegation with an executor result. The UI consistently renders Module 12 as explainer-and-proposer, never executor.