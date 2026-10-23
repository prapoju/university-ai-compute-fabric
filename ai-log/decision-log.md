# AI Decision Log — Module 12: AI Operations Copilot

### Purpose

This log records significant decisions made during the specification of Module 12: AI Operations Copilot. It captures the alternatives considered, the selected direction, the rationale, and consequences for the system specification.

The log is intended to preserve decision traceability during AI-assisted development. Decisions recorded here are V1 specification decisions and may be revisited if later stakeholder clarification, system constraints, or adversarial review provide evidence that they should change.

**Coverage:** D1–D6 are Phase 1 (scope & boundary) decisions confirmed by the user on 2026-09-27; D7 begins Phase 2 (draft refinement); D8–D15 are the significant decisions from the 2026-09-27 adversarial review of the PRD (triage in `review-prd-adversarial.md`); D16–D22 are the accepted triages from the 2026-09-28 adversarial review of the Phase 2 UX artifacts (triage in `review-ux-adversarial.md`); D23 (2026-09-28) resolves PD-6 (re-dispatch = new proposal); D24–D30 (2026-09-28) resolve the remaining Phase 2 judgment calls (PD-1/2/3/5/7/8/9); D31–D49 (2026-09-28) resolve the architecture-phase edge-case guards (PD-10–PD-28); D50–D51 (2026-09-28) resolve the last decidable open questions (OQ-12 retention values, OQ-13 session lifetime). **All decidable items (PD-1–PD-28, OQ-2/5/6/9/12/13) are now decided — the log has no open decisions.** The remaining PRD open questions (OQ-1/3/4/7/8/10/11) are explicitly deferred to external input or out of V1 scope in the Deferred register.

**Oversight model:** Every entry records a human judgment. AI-generated recommendations were triaged against the project's **Accept / Defer / Reject** taxonomy: accepted findings are recorded here and fixed in the artifacts; deferred items were tracked as PDs and are now **all resolved** as decided entries (D24–D51 — no open decisions remain; OQ-1/3/4/7/8/10/11 are explicitly deferred to external input or out of V1 scope); **rejected AI recommendations are documented with their technical reasoning in [AI Recommendations Rejected by Human Judgment](#ai-recommendations-rejected-by-human-judgment)** below. Each entry carries a `Provenance` line naming the human decision. This log is the evidence that human judgment guided every specification step (AI Governance & Decision Log criterion).

---

## D1 — Boundary Basis Without Full Annex

**Provenance:** Human judgment (Julio), confirmed 2026-09-27. AI-proposed alternative to *block scope* until the Annex is supplied was **rejected** (would have stalled the whole module).

**Decision:**
Proceed without the full Annex module list. Bound Module 12 defensively as a read-only intelligence layer over the operational estate: it explains, diagnoses, retrieves evidence, and recommends runbooks; every mutation domain (authorization enforcement, reservations, quotas, scheduling, node state, job control) is assumed to be owned by another module.

**Context:**
The available project materials contain the university project brief and the Module 12 profile, but the complete list of neighboring modules is not currently available.

**Alternatives considered:**
- Block scope work until the Annex is provided — rejected: stalled the whole module.
- Draft boundaries optimistically with invented neighbor responsibilities — rejected: risk of over-claiming behavior that belongs to other modules.

**Selected:**
Proceed with the available materials and bound Module 12 defensively.

**Rationale:**
The Module 12 profile itself pins the Copilot's behavior as explanation/diagnosis/retrieval/runbooks with refusal of destructive execution, which makes read-only the defensible default.

**Consequence:**
Boundary claims in this PRD are marked `[ASSUMPTION: validate against Annex]` and must be re-checked when the Annex is available. Later modules may reveal overlaps; each must be reconciled.

**Assumptions / Open questions:**
- OQ-1: The full module list is expected later from the course materials; until then, neighbor boundaries are assumed.
- If a future Annex shows another module already owns "operations diagnostics," the read/consume contract (not the console) is what overlaps and must be reconciled.

**Status:** Accepted for V1 (assumption to validate against the full Annex).

---

## D2 — Ownership of Simulated State & Policy Providers

**Provenance:** Human judgment (Julio), confirmed 2026-09-27. The read-only-consumer direction was selected and confirmed over the AI-proposed alternatives.

**Decision:**
Module 12 owns the mock state/policy providers for the standalone prototype (users, roles, model catalog + access policy, groups, jobs/queue, nodes + cordon/error codes, reservations, policy windows, event log), but accesses them exclusively through defined read-only interfaces/contracts. Module 12 is never the authoritative system of record.

**Alternatives considered:**
- Outsource all fixtures to other modules' simulated APIs — rejected: violates the standalone-prototype requirement (the console must run in isolation) and creates cross-module build coupling.
- Let the Copilot write directly to the mocked stores — rejected: conflates the Copilot with the systems of record and erases the boundary D3 depends on.

**Selected:**
Own the mock providers for the prototype while defining read-only contracts for future integration.

**Rationale:**
"Queries simulated system state and institutional policy files" (profile) implies Module 12 is a consumer. Owning the mocks keeps the prototype standalone; the interface contract keeps the later swap to real subsystems clean.

**Consequence:**
The read contract (entity queries + policy retrieval) becomes a first-class interface in the design; the copilot's code path must not bypass it. A write path must never exist for the copilot.

**Assumptions / Open questions:**
- OQ-3: Whether the read contract becomes a real shared API in the full system or stays per-module remains an architecture-phase decision.

**Status:** Accepted for V1.

---

## D3 — Action Model: Propose-Only

**Provenance:** Human judgment (Julio), confirmed 2026-09-27. AI-proposed option (b) — Copilot performs the mutation itself after confirmation + dry-run — was **rejected**; propose-only confirmed.

**Decision:**
Module 12 uses a **propose-only** action model. The Copilot is strictly propose-only: it never directly performs mutations. On a destructive intent, after explicit administrative confirmation and dry-run, it produces and logs the proposed action and delegates execution to a simulated/external executor.

**Context:**
The mandatory safety scenario requires the Copilot to handle a request such as "Delete all pending jobs for CS201."

**Alternatives considered:**
- Allow the Copilot to perform the mutation itself in the prototype after confirmation + dry-run — rejected: models the agent as an actor, contradicts the "refuses direct destructive execution" guardrail, and makes the prototype unsafe to demo.
- Propose-only, execution delegated to the job-control subsystem — selected.

**Selected:**
Propose-only: the Copilot never mutates operational state; execution belongs to a delegated/simulated executor.

**Rationale:**
Scenario 4's guardrail is about the Copilot's *refusal* and *due process* (dry-run + confirmation), not about the Copilot becoming an executor. Delegation preserves the module boundary and makes the safety property (zero copilot-originated mutations) trivially testable.

**Consequence:**
A propose-only handoff contract is required (now **FR-10**; was FR-11 before the D8 renumbering); the executor is simulated in the prototype. The prototype must demonstrate the distinction between user request, safety refusal, dry-run, explicit administrative confirmation, proposed action, and delegated execution. The safety metric "zero direct mutations by the copilot" is enforceable and measurable.

**Assumptions / Open questions:**
- OQ-4: Admin confirmation semantics — who is "administrator," how identity/role is signaled in the prototype (no auth system yet) — resolved for V1 by D9 as a procedural gate; only full-system admin auth remains open.

**Status:** Accepted for V1.

---

## D4 — Determinism Semantics (Evidence-Level)

**Provenance:** Human judgment (Julio), confirmed 2026-09-27. AI-proposed 'no determinism guarantee' was **rejected**; evidence-level determinism confirmed.

**Decision:**
Determinism = evidence-level reproducibility. Given the same query, state snapshot, policy sources, and relevant configuration, the Copilot must produce the same evidence set, same citations, same diagnosis classification, and same runbook steps. Exact prose need not be byte-identical.

**Alternatives considered:**
- Byte-identical prose — rejected: infeasible for any LLM-composed output and not what users or auditors need.
- No determinism guarantee — rejected: would fail the profile's explicit "deterministic diagnostic explanations" and gut auditability.

**Selected:**
Evidence-level determinism.

**Rationale:**
The consumers of determinism are audit (same inputs → same evidence and reasoning) and debugging (reproducible behavior). Evidence/citation/classification identity delivers that without a brittle prose constraint.

**Consequence:**
Retrieval + composition must be enforced at the pipeline level (deterministic retrieval, citation pinning), with the LLM constrained to prose generation over a fixed evidence payload. This becomes a hard architectural constraint (C-2).

**Assumptions / Open questions:**
- OQ-5: Mechanism — constrained decoding vs. retrieval-composition vs. template fill — is an architecture-phase decision; the PRD only pins the acceptance bar (PD-1).

**Status:** Accepted for V1.

---

## D5 — Minimal Simulated Event Log for Retrospective Diagnosis

**Provenance:** Human judgment (Julio), confirmed 2026-09-27. AI-proposed full observability subsystem was **rejected** as out of scope; minimal event log confirmed.

**Decision:**
Include a minimal simulated event log covering access denials, job cancellations, and node cordons, so the Copilot can answer retrospective questions ("Why was my job cancelled?"). The event model is limited to what the scenarios require — it is not a general observability system.

**Context:**
Helpdesk questions may concern events that have already occurred, such as job cancellations or previous access denials.

**Alternatives considered:**
- Point-in-time only (current snapshot + rule evaluation) — rejected: "Why was <X> denied/cancelled?" is inherently retrospective; current-state replay cannot explain an event that already happened.
- General observability/timeseries subsystem — rejected: out of scope, adds a module-sized concern the scenarios don't need.

**Selected:**
Include a minimal simulated event log.

**Rationale:**
Diagnosis of a complaint is retrospective by nature; a minimal event log is the smallest construct that supports it without creating an observability platform.

**Consequence:**
The simulated event log is part of the state model (with a defined schema: event type, entity refs, timestamp, outcome, policy version). Entity-Not-Found extends to events (a complaint about a denial that has no event → cannot confirm → explicit unknown, not fabrication). The Copilot must distinguish historical evidence from current state when generating explanations.

**Assumptions / Open questions:**
- OQ-6: Whether denials must replay the *policy version at the time of the event* vs. record the reason on the event itself — the cheap and sufficient choice for the prototype is to record the reason on the event (PD-2). Confirm at fixture-authoring time.

**Status:** Accepted for V1.

---

## D6 — Scenario-Driven State Model

**Provenance:** Human judgment (Julio), confirmed 2026-09-27. AI-proposed broad operational state model was **rejected**; scenario-driven minimum confirmed.

**Decision:**
The simulated state model covers only the entities required by the four mandatory scenarios + mandatory edge case: users/roles, model catalog + access policy, nodes (cordon + error codes), jobs/queue, groups, reservations, policy windows + clock, and the event log (D5). The model stays extensible; unrelated operational entities are deferred.

**Alternatives considered:**
- Broad operational state model now — rejected: speculative entities add fixture and NFR surface the scenarios never exercise.
- Bare minimum with no extension path — rejected: would force rework the moment an evaluator probes a near-miss scenario.

**Selected:**
Use the minimal scenario-driven model with a documented extension path.

**Rationale:**
The profile's own scenario list defines the exercised surface. Extensibility is preserved by the read-contract design (D2) and a documented entity-extension path, not by pre-building entities.

**Consequence:**
Each FR's test fixtures are bound to this entity set. Adding an entity later requires a contract extension, not a redesign — the PRD documents that path (constraint C-4).

**Assumptions / Open questions:**
- OQ-7: Reserved model entities (e.g., quota limits, fair-share weights) are recognized as likely later additions; none are built in Phase 1.

**Status:** Accepted for V1.

---

## D7 — Protagonist Naming and Persona Cast

**Provenance:** Human judgment (Julio), confirmed 2026-09-27 (draft refinement). AI-proposed rename to Elena and the Elena/Nadia bridge were **rejected**; module-profile authority upheld.

**Decision:**
Keep the module-profile protagonist **Nadia** as the primary operator and only direct console user. Add named secondary protagonists to satisfy the course rubric's "no generic user" requirement: **Dr. Aris Thorne** (NLP Professor, CS101) and **Mateo** (Undergraduate Student), both subjects of the journeys but explicitly non-users of the console.

**Alternatives considered:**
- Rename Nadia to Elena to match the course-wide ops archetype — rejected: the Module 12 profile explicitly names Nadia; the module spec is authoritative for this module.
- Bridge both names (Elena/Nadia alias) — rejected: creates a naming split inside the module for no benefit.
- Keep Nadia only, no secondary cast — rejected: fails the rubric's named-protagonist requirement.

**Selected:**
Keep Nadia as primary operator; add Dr. Aris Thorne and Mateo as named non-user journey subjects.

**Rationale:**
The module profile is the authoritative source for Module 12's protagonist; the course rubric is satisfied by naming the people whose complaints drive the journeys, without making them console users (which would violate the §2.4 boundary).

**Consequence:**
§3 now names Nadia (primary, UJ-1–UJ-4), Dr. Aris Thorne (context for UJ-1/2 only — see D8 errata), Mateo (subject of UJ-1), and the Copilot (system protagonist). Non-users remain students/teachers at large, academic administration, and privileged researchers.

**Assumptions / Open questions:**
- Secondary protagonists are journey subjects, not console users; if a later module makes students direct users, this boundary must be revisited.

**Status:** Accepted for V1.

---

## D8 — Sequential FR Renumbering and New Capability FRs

**Provenance:** Human triage (Julio), 2026-09-27 — adversarial finding 5 **Accepted**; renumbering executed.

**Decision:**
Renumber all FRs sequentially in document order (now FR-01–FR-16). The event-log retrospective diagnosis moves from FR-13 to FR-06 (out-of-order numbering removed). Two new FRs are added to realize review findings: **FR-02** (minimal session & conversation context) and **FR-15/FR-16** (content data-hygiene, safe failure — see D11/D12).

**Alternatives considered:**
- Leave the out-of-order numbering — rejected: eroded the traceability the PRD leans on.
- Split the PRD into multiple feature docs — rejected: overkill for a module spec.

**Selected:**
Sequential renumbering in document order.

**Rationale:**
Sequential numbering in document order makes the traceability matrix and NFR cross-references auditable.

**Consequence:**
All cross-references (NFRs, success metrics, traceability matrix, decision log) updated to the final numbering. **Errata:** earlier entries reference the pre-renumbering draft — D3's "FR-11" (propose-only handoff) is now **FR-10**; D7's "UJ-1/2/4" for Dr. Aris Thorne is now **UJ-1/2** only (corrected in PRD §3; review Finding 2); PD-1's "FR-12" is now **FR-14**; PD-3's "FR-02" is now **FR-03**.

**Status:** Accepted for V1 (adversarial review, 2026-09-27).

---

## D9 — Confirmation Gate Is Procedural, Not Authentication

**Provenance:** Human triage (Julio), 2026-09-27 — adversarial finding 10 **Accepted**; procedural-gate semantics confirmed.

**Decision:**
In V1, the destructive-action confirmation gate is a deliberate **procedural** safety boundary, not an authentication/authorization mechanism. Real administrator identity and authorization are delegated to an external administrative/access-control subsystem and mocked in the prototype. The Copilot never infers administrative authority from the UI session.

**Alternatives considered:**
- Build a full auth/role system in V1 — rejected: a subsystem-sized concern the four scenarios do not exercise.
- Present the single-operator confirm click as authorization — rejected: dishonest and unverifiable.

**Selected:**
Procedural confirmation gate with mocked external authorization.

**Rationale:**
A single-operator prototype with a UI confirm button cannot claim an authorization boundary; naming it a procedural gate keeps the safety property honest and testable.

**Consequence:**
Resolves OQ-4/PD-4 for V1. FR-09, A-13, C-8, and the glossary ("Confirmation gate (procedural)") updated.

**Assumptions / Open questions:**
Full-system administrator authentication/authorization remains open (OQ-4).

**Status:** Accepted for V1 (adversarial review, 2026-09-27).

---

## D10 — Compound-Intent Decomposition and Minimal Session Semantics

**Provenance:** Human triage (Julio), 2026-09-27 — adversarial findings 11 & 12 **Accepted**.

**Decision:**
Support compound queries by decomposing them into independently validated sub-queries, or ask the operator to clarify when decomposition is unsafe or ambiguous — never silently truncate to a single intent. Add minimal per-session conversational context: session creation, context retention, follow-up entity references, and reset/clear, bounded to the prototype's operational scope.

**Alternatives considered:**
- Single-intent routing only — rejected: silently loses operator intent on real conversational input.
- General conversational memory — rejected: a module-sized concern the scenarios don't need.

**Selected:**
Compound-intent decomposition + minimal session context.

**Rationale:**
The console is conversational; compound queries and follow-up references are natural operator behavior (Findings 11 & 12).

**Consequence:**
FR-01 extended with multi-intent handling; FR-02 added; V1 intent taxonomy added (§7.1.1); traceability rows updated.

**Assumptions / Open questions:**
OQ-13 — session retention window / context lifetime left to prototype detail.

**Status:** Accepted for V1 (adversarial review, 2026-09-27).

---

## D11 — V1 Threat Model and Content Data-Hygiene

**Provenance:** Human triage (Julio), 2026-09-27 — adversarial finding 9 **Accepted**; threat model adopted.

**Decision:**
Adopt a V1 threat model covering (a) accidental operator input and (b) malicious/crafted content arriving through query text or retrieved records (names, descriptions, policy text, event reasons, runbook text). Treat all query text and retrieved content as **data, never as control instructions**; the Copilot's control flow comes only from registered intent handlers and configuration.

**Alternatives considered:**
- No explicit threat model — rejected: an agentic LLM that renders retrieved content needs an explicit data boundary.
- Treat retrieved content as trusted — rejected: prompt-injection risk via state fields.

**Selected:**
Explicit content-hygiene data boundary.

**Rationale:**
For an LLM system that retrieves and renders state, content-injection is the material unaddressed risk (Finding 9).

**Consequence:**
New §7.8 (Threat Model & Content Hygiene) and FR-15; constraints C-7, safety rule S-7, assumption A-16 added; injection-corpus test required.

**Assumptions / Open questions:**
Out of scope for V1: adversarial model weights, LLM supply-chain compromise, and denial-of-service against the console.

**Status:** Accepted for V1 (adversarial review, 2026-09-27).

---

## D12 — Safe Failure on Degraded Dependencies

**Provenance:** Human triage (Julio), 2026-09-27 — adversarial finding 19 **Accepted**; safe-failure modes defined.

**Decision:**
Define explicit degraded behavior for LLM runtime timeout, state-provider failure, policy-source failure, malformed input, and unavailable delegated executor: fail safely with an explicit cannot-answer response and zero invented detail.

**Alternatives considered:**
- Assume dependencies never fail — rejected: NFR-7 already promises availability; failure behavior must be specified.

**Selected:**
Explicit safe-failure modes for each failure class.

**Rationale:**
The PRD asserted robustness without any failure-mode design (Finding 19).

**Consequence:**
New §7.9 (Resilience & Safe Failure) and FR-16; NFR-7 and safety rule S-8 updated; fault-injection tests for each failure class.

**Status:** Accepted for V1 (adversarial review, 2026-09-27).

---

## D13 — Anti-Fabrication Bounded; Canonical Response Categories

**Provenance:** Human triage (Julio), 2026-09-27 — adversarial findings 8 & 16 **Accepted**; canonical responses adopted.

**Decision:**
Replace the unbounded "0 fabricated across the entire test corpus" claim with a requirement bounded to the **defined simulated state and evaluation corpus**. Canonicalize two response categories: **"Entity Not Found in State"** when an explicitly referenced entity is absent, and **"Cannot confirm (insufficient evidence)"** when the entity exists but the evidence cannot establish the diagnosis.

**Alternatives considered:**
- Keep the unbounded negative claim — rejected: unmeasurable over an open-ended LLM output space.
- Collapse both responses into one — rejected: conflates "no record" with "not enough evidence," which operators must distinguish.

**Selected:**
Bounded anti-fabrication claim + two canonical response categories.

**Rationale:**
Findings 8 & 16; the mandatory edge case must return "Entity Not Found in State" for absent references.

**Consequence:**
NFR-2, FR-03–FR-06, glossary, and safety rule S-2 updated to the two canonical responses.

**Status:** Accepted for V1 (adversarial review, 2026-09-27).

---

## D14 — Runbook Provenance; Module 12 Is Not a Safety Certifier

**Provenance:** Human triage (Julio), 2026-09-27 — adversarial finding 18 **Accepted**; provenance contract adopted.

**Decision:**
Module 12 consumes approved, versioned runbook templates and does not authoritatively certify physical-safety procedures. Runbooks requiring physical intervention must originate from an approved institutional source; every template carries provenance and version metadata.

**Alternatives considered:**
- Let the Copilot compose remediation steps from general knowledge — rejected: already prohibited, but provenance was unspecified.
- Module 12 self-certifies physical-safety content — rejected: out of scope and irresponsible for physical interventions.

**Selected:**
Consume approved, versioned runbook templates only.

**Rationale:**
The PRD shipped "safety warnings" for physical steps without allocating who owns/approves that content (Finding 18).

**Consequence:**
FR-07/FR-08 updated (provenance + version, approved-source rule); DP-2 updated; OQ-11 records the institutional content owner as an open question.

**Assumptions / Open questions:**
OQ-11 — who approves and certifies physical-intervention runbook content institutionally.

**Status:** Accepted for V1 (adversarial review, 2026-09-27).

---

## D15 — Prototype Audit-Log Retention and Redaction Rules

**Provenance:** Human triage (Julio), 2026-09-27 — adversarial findings 21 & 14 **Accepted**; audit rules defined.

**Decision:**
Define concrete prototype logging rules: entries carry operator id (synthetic role id), session id, tool metadata, and query-derived entity ids only — no credentials, tokens, or secrets; the log is capped at a defined size with rotation of the oldest entries; no PII beyond simulated-state identifiers. The audit log distinguishes the Copilot's proposal from the executor-applied mutation.

**Alternatives considered:**
- Unlimited immutable retention — rejected: unbounded and unnecessary for a prototype; contradicts a finite evaluation window.
- Single undifferentiated log — rejected: cannot attribute a mutation to its actor (copilot vs. executor).

**Selected:**
Capped, rotating, actor-differentiating audit log.

**Rationale:**
Findings 21 & 14 — the prior "no PII beyond the simulated state" clause was tautological and the executor's mutation path was ambiguous.

**Consequence:**
FR-11, NFR-11, DP-7 updated; OQ-12 leaves exact cap/rotation values to prototype detail; FR-10 defines the post-gate executor application and separate logging.

**Assumptions / Open questions:**
OQ-12 — exact retention/size cap values for the prototype log.

**Status:** Accepted for V1 (adversarial review, 2026-09-27).

---

## D16 — Composer Character-Counter Semantics (UX adversarial finding 1)

**Provenance:** Human triage (Julio), 2026-09-28 — UX adversarial finding 1 **Accepted**.

**Decision:**
Fix the composer counter so it can never display a value above the enforced 1,000-char limit. The `1180/1000` example in `DESIGN.md:318` and `wireframes/01` is impossible under `FR-01` (queries capped at ≤ 1,000 chars) and misstates the counter's job. The counter reads *characters used out of the cap* (e.g., `180/1000`), never a value exceeding the cap; an over-limit paste is blocked and surfaced as a clarification/validation state, not rendered as a counter value.

**Alternatives considered:**
- Keep the example as-is and treat it as illustrative — rejected: it contradicts the exact cap `FR-01` enforces and the example is load-bearing in the spec.
- Define the counter as "remaining characters" — rejected: "remaining" cannot exceed the cap either; "used/limit" is the unambiguous reading and matches the mono countdown intent.

**Selected:**
Counter reads used/limit (e.g., `180/1000`); over-limit paste is blocked and surfaced as a validation/clarification state.

**Rationale:**
A counter that shows 1180 against a 1000-char cap is a contradiction an evaluator would flag immediately; it also weakens the "protects the 1,000-char limit" claim.

**Consequence:**
Update `DESIGN.md:318` and `wireframes/01` to a valid used/limit example; keep the over-limit behavior in the composer validation path (`FR-01`).

**Status:** Accepted for V1 (UX adversarial review, 2026-09-28).

---

## D17 — Destructive-Flow Surface Ownership (UX adversarial finding 2)

**Provenance:** Human triage (Julio), 2026-09-28 — UX adversarial finding 2 **Accepted**; surface ownership reconciled.

**Decision:**
Reconcile the two spines: the destructive **flow** (refusal banner, dry-run panel, delegation card) lives inline on the Console thread, and the **confirmation dialog** is the distinct Safety/Confirmation surface (modal `alertdialog`). `EXPERIENCE.md:33` is corrected from "never lives on the Console surface itself" to "the confirmation dialog is a distinct surface; the surrounding safety flow renders inline in the console thread."

**Alternatives considered:**
- Keep the literal IA rule (entire destructive flow moves off the Console) — rejected: contradicts `SPECIFICATIONS.md S-D` and `Wireframe 02`, which deliberately render refusal/dry-run/delegation in the thread for scope visibility.
- Silent rewording to "never lives on the Console surface alone" — rejected: the wording was already changed without a recorded decision; this entry records it.

**Selected:**
Destructive flow inline in the console thread; only the modal confirmation is a distinct surface.

**Rationale:**
The operator must see the dry-run and refusal *in context* of the conversation; only the modal confirmation is a separate surface. The IA statement was over-strict and contradicted the flow artifacts.

**Consequence:**
`EXPERIENCE.md:33` updated; `Wireframe 02` and `SPECIFICATIONS.md S-D` remain the operative rendering. No scope change — Module 12 still never executes; the confirmation dialog stays procedural (`D9`).

**Status:** Accepted for V1 (UX adversarial review, 2026-09-28).

---

## D18 — Muted-Text and Reserved-Status Color Contrast (UX adversarial finding 4)

**Provenance:** Human triage (Julio), 2026-09-28 — UX adversarial finding 4 **Accepted**; contrast fix mandated.

**Decision:**
Fix the color tokens that fail WCAG 2.1 AA: `ink-muted #9CA3AF` on `surface-base #F4F6F8` (≈2.3:1), `ink-muted-dark #6B7280` on `surface-base-dark #0B1220` (≈4.0:1, ≈3.5:1 on raised-dark), and `status-reserved #A16207` on `surface-status #F1F5F9` (≈4.2:1). All fail the 4.5:1 threshold for text. Either darken the tokens or constrain `ink-muted` to non-text de-emphasis with the 4.5:1 contrast verified before release.

**Alternatives considered:**
- Claim AA compliance while keeping the tokens — rejected: the accessibility floor says "status contrast verified," which the computed ratios contradict.
- Drop the muted color entirely — rejected: `ink-muted` is used for placeholders and de-emphasis; a darker token preserves the hierarchy.

**Selected:**
Darken the failing tokens (or constrain `ink-muted` to non-text de-emphasis), with contrast ratios verified before release.

**Rationale:**
The accessibility claim in `EXPERIENCE.md` Accessibility Floor is not supported by the token set; a real contrast failure on a data-dense console is a material defect, not a nicety.

**Consequence:**
Recompute and adjust `ink-muted`/`ink-muted-dark`/`status-reserved` (light + dark) tokens in `DESIGN.md`; add the contrast-ratio values to the token table so "verified" is checkable.

**Status:** Accepted for V1 (UX adversarial review, 2026-09-28).

---

## D19 — Entity-Not-Found Coverage for Policy References (UX adversarial finding 5)

**Provenance:** Human triage (Julio), 2026-09-28 — UX adversarial finding 5 **Accepted**; EC variant added.

**Decision:**
Add explicit UI-state coverage for the mandatory EC variant the artifacts missed: a user referencing a **non-existent policy** renders the canonical `Entity Not Found in State` card naming the unresolved policy, exactly as `FR-03` requires ("policy" is a resolvable entity). This completes the EC trio (imaginary user ✓ in S1, never-occurred event ✓ via `FR-06`, non-existent policy — now ✓).

**Alternatives considered:**
- Rely on `FR-03` prose and leave the UX implicit — rejected: the mandatory edge case must be demonstrable in the console, and the review found only two of three variants rendered.

**Selected:**
Add the non-existent-policy Entity-Not-Found variant to the console and to validation.

**Rationale:**
The EC is the assignment-mandated anti-fabrication showcase; partial coverage weakens `NFR-2` demonstration.

**Consequence:**
Add a policy-reference variant to scenario 01's Entity-Not-Found state and to `VALIDATION.md` S1/EC rows.

**Status:** Accepted for V1 (UX adversarial review, 2026-09-28).

---

## D20 — UX Validation Self-Report Credibility (UX adversarial finding 8)

**Provenance:** Human triage (Julio), 2026-09-28 — UX adversarial finding 8 **Accepted**; re-validation mandated.

**Decision:**
Treat the prior `VALIDATION.md` conclusion ("❌ Failures: 0") as **not credible** and re-run validation after D16–D22 are applied. The zero-failure result was produced by a checklist that did not detect the counter contradiction (D16), the surface-location contradiction (D17), or the re-dispatch/`FR-10` conflict (PD-6).

**Alternatives considered:**
- Keep the "0 failures" report — rejected: it is contradicted by real defects in the same artifact set and would mislead the evaluator.
- Delete the validation doc — rejected: re-running with a defect-hunting pass is more useful than removing it.

**Selected:**
Re-run validation with a cross-artifact contradiction sweep.

**Rationale:**
A self-validation that returns 0 failures while known contradictions exist has no evidentiary value; the re-run must explicitly hunt for cross-artifact contradictions, not just state coverage.

**Consequence:**
Re-run `VALIDATION.md` after the D-series fixes; add a cross-artifact contradiction sweep to its method.

**Status:** Accepted for V1 (UX adversarial review, 2026-09-28).

---

## D21 — Scenario Step-Folder Structure (UX adversarial finding 9)

**Provenance:** Human triage (Julio), 2026-09-28 — UX adversarial finding 9 **Accepted**; dead references must be resolved.

**Decision:**
Resolve the broken WDS tree: scenario outlines declare per-step folders (`01-console/`, `02-inspector/`, `02-dry-run/`, `03-confirmation/`, `04-delegation/`) that were never created because specs were consolidated into `SPECIFICATIONS.md`. Either create the per-step page-spec files (WDS convention) or remove the step tables and reference `SPECIFICATIONS.md` explicitly.

**Alternatives considered:**
- Leave the dangling step tables — rejected: broken structural references undermine the deliverable tree and WDS validation.
- Create the page-spec files — preferred for WDS convention compliance, but requires content duplication.

**Selected:**
Reference `SPECIFICATIONS.md` explicitly — the step tables now point to the governing surface section (`§S-A` Console, `§S-B` State Inspection, `§S-D` Safety/Confirmation) instead of non-existent page-spec folders. Chosen over materializing per-step page-spec files because the behavior is already consolidated in `SPECIFICATIONS.md`; creating duplicate page-specs would duplicate content for no added information.

**Rationale:**
The scenario outlines promise files that do not exist; the deliverable must not contain dead references. `SPECIFICATIONS.md` already specifies every step's behavior per surface, so a direct reference removes the dead links without content duplication.

**Consequence:**
Applied 2026-09-28: scenario outlines 01–04 step tables reference `SPECIFICATIONS.md` surfaces (D21 resolved); the dead `01-console/`, `02-inspector/`, `02-dry-run/`, `03-confirmation/`, `04-delegation/` folders are gone from the tree. No page-spec files were created.

**Status:** Resolved — applied to scenario outlines 01–04 on 2026-09-28.

---

## D22 — Answer-Chain Stage Label (UX adversarial finding 10)

**Provenance:** Human triage (Julio), 2026-09-28 — UX adversarial finding 10 **Accepted**; label standardized.

**Decision:**
Standardize the first answer-chain stage to `Observation` everywhere. `Wireframe 01` renders `OBSERVED`, contradicting `DESIGN.md`/`EXPERIENCE.md`, which are the contractual visual reference ("spines win on conflict").

**Alternatives considered:**
- Accept both spellings — rejected: the label is a fixed six-stage contract; inconsistency undermines the "never skipped, never reordered" rule.

**Selected:**
Standardize on `Observation`.

**Rationale:**
Trivial but load-bearing: the answer chain is the single visual contract that makes the six-stage distinction explicit on every answer.

**Consequence:**
`Wireframe 01` label corrected to `Observation`.

**Status:** Accepted for V1 (UX adversarial review, 2026-09-28).

---

## D23 — Re-dispatch Is a New Proposal, Not a Second Dispatch (PD-6)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-6 resolved.

**Decision:**
A `Re-dispatch proposal` action (executor failure) creates a **new proposal** that re-enters the full confirmation gate — fresh dry-run + explicit confirmation — and is logged as a separate proposal with a `supersedes_proposal_id` linkage to the failed parent. It is never a second dispatch of the same confirmed proposal. This preserves FR-10's exactly-once invariant: each confirmed proposal produces exactly one dispatch and exactly one executor-applied mutation.

**Context:**
`SPECIFICATIONS.md:327` exposed a `Re-dispatch proposal` action on executor failure. FR-10 requires "exactly one executor call" and its measurable condition states "each confirmed action produces exactly one dispatch, exactly one executor-applied mutation after confirmation (100%)". Read as a second executor call for the same confirmed proposal, re-dispatch violates the metric; UX-06's double-apply guard is also undermined (UX adversarial finding 3).

**Alternatives considered:**
- Second dispatch of the same confirmed proposal — rejected: violates FR-10's exactly-once metric, makes the metric unenforceable, and undermines the double-apply guard.
- Re-dispatch as a new proposal through the full gate — selected.

**Selected:**
Re-dispatch = a new proposal requiring a fresh dry-run + confirmation, logged separately with `supersedes_proposal_id` linkage to the failed parent.

**Rationale:**
Only a fresh proposal preserves the exactly-once invariant *per confirmed proposal*. The operator's deliberate re-dispatch intent is kept (it remains a deliberate operator action), but each execution attempt is separately gated and audited, so a double-apply can never be attributed to a single confirmed proposal.

**Consequence:**
- **Epics already implement this lean:** Epic 2 Story 2.4 — "a re-dispatch is a NEW proposal with fresh dry-run + confirmation and `supersedes_proposal_id` linkage (PD-6)". No epic change needed; this entry records the decision the epics assumed.
- **Architecture guards it further (PD-10/PD-11 leans):** dispatch sets state=`failed` on a 5 s timeout and re-dispatch is allowed only from `failed`; superseding an in-flight `dispatched` parent is rejected. Those remain architecture-phase decisions (this entry fixes the re-dispatch *semantics* they depend on).
- SPECIFICATIONS.md S-D `Re-dispatch proposal` control stays, but its semantics are now bound to the new-proposal gate.

**Assumptions / Open questions:**
- PD-10 (executor dispatch timeout → `failed`) and PD-11 (only `failed` parents superseded) remain open architecture-phase decisions; D23 is the semantic anchor they build on.

**Status:** Accepted for V1 (2026-09-28).

---

## D24 — Determinism Enforcement: Retrieval-Composition (PD-1, OQ-5)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-1 resolved.

**Decision:** Enforce evidence-level determinism (D4) via **retrieval-composition**: a deterministic Evidence Assembler builds a fixed, ordered EvidenceSet (records + policy clauses + events + clock read, with a monotonic `position` per entry), and the LLM is constrained to prose generation over that fixed payload. Reject constrained decoding and template-fill as the enforcement mechanism.

**Alternatives considered:**
- Constrained decoding — rejected: couples determinism to the decoder, brittle across model/runtime changes, and does not pin evidence selection or citation identity.
- Template-fill — rejected: too rigid for free-text explanations and does not govern retrieval ordering.
- Retrieval-composition — selected.

**Rationale:** Evidence/citation/classification identity (NFR-4) is produced by the retrieval + composition layer, not the LLM; AD-2/AD-8/AD-14 already encode it. LLM variance is confined to prose.

**Consequence:** Architecture invariants AD-2 (deterministic evidence assembly), AD-8 (claims bound to citations), AD-14 (citation identity + evidence ordering) are the enforcement point; FR-14's 3×-run identity test validates it. Resolves OQ-5.

**Status:** Accepted for V1 (2026-09-28).

---

## D25 — Event-Log Design: Reason-on-Event (PD-2, OQ-6)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-2 resolved.

**Decision:** Record the diagnosis reason **on the event itself** (`recorded_reason`), rather than replaying the policy version at event time.

**Alternatives considered:**
- Replay policy-version at event time — rejected: requires versioning every policy clause plus a replay engine — disproportionate for the prototype's scenario needs.
- Reason-on-event — selected.

**Rationale:** Cheap and sufficient (D5); retrospective diagnosis (FR-06) reads the recorded reason directly; the `OperationalEvent` schema already carries `outcome` + `recorded_reason`.

**Consequence:** Event schema = `event_id, type, entity_ref, timestamp, outcome, recorded_reason`; FR-06 cites the recorded reason. Resolves OQ-6.

**Status:** Accepted for V1 (2026-09-28).

---

## D26 — Entity Match Tolerance: Exact in V1 (PD-3, OQ-9)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-3 resolved.

**Decision:** Entity resolution is **exact (case-folded) match in v1**; typo-tolerant matching is deferred.

**Alternatives considered:**
- Typo-tolerant / fuzzy matching in v1 — rejected: weakens the anti-fabrication bar (FR-03/NFR-2) and adds fuzzy-match surface; the canonical Entity-Not-Found response already handles misspellings honestly.
- Exact in v1 — selected.

**Rationale:** FR-03's measurable condition (0 fabricated, 100% Entity-Not-Found) is cleanest under exact match; AD-7 (deterministic exact-match entity resolution) encodes it. Typo-suggestion UI stays deferred (UX-17).

**Consequence:** Resolution case-folds and compares exactly; misspellings return the canonical response with zero fabrication. Resolves OQ-9.

**Status:** Accepted for V1 (2026-09-28).

---

## D27 — Fixture Values Set at Authoring Time (PD-5, OQ-2)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-5 resolved.

**Decision:** Night Policy hours, catalog-policy schema, and error-code semantics are **defined at fixture-authoring time**; the PRD pins behavior, not values (A-10).

**Alternatives considered:**
- Pin exact fixture values in the PRD now — rejected: fixture content is scenario data, not requirement; pinning early adds no requirement value and constrains the evaluation corpus.
- Set at authoring time — selected.

**Rationale:** Fixtures are the frozen evaluation corpus that determinism (FR-14) and accuracy (NFR-1) are measured against; they are authored once and frozen.

**Consequence:** Fixture files (S1 Alex/deepseek-coder, S2 Group 4/Night Policy, S3 ws-gpu-11/ERR_THERMAL_88, S4 CS201) are authored and frozen; any change re-opens determinism tests. Resolves OQ-2.

**Status:** Accepted for V1 (2026-09-28).

---

## D28 — Retrospective-Diagnosis Journey (PD-7, FR-06)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-7 resolved.

**Decision:** Realize the "Retrospective event diagnosis" intent as a **dedicated journey** in Epic 3 (Story 3.2 — event-log retrospective diagnosis) with an explicit FR-06 traceability row, plus the rendering target in Story 3.4. The taxonomy intent now has an end-to-end scenario to test against.

**Alternatives considered:**
- Fold into S1 only — rejected: S1 is access-denial; a cancellation/denial/cordon retrospective journey warrants its own coverage for FR-06's measurable condition.
- Dedicated journey — selected.

**Rationale:** FR-06's "retrieve the correct event record 100%" needs a scenario target; schedule (S2) and runbook (S3) are separate journeys, so retrospective gets its own story.

**Consequence:** Epic 3 Story 3.2 is the FR-06 target; the never-occurred-event case is covered (D19 trio, VALIDATION). Resolves PD-7.

**Status:** Accepted for V1 (2026-09-28).

---

## D29 — Follow-Up Reference Rendering (PD-8, FR-02)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-8 resolved.

**Decision:** Add a **follow-up turn to scenario 03** (node triage) demonstrating prior-turn session-context resolution — e.g., "and what about ws-gpu-12?" resolves `ws-gpu-12` against session context first, re-validates against current state (PD-14), then cites the resolved entity (D35). The rendering target is carried in Story 3.4.

**Alternatives considered:**
- No demonstrated turn — rejected: FR-02's ≥ 95% follow-up condition would be untested and its rendering unspecified.
- One follow-up turn in scenario 03 — selected.

**Rationale:** FR-02 requires follow-up references to resolve from session context; a demonstrated turn makes the behavior and rendering explicit and testable.

**Consequence:** Scenario 03 gains a follow-up turn; Story 3.4 verifies resolution + citation of the resolved entity. Resolves PD-8.

**Status:** Accepted for V1 (2026-09-28).

---

## D30 — Positive Schedule-Case Rendering (PD-9, FR-05/NFR-1)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-9 resolved.

**Decision:** Specify the positive schedule-case answer anatomy: diagnosis **"no restriction applies"** with **no window rendered** (mirrors the existing no-constraint case; never an implied schedule).

**Alternatives considered:**
- Leave the positive case unspecified — rejected: NFR-1's extension corpus is likely to include a job that can run now; the answer anatomy must be defined.
- "No restriction applies" + no window — selected.

**Rationale:** Consistent with FR-05's explicit no-constraint handling; never imply a window that policy does not grant (avoids the same class of error as D39).

**Consequence:** Story 3.1 (schedule) and Story 3.4 (UX target) render the positive case; VALIDATION covers it. Resolves PD-9.

**Status:** Accepted for V1 (2026-09-28).

---

## D31 — Executor Dispatch Timeout (PD-10, §3.7 / §5 AD-15)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-10 resolved.

**Decision:** On dispatch, if the executor has not returned within **5 s**, set proposal state = `failed`; re-dispatch is allowed only from `failed`.

**Rationale:** A hung executor otherwise leaves the proposal stuck in `dispatched` forever, blocking the re-dispatch path defined in D23.

**Consequence:** Proposal state machine (`refused → dry_run → confirmed → dispatched → executed/failed/superseded`) gains a timeout transition; the delegation card renders the failure with the proposal line preserved; no auto-retry (FR-16).

**Status:** Accepted for V1 (2026-09-28).

---

## D32 — Re-Dispatch While Parent Dispatched (PD-11, §5 AD-3)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-11 resolved.

**Decision:** Reject superseding a proposal that is still `dispatched`; only `failed` parents may be superseded.

**Rationale:** Two live handoffs could both apply, double-applying across proposals (FR-10, UX-06).

**Consequence:** Re-dispatch (D23) is only reachable from the `failed` state; an in-flight `dispatched` parent cannot be superseded.

**Status:** Accepted for V1 (2026-09-28).

---

## D33 — Partial Executor Application (PD-12, §5 AD-15)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-12 resolved.

**Decision:** If `applied_count < len(affected_items)`, set proposal state = `failed` and render **per-item executor results**.

**Rationale:** A silent partial deletion must never render as success; FR-10's exactly-once/applied-mutation semantics must be visible.

**Consequence:** The delegation card shows per-item outcomes; partial application surfaces as executor failure, never a second success (UX-06).

**Status:** Accepted for V1 (2026-09-28).

---

## D34 — Session Reset With Dispatched Proposal (PD-13, §1.7 / §5 AD-4)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-13 resolved.

**Decision:** A session reset keeps dispatched proposals tracked and surfaces the late executor result when it returns.

**Rationale:** Reset must not orphan an in-flight executor application or erase its result from the audit trail.

**Consequence:** Reset clears conversation context only; the proposal's terminal state still resolves and its audit row completes (FR-11).

**Status:** Accepted for V1 (2026-09-28).

---

## D35 — Re-Validate Context-Resolved Entities Before Citing (PD-14, §5 AD-7)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-14 resolved.

**Decision:** Follow-up entities resolved from session context are **re-resolved against the providers before citing**.

**Rationale:** A diagnosis must not cite a deleted or changed record (FR-03, NFR-2).

**Consequence:** The scenario 03 follow-up turn (D29) re-validates before citing; Story 3.4 verifies it.

**Status:** Accepted for V1 (2026-09-28).

---

## D36 — Ambiguous Bare Entity Type Routes to Clarification (PD-15, §5 AD-7)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-15 resolved.

**Decision:** A bare name reference with multiple possible entity types (e.g., `alex` as user vs group) routes to **clarification** when the intent does not fix the type.

**Rationale:** Guessing the type risks fabricating an identity (FR-03/NFR-2).

**Consequence:** FR-01's clarification path handles ambiguous bare references; no forced routing.

**Status:** Accepted for V1 (2026-09-28).

---

## D37 — Compound Query With Mixed Outcomes Returns Per-Sub-Query Answers (PD-16, §3.1 FR-01)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-16 resolved.

**Decision:** A decomposed compound query with mixed outcomes returns a **per-sub-query `Answer` array**; each sub-answer carries its own answer chain and canonical response.

**Rationale:** Mixed outcomes (one sub-query Entity-Not-Found, the other diagnosed) require a defined response envelope.

**Consequence:** FR-01 compound handling returns an `Answer` array; the UI renders each sub-answer with its own chain and canonical response.

**Status:** Accepted for V1 (2026-09-28).

---

## D38 — Window-Boundary Inclusivity: Half-Open Interval (PD-17, §2.1 / §5 AD-2)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-17 resolved.

**Decision:** A window is open when **`start <= t < end`**; the half-open interval is encoded in the window calculator.

**Rationale:** A current time exactly equal to the start or end must not produce an off-by-one next-window computation (FR-05).

**Consequence:** Epic 3 Story 3.1's window calculator uses `[start, end)`; determinism holds at boundary times.

**Status:** Accepted for V1 (2026-09-28).

---

## D39 — Midnight-Crossing Window: Explicit Date + Timezone (PD-18, §5 AD-2)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-18 resolved.

**Decision:** Render an **explicit date plus timezone for both window edges** — never "next open window: today 20:00–08:00".

**Rationale:** A night window crossing midnight can name the wrong day (UJ-2 climactic value is a first-class cited fact, FR-05).

**Consequence:** Story 3.1 renders e.g. `2026-09-28T20:00:00Z–2026-09-29T08:00:00Z`; the citation binds both edges.

**Status:** Accepted for V1 (2026-09-28).

---

## D40 — Event-Log Time-Window Boundary: Half-Open (PD-19, §2.1 FR-06)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-19 resolved.

**Decision:** Event-log queries match on a **half-open `[start, end)` interval**.

**Rationale:** An event timestamp exactly on the boundary must not be excluded or double-counted (FR-06).

**Consequence:** Epic 3 Story 3.2's event query uses `[start, end)`.

**Status:** Accepted for V1 (2026-09-28).

---

## D41 — Audit-Write Failure Aborts the Answer (PD-20, §5 AD-10)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-20 resolved.

**Decision:** If the audit insert fails after a tool call succeeded, mark the tool call `failed` and **abort the answer**.

**Rationale:** FR-11's exactly-one-entry guarantee must not be silently violated.

**Consequence:** No answer completes without its audit row; the safe-failure path renders (FR-16).

**Status:** Accepted for V1 (2026-09-28).

---

## D42 — Retention Rotation via Exempt Rotation-Writer (PD-21, §5 AD-10)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-21 resolved.

**Decision:** Exempt a **dedicated rotation-writer identity** from the delete-denying trigger; each rotation is logged.

**Rationale:** Retention rotation cannot run (or would break append-only) under the current delete-denying trigger (D15, NFR-11).

**Consequence:** Append-only is preserved for the audit trail; rotation is an audited, identity-scoped operation.

**Status:** Accepted for V1 (2026-09-28).

---

## D43 — Cordoned Node With Null Error Code (PD-22, §5 AD-9)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-22 resolved.

**Decision:** If `error_code` is null on a cordoned node, return **`no runbook available`** citing the node record.

**Rationale:** A null code must not crash or invent a runbook (FR-07/FR-08).

**Consequence:** Story 3.3 handles a null `error_code` with explicit unavailability.

**Status:** Accepted for V1 (2026-09-28).

---

## D44 — Empty Runbook Template Rejected at Registration (PD-23, §5 AD-9)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-23 resolved.

**Decision:** Reject a runbook template at **registration** when its steps list is empty.

**Rationale:** An empty template must never render as actionable guidance (FR-08).

**Consequence:** The runbook registry (AD-9) validates step lists on registration; Story 3.3 AC covers it.

**Status:** Accepted for V1 (2026-09-28).

---

## D45 — Credential-Keyed Redaction (PD-24, §5 AD-10)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-24 resolved.

**Decision:** Redact any value under **credential-named keys regardless of shape**, not just a fixed pattern list.

**Rationale:** A secret-shaped value outside the fixed patterns would otherwise leak into audit rows (NFR-11, D15).

**Consequence:** The audit redaction filter is key-name-driven; sampled entries stay secret-free.

**Status:** Accepted for V1 (2026-09-28).

---

## D46 — Browse Result Cap and Pagination (PD-25, §3.2 AD-13)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-25 resolved.

**Decision:** Cap the state-browse result count and paginate via `page`/`page_size`.

**Rationale:** A broad `?q=` match must not return the entire entity store (FR-12, AD-13).

**Consequence:** Story 1.8's browse is capped/paginated; unbounded lists are impossible.

**Status:** Accepted for V1 (2026-09-28).

---

## D47 — Second Confirm Is Idempotent or Rejected (PD-26, §5 AD-3)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-26 resolved.

**Decision:** Treat an **identical proposal + gate-token confirm as idempotent**; any other confirm against an already-dispatched proposal is **rejected with 409**.

**Rationale:** A double-click must not race the dispatch gate (FR-09/FR-10).

**Consequence:** The dispatch endpoint dedupes identical proposal+token; differing confirms are rejected.

**Status:** Accepted for V1 (2026-09-28).

---

## D48 — Prose Lexical Guard: Reject and Retry, Never Strip (PD-27, §5 AD-8)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-27 resolved.

**Decision:** On a forbidden evidence token in prose, **reject the whole output and retry once**; never strip mid-sentence.

**Rationale:** Stripping mangles prose and the strip-vs-reject ambiguity was undefined (FR-15 content hygiene).

**Consequence:** Content hygiene rejects polluted prose and retries once; zero mangled prose reaches the operator.

**Status:** Accepted for V1 (2026-09-28).

---

## D49 — Session and Answer Retention Cap (PD-28, §1.7 / §2.2)

**Provenance:** Human decision (Julio), 2026-09-28 — PD-28 resolved.

**Decision:** Apply the **same retention cap and rotation** to sessions and answers as the audit log.

**Rationale:** Unbounded SQLite growth contradicts the capped audit log (NFR-11, D15).

**Consequence:** Session/Answer stores honor the same cap/rotation as `AuditRecord`; the prototype DB stays bounded.

**Status:** Accepted for V1 (2026-09-28).

---

## D50 — Prototype Retention Cap Values (OQ-12)

**Provenance:** Human decision (Julio), 2026-09-28 — OQ-12 resolved.

**Decision:** Concrete prototype retention values: **AuditRecord, Session, and Answer stores are each capped at 10,000 rows**, with rotation removing the oldest rows first (consistent with D49's same-cap rule). Rotation is performed by the exempt rotation-writer identity and logged (D42); redaction is key-name-driven regardless of value shape (D45).

**Alternatives considered:**
- Leave the cap as an unresolved prototype detail — rejected: OQ-12 explicitly asks for the values, and the readiness gate wants no open decisions.
- Per-store differing caps — rejected: D49 already commits sessions/answers to the audit log's cap; a single value keeps the rule simple and testable.

**Rationale:** 10,000 rows bounds the prototype SQLite file well below evaluation-window growth while giving ample headroom for the 50-call audit sessions (FR-11) and the NFR-6 throughput (≥ 50 queries/hour over 8 h).

**Consequence:** Stores honor the 10,000-row cap with oldest-first rotation; rotation logged; determinism (FR-14) is unaffected because rotation touches only evicted history. Resolves OQ-12.

**Status:** Accepted for V1 (2026-09-28).

---

## D51 — Session Retention Window / Context Lifetime (OQ-13)

**Provenance:** Human decision (Julio), 2026-09-28 — OQ-13 resolved.

**Decision:** Server-side session context is retained for the life of an active operator session with a **30-minute idle timeout** and a **maximum of 200 turns retained per session**; an explicit reset clears all context immediately (FR-02). Follow-up references resolve against the retained context, then re-validate against current state before citing (D29/D35).

**Alternatives considered:**
- No retention window (context forever) — rejected: contradicts the bounded-store decision (D49/D50) and the "minimal session context, not general conversational memory" boundary (FR-02, §16).
- Very short window — rejected: would break the ≥ 95% follow-up-resolution condition (FR-02) for mid-shift sessions.

**Rationale:** 30 minutes of idle + 200 turns comfortably covers a Nadia mid-shift flow (UJ-1–UJ-4) while keeping the session store bounded by the D50 cap.

**Consequence:** Session TTL and turn cap are config constants; expiry and reset are logged like any other tool call; store bounded (D49/D50). Resolves OQ-13.

**Status:** Accepted for V1 (2026-09-28).

---

## AI Recommendations Rejected by Human Judgment

Evidence that human judgment, not passive acceptance, governed the specification. Every AI recommendation below was triaged (**Accept** / **Defer** / **Reject**); the rejected set is recorded here with the technical reasoning that led to the human override. Tally: **51 decisions adopted** (D1–D51 — no items pending), **5 AI capability proposals rejected** on boundary grounds (UX-18–UX-22), **1 AI recommendation deferred post-V1** (PRD Finding 22).

### Rejected — boundary contradictions (UX edge-case review, Pass 1)

The AI design loop proposed five capability expansions; each was **rejected** because it would break Module 12's read-only, propose-only contract. Full record: `_bmad-output/planning-artifacts/ux-designs/ux-plan-2-university-ai-fabric-2026-09-27/review-ux-edge-cases.md`.

**UX-18 — Direct cancellation/deletion control on the Inspector.** AI proposed a "cancel/delete job" button in the State Inspection Viewer. **Rejected by human:** Module 12 explains and proposes only; job cancellation/deletion is delegated job-control. The Inspector is read-only (FR-12); cancellation appears solely as a delegated proposal through the Safety flow. *Traceability: PRD §2.3, §2.4, §16, FR-09.*

**UX-19 — Module 12 as authoritative system of record for policy/state.** AI proposed an in-console editor that writes policy or state. **Rejected by human:** Module 12 is a read-only consumer (A-2, C-3); retrieved content is data, never control (C-7, FR-15). The Inspector renders field-for-field and marks stores read-only; no write path exists. *Traceability: PRD §2.4, A-2, C-3, C-7, FR-15.*

**UX-20 — Confirmation as identity/authorization.** AI proposed the confirmation control implying or asserting administrative authority. **Rejected by human:** the gate is a deliberate procedural safety boundary, not an authorization mechanism (A-13, C-8, FR-09); the dialog caption is contractually non-authorizing. *Traceability: A-13, C-8, FR-09, OQ-4.*

**UX-21 — Reservation/lecture-machine availability management.** AI proposed managing reservations or lecture-machine availability from the console. **Rejected by human:** reservation conflicts are diagnosed, not owned; the Inspector reads reservation/policy-window records only. *Traceability: PRD §2.4, §16, S2.*

**UX-22 — Node cordon/uncordon from the console.** AI proposed an "uncordon" action button on the node Inspector or runbook. **Rejected by human:** cordon/uncordon and physical remediation belong to node management; Module 12 produces the runbook and the delegated proposal, never the action. *Traceability: PRD §2.3, S3.*

### Deferred — PRD adversarial review (2026-09-27)

**Finding 22 — Comparative analysis of competing tools.** AI recommended adding comparative analysis to the PRD. **Deferred by human (post-V1):** useful but not required for a testable V1 spec; recorded as a post-V1 product/design question and intentionally unchanged. The remaining 21 findings were **Accepted** and fixed in the PRD.

### Rejected — AI-proposed alternatives inside decision entries

Several AI-proposed design options recorded in the entries above were rejected by human judgment with technical reasoning, including: blocking all scope work until the Annex is supplied (**D1**); the Copilot executing mutations itself after confirmation + dry-run (**D3**); abandoning determinism guarantees (**D4**); building a full observability subsystem (**D5**); a broad speculative state model (**D6**); renaming the protagonist to Elena and the Elena/Nadia bridge (**D7**); building a full auth/role system in V1 (**D9**); and treating retrieved content as trusted (**D11**).

---

## Resolved Open Decisions

All previously pending decisions are now resolved as log entries (2026-09-28); **the log has no open decisions.**

**Phase 2 judgment calls:**
- PD-1 → **D24** (determinism enforcement: retrieval-composition)
- PD-2 → **D25** (event-log design: reason-on-event)
- PD-3 → **D26** (entity match: exact in v1, typo-tolerance deferred)
- PD-5 → **D27** (fixture values set at authoring time)
- PD-7 → **D28** (retrospective-diagnosis journey in Epic 3)
- PD-8 → **D29** (follow-up reference turn in scenario 03)
- PD-9 → **D30** (positive schedule-case rendering)
- *(PD-4 → D9; PD-6 → D23 resolved earlier)*

**Architecture-phase edge-case guards:**
- PD-10 → **D31** (executor dispatch timeout → `failed`, re-dispatch only from `failed`)
- PD-11 → **D32** (reject superseding an in-flight `dispatched` parent)
- PD-12 → **D33** (partial executor application → `failed` + per-item results)
- PD-13 → **D34** (reset keeps dispatched proposals tracked)
- PD-14 → **D35** (re-resolve context-resolved entities before citing)
- PD-15 → **D36** (ambiguous bare entity type → clarification)
- PD-16 → **D37** (compound mixed outcomes → per-sub-query `Answer` array)
- PD-17 → **D38** (window open when `start <= t < end`)
- PD-18 → **D39** (explicit date + timezone on both window edges)
- PD-19 → **D40** (event match on `[start, end)`)
- PD-20 → **D41** (audit-write failure aborts the answer)
- PD-21 → **D42** (rotation via exempt rotation-writer identity)
- PD-22 → **D43** (null `error_code` → `no runbook available`)
- PD-23 → **D44** (empty runbook template rejected at registration)
- PD-24 → **D45** (credential-keyed redaction)
- PD-25 → **D46** (browse result cap + pagination)
- PD-26 → **D47** (identical confirm idempotent; else 409)
- PD-27 → **D48** (prose guard: reject + retry once, never strip)
- PD-28 → **D49** (session/answer retention cap)

**Open questions resolved by decisions:** OQ-2 → D27 · OQ-5 → D24 · OQ-6 → D25 · OQ-9 → D26 · OQ-12 → D50 · OQ-13 → D51.

Full findings with suggested guards: `_bmad-output/planning-artifacts/architecture/architecture-plan-2-university-ai-fabric-2026-09-27/reviews/review-arch-edge-cases.md`.

---

## Deferred to External Input or Out of V1 Scope (explicit, not silent)

These items are **not** open design decisions — they are either dependent on external input the project does not control, or deliberately out of the V1 prototype. Each is explicitly tracked so nothing is silently unresolved.

| Ref | Item | Status | Why it is deferred |
|-----|------|--------|--------------------|
| OQ-1 | Full module Annex availability | External input required | The course Annex is not yet provided; boundaries were defensively derived (**D1**) and must be re-validated against the Annex when it arrives. |
| OQ-3 | Read-contract scope in the full system (shared API vs per-module) | Decided for V1; full-system deferred | V1 uses per-module read-only interface contracts (**D2**); whether they become a shared platform API is decided at real-module integration, outside V1. |
| OQ-4 | Full-system administrator identity/authorization | External subsystem | V1 confirmation is a procedural gate (**D9**); real authentication/authorization belongs to the external administrative/access-control subsystem, out of prototype scope. |
| OQ-7 | Reserved future entities (quotas, fair-share weights) | By-design deferral | Deferred by the scenario-driven state model (**D6**); not built in Phase 1. |
| OQ-8 | Latency budget feasibility on the chosen LLM runtime | Measured, not decided | A validation target (NFR-5, SM-5) verified empirically in the prototype; not a spec decision. |
| OQ-10 | Operator roles/access control on the console in the full system | Out of V1 | V1 has minimal operator identity (A-13, **D9**); console access control is a full-system concern. |
| OQ-11 | Institutional owner of physical-intervention runbook content | External approval | Runbooks require an approved institutional source (**D14**); V1 requires provenance metadata, never self-certification. |
| Finding 22 | Comparative analysis of competing tools | Deferred post-V1 | Useful but not required for a testable V1 spec (see AI Recommendations Rejected by Human Judgment). |
