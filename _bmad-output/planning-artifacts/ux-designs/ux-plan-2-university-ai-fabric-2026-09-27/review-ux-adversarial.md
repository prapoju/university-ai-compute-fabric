# Adversarial Review — Module 12 UX Artifacts (Phase 2)

- **Lens:** adversarial (bmad-review-adversarial-general)
- **Baseline (canonical PRD):** `_bmad-output/planning-artifacts/prds/prd-plan-2-university-ai-fabric-2026-09-27/prd.md`
- **Artifacts reviewed:**
  - `_bmad-output/planning-artifacts/ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/EXPERIENCE.md`
  - `_bmad-output/planning-artifacts/ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/DESIGN.md`
  - `_bmad-output/planning-artifacts/ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/C-UX-Scenarios/` (00 index + 01–04 outlines)
  - `_bmad-output/planning-artifacts/ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/wireframes/` (01 console, 02 safety)
  - `_bmad-output/planning-artifacts/ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/SPECIFICATIONS.md`
  - `_bmad-output/planning-artifacts/ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/VALIDATION.md`
  - `_bmad-output/planning-artifacts/ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/review-ux-edge-cases.md`
- **Date:** 2026-09-27
- **Method:** Cynical review of the UX artifact set against the canonical PRD (FR-01–FR-16, NFR-1–NFR-11, §15 traceability, §2 boundaries). Findings below; each is cross-referenced to the PRD requirement(s) it touches and classified into the project's triage taxonomy (**Accept** / **Defer** / **Reject**) for downstream handling.

## Findings

1. **Composer countdown contradicts the limit it enforces.** `DESIGN.md:318` and `wireframes/01-primary-operations-console.md:45` show the composer counter as `1180/1000`. `FR-01` caps queries at ≤ 1,000 chars; a counter at 1180 has already exceeded the enforced maximum and can never legally render. The label claims to "protect the 1,000-char limit" while displaying an impossible value. Either the value is a typo (e.g., `180/1000`) or the counter semantics (remaining vs. used) are undefined. Contradiction between the visual spine and `FR-01`.

2. **The destructive flow lives on the Console in the artifacts, contrary to the IA spine.** `EXPERIENCE.md:33` states the destructive flow "never lives on the Console surface itself — it always moves to the Confirmation surface." Yet `Wireframe 02` and `SPECIFICATIONS.md S-D` render the refusal banner, the dry-run panel, and the delegation card **inline in the center thread** (the Console), with only the confirmation dialog as a modal. `Wireframe 02:4` silently rewrites the rule to "never lives on the Console surface *alone*" (emphasis added). The two spines disagree about which surface owns the safety flow, and the phrase was changed without a recorded decision.

3. **`Re-dispatch proposal` conflicts with `FR-10` exactly-once.** `SPECIFICATIONS.md:327` exposes a `Re-dispatch proposal` action on executor failure. `FR-10` requires "exactly one executor call" and its measurable condition states "each confirmed action produces exactly one dispatch, exactly one executor-applied mutation after confirmation (100%)". A re-dispatch is a second executor call for the same confirmed proposal, violating the exactly-once invariant. The UX-05 resolution ("re-dispatch is a deliberate operator action") does not say the re-dispatch re-enters the confirmation gate or is logged as a *new* proposal, so the metric is unenforceable as specified. `UX-06`'s double-apply guard is also undermined if re-dispatch is permitted. Contradiction between the UX and `FR-10`/`NFR-8`.

4. **`ink-muted` text color fails WCAG 2.1 AA contrast in both modes.** `DESIGN.md` claims WCAG 2.1 AA compliance and "status contrast verified against surface-status and surface-base". Computed contrast of `ink-muted #9CA3AF` on `surface-base #F4F6F8` ≈ **2.3:1**, and `ink-muted-dark #6B7280` on `surface-base-dark #0B1220` ≈ **4.0:1** (≈ 3.5:1 on `surface-raised-dark`). Both fail the 4.5:1 AA threshold for text. `ink-muted` is used for placeholders and de-emphasis (composer placeholder, captions). Additionally `status-reserved #A16207` on `surface-status #F1F5F9` ≈ **4.2:1**, just under AA for the 12px badge label. The accessibility claim in `EXPERIENCE.md` Accessibility Floor is not supported by the token set.

5. **Mandatory edge case: the "non-existent policy" variant has no UI state coverage.** PRD §15 `EC` = "imaginary user / non-existent policy / event that never occurred". Scenario 01 covers the imaginary-user variant (`Entity Not Found`), and `FR-06`'s `Cannot confirm` covers the never-occurred event. But no scenario outline, state table, or wireframe defines the `Entity Not Found in State` rendering for a user **referencing a non-existent policy**, which `FR-03` explicitly includes among resolvable entities ("policy"). The EC is only partially covered.

6. **`FR-06` retrospective-diagnosis intent has no scenario.** §7.1.1 registers the intent "Retrospective event diagnosis" ("why was X cancelled/denied/cordoned?"). The scenario index covers S1–S4 + EC only; no journey exercises a retrospective cancellation/denial diagnosis end-to-end. `FR-06`'s measurable condition (retrieve the correct event record 100%) has no dedicated scenario to test against. Partially met inside S1's event grounding, but the taxonomy's standalone intent is unjourneyed.

7. **`FR-02` follow-up reference resolution is never exercised.** `FR-02` requires follow-up entity references ("and what about ws-gpu-12?") to resolve against session context, with a ≥ 95% measurable condition. `EXPERIENCE.md` mentions follow-up resolution in passing, but no scenario demonstrates a follow-up turn, so the interaction and its rendering are unspecified and untested.

8. **`VALIDATION.md` reports zero failures despite containing defects.** `VALIDATION.md:103` concludes "❌ Failures: 0, ⚠ Pass-with-note: 0". The same artifact set contains finding 1 (`1180/1000`), finding 2 (surface-location contradiction), and finding 3 (re-dispatch vs. `FR-10`). A self-validation that returns 0 failures while real contradictions exist is not credible; its checklist did not detect them.

9. **Scenario outlines declare step folders that do not exist.** Each outline's "Scenario Steps" table lists per-step folders (`01-console/`, `02-inspector/`, `02-dry-run/`, `03-confirmation/`, `04-delegation/`) per the WDS page-spec convention. Those page-spec files were never created (specs were consolidated into `SPECIFICATIONS.md`), so the scenario outlines contain broken structural references and the WDS deliverable tree is incomplete.

10. **Answer-chain stage label is inconsistent between artifacts.** `DESIGN.md`/`EXPERIENCE.md` name the first stage `Observation`. `Wireframe 01:26` renders it `OBSERVED`. Trivial but real: the wireframe uses a different word from the spine that is contractually the visual reference ("spines win on conflict").

11. **No scenario covers a schedule inquiry where the job can run now.** `FR-05`/S2 covers the "cannot run now + next window" path and the "no constraint applies" path, but no outline covers the positive case (job *can* run at the current time). `NFR-1`'s ≥ 90% on the extension corpus is likely to include such a variant, and the answer-anatomy rendering for it (diagnosis "no restriction applies" + no window) is not specified. Coverage gap.

## Triage

| # | Classification | Rationale | Action |
|---|----------------|-----------|--------|
| 1 | **Accept** | Real defect; contradicts `FR-01`. | Fix the counter value/semantics in `DESIGN.md` + wireframe 01. |
| 2 | **Accept** | Internal IA contradiction; user-facing surface ownership. | Reconcile `EXPERIENCE.md:33` with S-D/wireframe 02; record the decision. |
| 3 | **Defer — needs decision** | Real conflict with `FR-10` exactly-once. Requires deciding whether re-dispatch re-enters confirmation or `FR-10` metric is adjusted. | Do not silently resolve; surface to user. |
| 4 | **Accept** | Token set fails AA; contradicts accessibility claim. | Adjust `ink-muted`/`status-reserved` tokens or constrain their use. |
| 5 | **Accept** | Missing coverage of a mandatory EC variant. | Add explicit `Entity Not Found` state for a policy reference. |
| 6 | **Defer** | Taxonomy intent without a journey; PRD still specifies the FR with a test. | Add scenario or map into S1/EC explicitly; confirm with user. |
| 7 | **Defer** | `FR-02` behavior unspecified in a journey. | Add a follow-up turn example to a scenario. |
| 8 | **Accept** | Validation self-report not trustworthy. | Re-run validation after fixing 1–7; add defect-hunting to the pass. |
| 9 | **Accept** | Broken structural references in the WDS tree. | Create the page-spec files or remove the step tables. |
| 10 | **Accept** | Naming inconsistency with the contract spine. | Standardize to `Observation`. |
| 11 | **Defer — needs decision** | Coverage gap likely exercised by the extension corpus. | Add the positive-case rendering or confirm scope with user. |

## Re-check (post-findings, artifact-to-PRD)

1. **No new scope/boundary violation found** — every artifact stays within read-only + propose-only (§2.3, §2.4); the delegation card always labels executor-applied mutations as executor-originated; no surface control mutates state directly. The re-dispatch finding (3) is an *FR/NFR contradiction*, not a boundary expansion.
2. **Citation integrity, safe failure, data hygiene, and determinism** contracts from the PRD are mirrored correctly in the artifacts.
3. **The 5 previously rejected boundary contradictions** (UX-18–UX-22) remain rejected and are not reopened by this review.

## Decisions escalated

- Re-dispatch vs. `FR-10` exactly-once (finding 3) — requires a decision, not silent resolution.
- EC non-existent-policy coverage (finding 5) and positive-schedule-case coverage (finding 11) — scope-of-coverage decisions.