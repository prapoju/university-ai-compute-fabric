# UX Edge-Case Review — Module 12 AI Operations Copilot

- **Spines reviewed:** `DESIGN.md`, `EXPERIENCE.md` (run folder `ux-plan-2-university-ai-fabric-2026-09-27`)
- **Method:** Exhaustive path enumeration (edge-case-hunter discipline) over the two spines — every state, flow, and transition in the answer anatomy, safety state machine, and the four Key Flows was walked. Only paths lacking handling are reported. No severity labels.
- **Triage taxonomy:** **Accept** (real gap — handling folded into the spine) · **Defer** (valid, held pending an open PRD question) · **Reject** (boundary contradiction — flagged, deliberately not expanded into scope).
- **Traceability:** each finding cites the PRD requirement (`FR-n` / `NFR-n` / `S-n` / `C-n`) and scenario (`S1`–`S4`, `EC`, `PT`) it touches.

## Rubric Pass 1 self-check (proactive)

- **Flow coverage:** UJ-1 → Flow 1, UJ-2 → Flow 2, UJ-3 → Flow 3, UJ-4 → Flow 4; each has a named protagonist, numbered steps, a climax beat, and failure paths. EC (anti-fabrication) and PT (console surfaces) are covered across IA/Component Patterns and flows. Strong.
- **Token completeness:** all frontmatter color tokens carry light + dark hex; every `{path.to.token}` reference in both spines resolves to a defined token (spot-audited: `colors.*`, `typography.*`, `rounded.*`, `spacing.*`). Strong.
- **Component coverage:** every component named in prose or flows has a row in `DESIGN.md` Components *and* `EXPERIENCE.md` Component Patterns. Strong.
- **State coverage:** all 13 mandatory states present; every IA surface covered for loading/empty/error. Strong.
- **Visual reference coverage:** no mockups/wireframes/imports in this run; `EXPERIENCE.md` states this and asserts spines-win-on-conflict. OK.
- **Shape fit:** DESIGN.md sections in canonical order; EXPERIENCE.md required defaults all present plus earned inventions (Answer Anatomy, Safety & Confirmation Model, Boundary Contradictions).

## Findings

### Accepted (16) — handled in the spines

**UX-01 — Destructive intent with an unresolved target**
- *Path walked:* `Request → …` where intent classification names a target absent from state.
- *Gap:* dry-run would open on a phantom target; ambiguous refusal.
- *Triage:* **Accept**. *Traceability:* `FR-03`, `FR-09`, `S4`.
- *Resolution:* Safety & Confirmation Model — `Entity Not Found in State` renders **before** any dry-run; the dry-run never opens on an unresolved target.

**UX-02 — Empty dry-run**
- *Path walked:* destructive intent matching zero items.
- *Gap:* confirmation on a no-op is meaningless; an accidental confirm of "nothing" is a footgun.
- *Triage:* **Accept**. *Traceability:* `FR-09`, `S4`.
- *Resolution:* dry-run shows `0 affected items` and **disables confirmation**; no no-op handoff.

**UX-03 — Stale dry-run snapshot**
- *Path walked:* state changes between dry-run render and confirm (job completes, node uncordons).
- *Gap:* a confirm against a stale list proposes an outdated payload.
- *Triage:* **Accept**. *Traceability:* `FR-09`, `FR-10`, `S4`.
- *Resolution:* dry-run is a timestamped snapshot; at confirm the affected set is re-validated and a scope delta re-opens the dry-run for re-review.

**UX-04 — Compound query containing a destructive intent**
- *Path walked:* e.g., "why was X denied, and delete all CS201 jobs".
- *Gap:* `FR-01` allows decomposition or clarification; decomposition of destructive intent is unsafe and was unspecified.
- *Triage:* **Accept**. *Traceability:* `FR-01`, `FR-09`, `S4`.
- *Resolution:* any compound query with a destructive/mutating verb routes to clarification; never decomposed.

**UX-05 — Provider failure between dry-run and confirm; executor unavailable at dispatch**
- *Path walked:* LLM/provider outage at a stage that does not need the LLM; executor down at handoff.
- *Gap:* unspecified whether the procedural gate depends on the provider.
- *Triage:* **Accept**. *Traceability:* `FR-09`, `FR-10`, `FR-16`, `S4`, `S8`.
- *Resolution:* confirm gate is provider-independent (procedural); executor unavailability renders executor failure on the delegation card with the proposal preserved; re-dispatch is deliberate.

**UX-06 — Executor double-apply**
- *Path walked:* `FR-10` exactly-once invariant violated in the executor.
- *Gap:* UI needed a way to show a second applied record without implying two successes.
- *Triage:* **Accept**. *Traceability:* `FR-10`, `NFR-8`, `S4`.
- *Resolution:* delegation card renders the applied-mutation count; a second record surfaces as executor-failure, never as success.

**UX-07 — Open confirmation dialog + session switching**
- *Path walked:* operator navigates sessions (`[` / `]`) with the dialog open.
- *Gap:* a safety state could be abandoned silently.
- *Triage:* **Accept**. *Traceability:* `NFR-6`, `FR-09`.
- *Resolution:* open confirmation dialog blocks session/rail navigation until dismissed or confirmed.

**UX-08 — Session reset mid-flow**
- *Path walked:* reset while an answer or destructive flow is in flight.
- *Gap:* reset semantics vs. an in-progress safety state were unspecified.
- *Triage:* **Accept**. *Traceability:* `FR-02`, `FR-09`.
- *Resolution:* reset cancels in-flight requests; a destructive flow returns to its refusal/dry-run stage and never auto-continues.

**UX-09 — Audit redaction not explicit in the UI**
- *Path walked:* audit row rendering of parameters.
- *Gap:* `NFR-11` mandates no secrets; the row's parameter rendering needed an explicit contract.
- *Triage:* **Accept**. *Traceability:* `FR-11`, `NFR-11`, `S5`.
- *Resolution:* audit rows render tool name + parameter summary only — never credentials/tokens/secrets.

**UX-10 — Empty audit log**
- *Path walked:* fresh session, Audit tab.
- *Gap:* empty state unspecified for the audit surface.
- *Triage:* **Accept**. *Traceability:* `FR-11`.
- *Resolution:* `No tool calls in this session.`; paged, never infinite-scroll.

**UX-11 — Clock/time source failure (S2)**
- *Path walked:* `FR-05` clock resolves; clock source fails.
- *Gap:* fabricated window risk on a failed clock read.
- *Triage:* **Accept**. *Traceability:* `FR-05`, `FR-16`, `S2`, `S8`.
- *Resolution:* safe-failure — `Cannot confirm (insufficient evidence)` or provider-unavailable banner; a window is never fabricated.

**UX-12 — Citation that cannot resolve**
- *Path walked:* a citation fails to resolve at render time.
- *Gap:* a broken citation must not stand as evidence.
- *Triage:* **Accept**. *Traceability:* `FR-03`, `FR-13`, `NFR-3`.
- *Resolution:* broken citation never renders; the answer downgrades to `Cannot confirm (insufficient evidence)`.

**UX-13 — Retrieved content auto-linked / executable**
- *Path walked:* runbook text, policy text, job names, event reasons rendered as content.
- *Gap:* injection payloads must have no control effect (`FR-15`).
- *Triage:* **Accept**. *Traceability:* `FR-15`, `S7`, `C7`, `S1`–`S4`.
- *Resolution:* retrieved content rendered bounded, mono, un-styled, and never auto-linked or executable (`DESIGN.md` Do's/Don'ts).

**UX-14 — Runbook steps without approved-source metadata**
- *Path walked:* physical-intervention template lacking provenance.
- *Gap:* steps must not render as sanctioned if the source is not approved.
- *Triage:* **Accept**. *Traceability:* `FR-08`, `OQ-11`, `S4`, `S3`.
- *Resolution:* runbook renders unavailability, not the unvetted steps.

**UX-15 — Status dot without label in dense tables**
- *Path walked:* Inspector/Audit dense tables with `status-dot` only.
- *Gap:* violates never-color-alone.
- *Triage:* **Accept**. *Traceability:* user spec §5; WCAG 2.1 AA.
- *Resolution:* text label always present per status cell; a dot alone is not a valid rendering.

**UX-16 — Answer chain on degraded answers**
- *Path walked:* `Cannot confirm` / provider-unavailable / refusal answers.
- *Gap:* the chain could imply stages the system did not reach.
- *Triage:* **Accept**. *Traceability:* `FR-04`–`FR-06`, `FR-16`, `EC`.
- *Resolution:* only reached stages populate; the Diagnosis chip is emphasized only when established; refusal answers never show Proposal/Execution populated.

### Deferred (1)

**UX-17 — Entity typo tolerance**
- *Path walked:* a misspelled entity reference.
- *Gap:* v1 is exact-match (`FR-03`); the UI surfaces `Entity Not Found in State` for typos, which is correct but offers no suggestion.
- *Triage:* **Defer** — held pending `OQ-9` (entity match tolerance). The spine already renders the canonical response for v1; typo-suggestion UI lands when `OQ-9` resolves. *Traceability:* `FR-03`, `OQ-9`.

### Rejected (5) — boundary contradictions, flagged not expanded

**UX-18 — Direct cancellation/deletion control on the Inspector**
- *Requested behavior:* a "cancel job" / "delete job" button in the State Inspection Viewer.
- *Triage:* **Reject**. *Traceability:* `PRD §2.3`, `§2.4`, `§16`, `FR-09`, `S6`.
- *Finding:* this is a boundary contradiction. Module 12 explains and proposes only; job cancellation/deletion is delegated job-control. The Inspector is read-only (`FR-12`); cancellation appears solely as a delegated proposal through the Safety flow. No surface change was made.

**UX-19 — Module 12 as authoritative system of record for policy/state**
- *Requested behavior:* an in-console editor that writes policy or state.
- *Triage:* **Reject**. *Traceability:* `PRD §2.4`, `A-2`, `C-3`, `C-7`, `FR-15`.
- *Finding:* boundary contradiction. Module 12 is a read-only consumer; retrieved content is data. The Inspector renders field-for-field and marks stores `read-only`; no write path exists.

**UX-20 — Confirmation as identity/authorization**
- *Requested behavior:* the confirmation control implying or asserting administrative authority.
- *Triage:* **Reject**. *Traceability:* `A-13`, `C-8`, `FR-09`, `OQ-4`.
- *Finding:* boundary contradiction. The confirmation gate is a deliberate procedural safety boundary, not an authorization mechanism; real identity/authorization is delegated to the external administrative/access-control subsystem. The dialog caption is contractually non-authorizing.

**UX-21 — Reservation/lecture-machine availability management**
- *Requested behavior:* managing reservations or lecture-machine availability from the console.
- *Triage:* **Reject**. *Traceability:* `PRD §2.4`, `§16`, `S2`.
- *Finding:* boundary contradiction — reservation conflicts are diagnosed elsewhere. The Inspector reads reservation/policy-window records only.

**UX-22 — Node cordon/uncordon from the console**
- *Requested behavior:* an "uncordon" action button on the node Inspector or runbook.
- *Triage:* **Reject**. *Traceability:* `PRD §2.3`, `S3`.
- *Finding:* boundary contradiction. Cordon/uncordon and physical remediation are node-management's job; Module 12 produces the runbook and the delegated proposal, never the action.

## Pass 2 — edge-case review over the design-loop artifacts

- **Artifacts reviewed:** `C-UX-Scenarios/00-ux-scenarios.md`, `C-UX-Scenarios/01–04/…`, `wireframes/01-primary-operations-console.md`, `wireframes/02-safety-proposed-action.md`, `SPECIFICATIONS.md`, `VALIDATION.md`.
- **Method:** same edge-case-hunter discipline — every state, transition, and interaction in the new artifacts walked against the PRD FR/NFR and the Pass 1 resolutions.
- **Triage taxonomy unchanged:** **Accept** (handling folded into the artifacts) · **Defer** (held pending an open PRD question) · **Reject** (boundary contradiction — flagged, not expanded).
- **Traceability:** each finding cites the PRD requirement (`FR-n` / `NFR-n` / `S-n` / `C-n`) and scenario (`S1`–`S4`, `EC`, `PT`).

### Findings

**UX-23 — Runbook shown for a node that is cordoned with a *different* code than the query states**
- *Path walked:* node exists and is cordoned, but its recorded error code differs from the code in the query.
- *Gap:* the runbook could be keyed to a code the node does not actually report.
- *Triage:* **Accept**. *Traceability:* `FR-07`, `S3`.
- *Resolution:* scenario 03 requires the Copilot to **confirm** cordon + stated code against the node record before pulling the template; a mismatch surfaces the discrepancy (node record citation) and routes to `no runbook available for the recorded code` if unmatched — never an assumed match.

**UX-24 — Next-open-window rendered when the job has no scheduling constraint**
- *Path walked:* schedule inquiry on a job with no governing constraint.
- *Gap:* the Recommendation stage could render a fabricated window.
- *Triage:* **Accept**. *Traceability:* `FR-05`, `S2`.
- *Resolution:* scenario 02 + VALIDATION S2: **no constraint applies** is stated explicitly and **no window is rendered**; the Recommendation chip is not populated without a policy-derived value.

**UX-25 — Evidence strip visible on a degraded answer**
- *Path walked:* `Cannot confirm` / provider-unavailable answers on the Console.
- *Gap:* the Evidence stage could render partial/stale records that imply a diagnosis.
- *Triage:* **Accept**. *Traceability:* `FR-04`–`FR-06`, `FR-16`, `EC`.
- *Resolution:* SPECIFICATIONS S-A + wireframe 01 §3: degraded answers render the canonical response, not a populated Evidence/Diagnosis; only reached stages populate (Pass 1 UX-16 held).

**UX-26 — Confirmation button momentarily enabled during stale-snapshot re-validation**
- *Path walked:* scope delta detected between dry-run render and confirm click.
- *Gap:* a user could confirm before re-validation completes.
- *Triage:* **Accept**. *Traceability:* `FR-09`, `FR-10`, `S4`.
- *Resolution:* wireframe 02 + SPECIFICATIONS S-D: the dialog closes back to a re-rendered dry-run with the delta surfaced; the confirm button is **disabled** while re-validation is pending (state added to Component states).

**UX-27 — Empty/error copy on the Safety surface read as celebratory or exculpatory**
- *Path walked:* `0 affected items`, executor failure, double-apply copy.
- *Gap:* tone could understate a safety boundary.
- *Triage:* **Accept**. *Traceability:* `FR-09`, `FR-10`, `NFR-8`, `S4`.
- *Resolution:* Voice & Tone rules apply on S-D verbatim: no exclamation, no encouragement; `0 affected items` disables confirmation; executor failure copy is explicit, not apologetic.

**UX-28 — Keyboard trap risk in the confirmation dialog**
- *Path walked:* modal `alertdialog` focus handling.
- *Gap:* focus must stay within the dialog and restore on close.
- *Triage:* **Accept**. *Traceability:* `C-8`, `FR-09`, WCAG 2.1 AA.
- *Resolution:* SPECIFICATIONS S-D Accessibility: full keyboard operation, focus containment, focus restored to the dry-run trigger on close, confirm never auto-focused.

**UX-29 — Audit page count vs. retention cap mismatch**
- *Path walked:* paged audit log at the retention cap.
- *Gap:* the pager could imply more history than the cap retains.
- *Triage:* **Accept**. *Traceability:* `FR-11`, `NFR-11`, `OQ-12`.
- *Resolution:* SPECIFICATIONS S-C: paging honors the retention cap; rotation of oldest entries is reflected in display; the `read-only` marker and row count make the bounded window explicit.

**UX-30 — Inspector "open in Inspector ↗" affordance on a citation whose record is ephemeral**
- *Path walked:* citation card linking to a record that no longer resolves.
- *Gap:* an unresolvable source could present a dead affordance.
- *Triage:* **Accept**. *Traceability:* `FR-03`, `FR-13`, `NFR-3`.
- *Resolution:* held from Pass 1 UX-12: a broken citation never renders; the answer downgrades. The affordance only ever exists on a resolvable record, so no dead link renders.

### Summary (Pass 2)

8 findings, all **Accepted** and folded into the scenario outlines, wireframes, SPECIFICATIONS, and VALIDATION — no deferrals added, no new boundary contradictions (the 5 Pass 1 Rejects UX-18–UX-22 remain correctly rejected and are re-asserted in VALIDATION). The design-loop artifacts stay within Module 12's read-only, propose-only contract.

## Summary

16 gaps found and closed in the spines (all mapped to PRD requirements), 1 deferred on an open question, 5 boundary contradictions flagged and rejected without scope expansion. The spine pair remains within Module 12's read-only, propose-only contract. **Pass 2** over the design-loop artifacts added 8 accepted findings (UX-23–UX-30), all folded into the new artifacts; the same 5 boundary contradictions remain rejected and unexpanded.