# Adversarial Review — Triage Record

- **Artifact:** PRD, Module 12 — AI Operations Copilot
- **Canonical path:** `_bmad-output/planning-artifacts/prds/prd-plan-2-university-ai-fabric-2026-09-27/prd.md`
- **Reviewed path (as requested):** `docs/planning-artifacts/prd.md` (does not exist — see Finding 1)
- **Date:** 2026-09-27
- **Lens:** adversarial (bmad-review-adversarial-general)
- **Method:** Cynical review producing 22 findings; human triage classified each as Accept / Defer / Reject.
- **Note on Finding 1:** The PRD is **not** moved or duplicated into `docs/planning-artifacts/`. The canonical location chosen by BMAD is retained. All review/reference commands and internal documentation must point to the canonical path above.

## Triage

| # | Classification | Rationale | PRD section(s) changed or intentionally unchanged | Resulting consequence |
|---|---|---|---|---|
| 1 | Accept (keep current location) | The issue is the review/reference path, not the artifact location chosen by BMAD. | §0 (document purpose) — added `canonical_path` frontmatter field and explicit reference to `review-prd-adversarial.md`. PRD file location unchanged. | All future review/reference commands must use the canonical path; the record now points to the authoritative location. |
| 2 | Accept | A non-console user cannot drive all four journeys; mapping must reflect actual relevance. | §3 Dr. Aris Thorne persona — now associated only with UJ-1, UJ-2; §3 Nadia — clarified as primary persona driving UJ-1–UJ-4. | Persona-to-journey mapping is consistent; no persona claims journeys it does not appear in. |
| 3 | Accept | Reservation conflict is out of Module 12's scope; remove the promise rather than expand scope. | §3 Aris persona — removed "lecture machines must be reserved and free" promise; §2.4 and §16 — added explicit reservation-management exclusion. | No persona implies a capability the module does not deliver; scope boundaries stay intact. |
| 4 | Accept | Concurrency is a session-level requirement; "only user" wording was over-strict. | §2.4, §3 Nadia, A-9, NFR-6, NFR-9, glossary (new "Nadia-class operator" term). | Nadia remains the named primary persona; concurrency/throughput now scoped as session-level with an explicit operator-profile definition. |
| 5 | Accept | Sequential numbering is required; FR-13 was out of order. | §7 all FRs renumbered FR-01–FR-16 (event-log retrospective moved to FR-06; new FR-02, FR-15, FR-16 added); all cross-references in §8–§15 updated. | Numbering is sequential in document order; every FR/NFR/traceability reference updated (verified by re-check). |
| 6 | Accept | PRD must not imply byte-identical prose. | §0, §1 vision, G-1, §7.3 description, FR-14 (determinism), SM-1 — wording changed to "evidence-level deterministic" with explicit definition. | Language now matches D4/A-5/A-11: determinism = evidence/citation/class/step identity, prose may vary. |
| 7 | Accept | Citation coverage must be reproducible, not dependent on undefined judgment. | FR-13 (new) — added a concrete citation-coverage rubric (what counts as a factual claim, how coverage is evaluated, machine-checkable claim→source mapping). | The 100% citation metric is now testable over the fixture corpus without free-form human/LLM judgment. |
| 8 | Accept | Unbounded "zero fabrication" is not measurable. | NFR-2, G-2, SM-2, FR-03 — rewritten to be bounded to the defined simulated state and evaluation corpus; mandatory edge case returns "Entity Not Found in State". | Anti-fabrication is testable: resolution against defined state or canonical Entity-Not-Found, 0 fabrication over the defined corpus. |
| 9 | Accept | An agentic LLM consuming retrieved content needs explicit data-hygiene. | §7.8 (new Threat Model & Content Hygiene section), FR-15 (new), C-7, S-7, A-16, §16 (in-scope threat assumptions). | Query text and retrieved content are treated as data; injection corpus test enforces behavioral parity and zero control-flow effects. |
| 10 | Accept | Confirmation is a procedural safety boundary, not auth. | FR-09 validation, A-13, C-8, glossary ("Confirmation gate (procedural)"), OQ-4. | The guardrail is honest about being procedural in V1; the copilot never infers admin authority from the UI session; real identity/authorization delegated + mocked. |
| 11 | Accept | Compound queries must not be silently truncated. | FR-01 — multi-intent decomposition or clarification added to responsibility, validation, outputs, and test condition; §7.1.1 intent taxonomy. | Compound queries either decompose into independently validated sub-queries or trigger clarification; behavior is tested. |
| 12 | Accept | A conversational console needs minimal session semantics. | FR-02 (new) + §7.1 description, traceability PT/S1–S4 rows, OQ-13, §16 (not a general conversational-memory system), §17. | Sessions have creation, context retention, follow-up entity resolution, and reset; bounded to prototype scope. |
| 13 | Accept | Glossary and FR sequence must agree. | Glossary "Dry-run" definition corrected (dry-run precedes confirmation/handoff); FR-09 sequence consistent. | Terminology and behavioral sequence now agree. |
| 14 | Accept | The simulated executor's behavior was ambiguous. | FR-10, UJ-4 resolution, glossary "Propose-only handoff" — executor applies mutation only after the confirmation gate; audit log distinguishes copilot proposal from executor-applied mutation; FR-11 (audit) note. | The demo's mutation path is defined; the safety metric (0 copilot-originated mutations) is meaningful and the audit distinguishes actors. |
| 15 | Accept | Routing needs an explicit intent inventory. | §7.1.1 — added V1 intent taxonomy table (purpose, trigger shape, inputs, associated FRs). | Every registered intent is explicit; routing, inputs, and FR ownership are traceable. |
| 16 | Accept | Two non-fabrication responses were conflated. | §7.2, glossary ("Entity Not Found in State" vs "Cannot confirm (insufficient evidence)"), FR-03–FR-06 outputs, S-2. | Canonical response categories are defined and consistently applied: absent entity vs. present entity with insufficient evidence. |
| 17 | Accept | No metric measured the headline value claim. | SM-5 (new), A-14, G-1/§1 — diagnosis completion time metric added; "hours" baseline labeled illustrative; no invented university baseline. | Core value is measurable; unsupported claims about current resolution time are flagged as assumptions. |
| 18 | Accept | Runbook content is consumed, not certified. | FR-07, FR-08 (provenance + version metadata, approved-source rule), OQ-11 (new), UJ-3 resolution, §16 (not a certifier). | Module 12 consumes approved content; the institutional owner of physical-safety content is a recorded open question. |
| 19 | Accept | Failure modes were unspecified. | §7.9 (new Resilience & Safe Failure), FR-16 (new), NFR-7, S-8. | Each failure class (LLM timeout, state-provider, policy-source, malformed input, executor unavailability) has defined safe-fail behavior and a fault-injection test. |
| 20 | Accept | Matrix must map only governing requirements. | §15 traceability matrix fully reconciled against final FR/NFR numbering; S1 no longer lists the retrospective FR; new FRs added to governing rows; S3/S4/EC/PT tightened. | Every mandatory scenario maps only to requirements that govern it, under final numbering. |
| 21 | Accept | PII clause was tautological. | NFR-11, FR-11 — concrete logging rules (allowed identifiers, retention cap + rotation, secret redaction), OQ-12 (new), DP-7 (new). | Audit log rules are concrete and bounded; no unlimited immutable storage implied. |
| 22 | Defer (post-V1) | Comparative analysis is useful but not required for a testable V1 spec. | Intentionally unchanged. | Recorded as a post-V1 product/design question; does not block V1. |

## Re-check (post-change)

1. **FR/NFR numbering** — FR-01–FR-16 sequential in document order; NFR-1–NFR-11 reference the final numbers; confirmed by grep (no stale FR references).
2. **Scenario traceability** — §15 reconciled; each scenario maps only to governing FRs/NFRs under final numbering.
3. **Persona-to-journey mapping** — Nadia drives UJ-1–UJ-4; Aris is associated with UJ-1/UJ-2 only; Mateo with UJ-1; no non-user claims console journeys.
4. **Deterministic/evidence terminology** — broad "deterministic" claims replaced with "evidence-level deterministic" + definition; A-5/A-11/D4 consistent.
5. **Safety and delegation boundaries** — zero mutation path (C-1), procedural confirmation (D9), propose-only handoff with post-gate executor application (FR-10), content data-hygiene (FR-15).
6. **Hallucination/non-fabrication behavior** — bounded to defined state + corpus (NFR-2/FR-03); canonical Entity-Not-Found vs cannot-confirm (FR-04–06, S-2).
7. **Failure modes** — FR-16 covers LLM timeout, state-provider, policy-source, malformed input, executor unavailability; NFR-7 updated.
8. **Measurable acceptance conditions** — citation rubric (FR-13), bounded anti-fabrication, SM-5 completion time, fault-injection tests all concrete.
9. **Glossary ↔ FR/NFR/scenario consistency** — Dry-run, Confirmation gate, Propose-only handoff, Nadia-class operator, and the two canonical responses are defined and referenced consistently.

## Decisions escalated to the AI Decision Log

The significant decisions arising from this review are recorded as entries **D8–D15** in `ai-decision-log.md` (same directory).