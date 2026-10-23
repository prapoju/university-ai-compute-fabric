# PRD/SCOPE Reconciliation Review — Module 12 Architecture

- **Reviewer:** PRD/SCOPE Reconciliation (capability gate)
- **Target:** `ARCHITECTURE.md` (architecture-plan-2-university-ai-fabric-2026-09-27)
- **Canonical sources:** `prd.md` (FR-01..FR-16, NFR-1..NFR-11, S-1..S-8, C-1..C-8, A-1..A-16, §15 traceability); `ai-decision-log.md` (D1..D22, PD-1..PD-9); Phase-2 UX artifacts (`DESIGN.md`, `EXPERIENCE.md`, `SPECIFICATIONS.md`, `VALIDATION.md`, `review-ux-edge-cases.md` — UX-01..UX-30)
- **Method:** every load-bearing PRD input walked against the architecture's components, routes, and AD-1..AD-13; quiet requirements checked; scope-change scan vs. the Phase 1/2 decision record; Open Architectural Decisions section audited.
- **Scope:** review-only. No files modified.

---

## Verdict

**The architecture faithfully lands FR-01..FR-16 and the entire D-series safety/determinism spine — the read-only boundary (AD-1), propose-only exactly-once handoff (AD-3), server-side ordered safety state machine (AD-4), and evidence-level determinism (AD-2) are all enforced — but it is not shippable as-is: NFR-5/6/7 (latency, concurrency, availability) have no architectural allocation and sit in un-flagged tension with the single-process synchronous stack, and the UX-08 session-reset-mid-flow edge is bound nowhere, so this review is APPROVE-WITH-CONDITIONS pending HIGH-1 and HIGH-2.**

## 1. FR / NFR Coverage Table

| ID | Requirement (abridged) | Architecture coverage | Status |
|---|---|---|---|
| FR-01 | Conversational intake & intent routing; compound decompose-or-clarify; no forced routing | §1.3 Intent Classifier (taxonomy, decomposition, LLM-assist only for clarification); AD-4 rule "compound containing a destructive verb routes to clarification, never decomposition"; AD-11 (routing from taxonomy/config only) | ✅ Covered |
| FR-02 | Minimal session/context; follow-up refs; reset; context never authorizes destructive | §1.7 Session Store; §3.1 session routes incl. `DELETE` reset; AD-5 ("session context never authorizes a destructive action"); follow-up resolution via AD-7 resolver. **UX-08 reset-mid-flow semantics unbound → HIGH-2** | ⚠️ Partial (gap: UX-08) |
| FR-03 | Entity resolution exact-match; Entity-Not-Found guardrail | AD-7 (exact id, unresolved → literal `Entity Not Found in State`, diagnosis gated on full resolution); canonical strings in Consistency Conventions | ✅ Covered |
| FR-04 | Access-denial diagnosis | §1.5 access-denial diagnoser; §2.1 reason_class; §4.2 flow; AD-2/AD-8 | ✅ Covered |
| FR-05 | Schedule/window; next-open-window; no-constraint explicit, no implied window | §1.5 schedule+window diagnoser + Window Calculator; clock port (P9); no-window-unconstrained + positive case surfaced via PD-9 in Open Decisions | ✅ Covered |
| FR-06 | Retrospective event diagnosis; cannot-confirm on no event | §1.5 retrospective diagnoser; §2.1 `OperationalEvent` (reason-on-event, D5/PD-2); AD-8 canonical downgrade | ✅ Covered |
| FR-07 | Node-triage runbook; never invent steps | §1.5 node-triage; AD-9 (cordon+code verified before lookup; code mismatch → `no runbook available for the recorded code`) | ✅ Covered |
| FR-08 | Runbook source rule; provenance/version; approved source for physical steps | AD-9 (registry-bound, verbatim steps, provenance/version rendered+audited, approved-source metadata gate) | ✅ Covered |
| FR-09 | Destructive refusal → dry-run → explicit confirm → handoff | §1.9 safety state machine; AD-4 (ordered, refused before dry-run, no-op confirm disabled); AD-5 (procedural, distinct request); AD-6 (re-validation); §3.6 routes | ✅ Covered |
| FR-10 | Propose-only handoff; exactly-once dispatch/apply; second confirm cannot execute | AD-3 (dispatch only on stored `confirmed`; exactly one executor call; second dispatch of same proposal rejected; re-dispatch = new proposal per PD-6); §1.11 executor contract; §3.7. **UX-06 double-apply guard only implicit → MEDIUM-2** | ⚠️ Partial (gap: UX-06 citation) |
| FR-11 | Tool-call audit; append-only; exactly one row per call; retention/redaction | §1.8 Audit Writer/Store; AD-10 (append-only trigger, redaction at write, retention rotation, 1:1 ToolCall↔AuditRecord) | ✅ Covered |
| FR-12 | State inspection viewer, field-for-field | §3.2 `/api/v1/state/{entity_type}/{id}` + browse; AD-1; console S-B per §1.1 | ✅ Covered |
| FR-13 | Citation & evidence integrity | AD-8 (every Claim ≥1 resolvable citation; broken citation downgrades; citation coverage = data check) | ✅ Covered |
| FR-14 | Determinism (evidence/citation/class/steps) | AD-2 (deterministic EvidenceSet + pure diagnosers; LLM once per answer, prose-only; 3× determinism test) | ✅ Covered |
| FR-15 | Untrusted input/retrieved-content data-hygiene | AD-11 (data-object serialization, bounded rendering, injection corpus with parity assertions) | ✅ Covered |
| FR-16 | Safe failure on degraded dependencies | AD-12 (typed results, abort-before-prose, literal degraded responses, fault-injection per class) | ✅ Covered |

| ID | NFR (abridged metric) | Architecture coverage | Status |
|---|---|---|---|
| NFR-1 | Diagnosis accuracy 100% fixtures / ≥90% corpus | Design enables it (AD-2); accuracy is a test target, not arch surface. No contradiction | ✅ Covered (test-level) |
| NFR-2 | Anti-fabrication, 0 fabricated, 100% Entity-Not-Found | AD-7 + AD-8 + AD-12 canonical responses | ✅ Covered |
| NFR-3 | Citation integrity 100% | AD-8 | ✅ Covered |
| NFR-4 | Determinism 3× identity | AD-2 | ✅ Covered |
| NFR-5 | Latency p95 ≤3 s answer / ≤5 s runbook / p99 ≤8 s | **No allocation.** Single-process sync REST + one local Ollama, no streaming, no cache/queue (§3, Stack §"No queue, broker, or cache"). Tension un-flagged in Open Decisions → **HIGH-1** | ❌ Gap |
| NFR-6 | Concurrency ≥5 sessions; ≥50 q/h | No concurrency model; single Ollama instance likely serializes concurrent LLM requests → **HIGH-1** | ❌ Gap |
| NFR-7 | Availability ≥99%/8 h; cold-start ≤60 s; 0 hard crashes | Crash-free covered (AD-12); cold-start vs. local Ollama model-load and 99%/8 h unaddressed → **HIGH-1** | ❌ Gap |
| NFR-8 | Safety: 0 copilot mutations; refuse+dry-run+confirm; audit 100% | AD-1, AD-3, AD-4, AD-10; "0 copilot-originated writes across scenario suite" asserted | ✅ Covered |
| NFR-9 | Usability ≥90% end-to-end <5 min | Delegated to console (S-A..S-D, answer chain, canonical strings verbatim, keyboard-first) bound via §1.1 + frontmatter UX sources | ✅ Covered (delegated) |
| NFR-10 | Extensibility: entity ≤1 dev-day no console change; runbook config-only | AD-13 (port surface is the extension path, C-4); console is a generic bounded renderer; Runbook Registry config-driven | ✅ Covered |
| NFR-11 | Security/privacy of logging; retention cap; no state-mutating control; no PII | AD-10 (redaction, retention rotation, audit API no update/delete); AD-1/AD-13 (no mutating control surface) | ✅ Covered |

**FR/NFR tally:** 16/16 FRs — 14 fully covered, FR-02 and FR-10 partial (quiet edges below). 11 NFRs — 8 covered, 3 gaps (NFR-5/6/7, all the same root: unallocated non-functional budget).

## 2. Quiet-Requirement Check (S / C / A / D / UX)

| Ref | Requirement | Architecture honor | Status |
|---|---|---|---|
| S-1 | Destructive → refuse/dry-run/confirm/propose-only, never auto-execute | AD-4, AD-3 | ✅ |
| S-2 | Two canonical responses; never fabricate | AD-7, AD-8 | ✅ |
| S-3 | Uncertainty → state it and offer escalation | `Cannot confirm` copy present (AD-8); **escalation affordance absent from arch and UX artifacts alike** (PRD-only today) | ⚠️ Low |
| S-4 | Runbooks only from registered templates | AD-9 | ✅ |
| S-5 | Audit append-only, no secrets | AD-10 | ✅ |
| S-6 | No console control mutates state | AD-1, §1.1, AD-13 | ✅ |
| S-7 | Content is data, not instructions | AD-11 | ✅ |
| S-8 | Fail safe on dependency failure | AD-12 | ✅ |
| C-1..C-8 | Read-only / deterministic LLM / facts retrieved / contract extension / standalone / executor schema / data-hygiene / procedural gate | AD-1, AD-2, AD-2/AD-8, AD-13, §1.10, §3.7, AD-11, AD-5 — one-to-one | ✅ |
| A-1..A-16 | Assumptions | A-1→OQ-1 open ✓; A-2/3→AD-1/ports ✓; A-4→AD-3 ✓; A-5/11→AD-2 ✓; A-6→D5 ✓; A-7→D6/§2 ✓; A-10→Deferred PD-5 ✓; A-12→stack Ollama-local ✓; A-13→AD-5 ✓; A-15→**NFR-6 gap**; A-16→AD-11 ✓ | ✅ (A-15 tied to HIGH-1) |
| D1..D15 | Phase 1 + adversarial spine | AD-1..AD-13 bind D1..D15 + PD-1..PD-5; D8 renumber honored (`binds: FR-01..FR-16`) | ✅ |
| D16–D22 | UX adversarial decisions | D17 surface ownership consistent (§1.1 + topology: inline flow + modal); D22 answer-chain label — arch names no stages, no conflict; D16/D18/D20/D21 are UX-artifact-level, correctly delegated to console per frontmatter sources | ✅ |
| UX-01 | Dry-run never opens on unresolved target | AD-4 rule verbatim; §1.9; §3.6 | ✅ |
| UX-02 | Empty dry-run disables confirmation | AD-4; AD-6 (non-empty snapshot required) | ✅ |
| UX-03 | Stale-snapshot re-validation → re-rendered dry-run | AD-6 (re-query + delta + dispatch only on equal sets) | ✅ |
| UX-04 | Compound-with-destructive → clarification | AD-4; §1.3 | ✅ |
| UX-05 | Confirm gate provider-independent; executor-down preserves proposal | AD-5 has no LLM dependency, but **UX-05 not cited in any bind list; "requires no LLM/provider" guarantee unstated; AD-6 re-validation hard-depends on the job provider at confirm time and AD-12 aborts on failure → tension** → **MEDIUM-1** | ⚠️ Partial |
| UX-06 | Double-apply surfaces as executor-failure, never second success | Supported implicitly via `Proposal.executor_result.applied_count` + §4.3 "applied N of M"; **UX-06 not bound/cited in any AD** → **MEDIUM-2** | ⚠️ Partial |
| UX-07 | Open dialog blocks session/rail nav | Bound in AD-4 bind list; delegated to console | ✅ |
| UX-08 | Session reset mid-flow: cancel in-flight; destructive flow returns to refusal/dry-run, never auto-continues | **No component, AD, route, or §1.7 reset semantics address an in-progress safety flow across reset** → **HIGH-2** | ❌ Gap |
| UX-09/10 | Audit redaction explicit; empty-audit state | AD-10; console S-C | ✅ |
| UX-11 | Clock failure → no fabricated window | AD-12 (clock failure class) | ✅ |
| UX-12/25 | Broken citation downgrades; degraded answers render no populated Evidence/Diagnosis | AD-8; §2.2 `answer_chain` (reached stages) | ✅ |
| UX-13 | Retrieved content not auto-linked/executable | AD-11 | ✅ |
| UX-14 | Runbook w/o approved-source → unavailability | AD-9 | ✅ |
| UX-17 | Typo tolerance deferred | Deferred table (PD-3/OQ-9) | ✅ (deferred, correct) |
| UX-18..22 | Boundary contradictions flagged, not expanded | UX-21 bound (§2.1 "read-only (UX-21)"); AD-13 covers the rest | ✅ |
| UX-23 | Runbook code-mismatch | AD-9 | ✅ |
| UX-24 | No window when unconstrained | FR-05 + PD-9 open decision | ✅ |
| UX-26 | Confirm disabled during re-validation | Bound in AD-4/AD-6; delegated to console | ✅ |
| UX-27/28/29/30 | Tone, focus trap, audit paging cap, dead citation affordance | AD-10 paging cap; AD-8 dead-citation; tone/focus are console-level, delegated | ✅ |

**Quiet-requirement tally:** S-1..S-8 ✅ (S-3 escalation low), C-1..C-8 ✅, A-1..A-16 ✅ (A-15 tied to HIGH-1), D1..D22 ✅, UX-01..UX-30 → 3 flagged (UX-05 partial, UX-06 partial, UX-08 gap); the rest covered or correctly delegated to the console per the bound UX artifacts.

## 3. Scope-Change & Open-Decision Audit

The architecture does **not** silently change PRD scope: read-only/propose-only/no-control-plane boundaries (AD-1/AD-3/AD-13) match §2.2/§2.4/§16; the Deferred table correctly parks GPU abstractions, real-subsystem swap, admin identity, fixture values, retention/session values, typo-tolerance. No Phase 1/2 decision is contradicted. Four issues for the record:

- **PD-6 (re-dispatch) was a PENDING decision** (lean only) and the architecture *resolves* it (route + AD-3: re-dispatch = new proposal, fresh dry-run + confirmation). The direction is the only one compatible with FR-10's exactly-once metric and is correct, but it is a silent resolution of a pending item — it should be recorded as resolved (or referenced from the Open section), not carried as a settled fact (MEDIUM-3).
- **Open Architectural Decisions section** lists OQ-1/D1, PD-9, OQ-11, OQ-3 — all legitimately open and correctly flagged. **Missing from it:** the NFR-5 latency/stack tension (HIGH-1) and the UX-08 reset-mid-flow semantics (HIGH-2) — both are exactly the "conflict that must be flagged as an open architectural decision, not silently assumed" case the gate brief demands.
- **NFR-5/6/7 vs. "No queue, broker, or cache product is used (AD/proportionality)" (Stack):** proportionality is a real constraint (C-5, A-12), but the synchronous single-process + one-Ollama shape *guarantees* an LLM serialization point for concurrent sessions, so the p95/p99 budget and 50-q/h concurrency are not free. A latency budget allocation (or an explicit deferral of NFR-5 to measurement, per OQ-8) must appear.
- **UX-05 vs. AD-6/AD-12:** the confirm gate is declared LLM-free (good) but the re-validation hard-requires the live job provider, so "a provider outage affects diagnosis stages only" is only partially true — a job-provider outage at confirm time will abort the gate under AD-12. The arch should carve this explicitly (re-validation failure = distinct "cannot re-validate" state), not leave it to inference.

## Findings

### Critical
- None. The spine-level invariants (read-only, propose-only exactly-once, ordered safety flow, evidence-level determinism, content hygiene, safe failure) all landed with machine-enforceable rules and test bindings; no FR/NFR load-bearing requirement is contradicted outright.

### High
- **HIGH-1 — NFR-5/6/7 have no architectural allocation and the latency/concurrency budget is in un-flagged tension with the single-process synchronous stack.** The Stack section (and §3 "no event bus, queue, or messaging infrastructure") commits to sync REST, one FastAPI process, one local Ollama, no cache/queue/streaming — yet NFR-5 (p95 ≤3 s / runbook ≤5 s / p99 ≤8 s), NFR-6 (≥5 sessions, ≥50 q/h), and NFR-7 cold-start ≤60 s + ≥99%/8 h are never mentioned, budgeted, or deferred. A concurrent LLM request to a single Ollama instance is a serialization point; cold model-load threatens NFR-7. Fix: allocate the budget (deterministic core ≈ free; dominant term = the one LLM call; state the margin) or flag NFR-5 as an open architectural decision (it is the gate-brief's explicit example). Location: `ARCHITECTURE.md` Stack + §3 + Open Architectural Decisions.
- **HIGH-2 — UX-08 (session reset mid-flow) is bound nowhere.** §1.7 defines reset as "clears it" (context) and AD-5 stops "session context never authorizes a destructive action," but nothing addresses an in-flight destructive flow across a reset: does reset orphan/preserve a confirmed proposal in the Proposal store, does S-D return to its refusal/dry-run stage, can a reset ever auto-continue a dispatch? UX-08's accepted resolution ("reset cancels in-flight requests; a destructive flow returns to its refusal/dry-run stage and never auto-continues") must be bound to a component (safety workflow / session store) or flagged open. Location: `ARCHITECTURE.md` §1.7 + AD-4 bind list (which cites UX-01/02/03/07/26 but not UX-08).

### Medium
- **MEDIUM-1 — UX-05 (provider-independent confirm gate) is only partially honored and conflicts at the margin with AD-6/AD-12.** The gate is procedurally LLM-free (AD-5), but UX-05 is absent from every AD bind list, the "requires no LLM/provider" guarantee is never stated, and AD-6's re-validation requires a live read of the job provider at confirm time — under AD-12 that abort is a *provider-dependent* failure of the gate, contradicting "a provider outage affects diagnosis stages only." Carve the re-validation failure into its own degraded state.
- **MEDIUM-2 — UX-06 (double-apply guard) is supported only implicitly.** `Proposal.executor_result.applied_count` and §4.3 "applied N of M" let the UI render a duplicate as failure, but AD-3's bind list omits UX-06 and no AD states the dispatch/result path cannot re-report a duplicate as success. Bind UX-06 in AD-3 (exactly-once is AD-3's own metric).
- **MEDIUM-3 — PD-6 was resolved silently.** The pending decision ("Re-dispatch vs. exactly-once") is adopted as settled (route `POST /destructive/proposals/{pid}/re-dispatches` "new proposal (fresh dry-run + confirmation), per PD-6") without recording that a pending item was decided. Direction is correct and forced by FR-10; record it (decision log or Open section note).

### Low
- **LOW-1 — S-3 escalation affordance is unimplemented at both arch and UX level.** `Cannot confirm` copy exists; "offer escalation" has no control/component anywhere. PRD→UX gap, surfaced here so it isn't lost.
- **LOW-2 — FR-01 input validation (UTF-8 ≤1,000 chars) and D16 composer-counter semantics are left implicit.** Reasonable to defer to the API/composer, but a one-line validation rule in §3.1 would pin D16's "never render a count above the cap."
- **LOW-3 — Frontmatter `binds:` reads "S1..S4"** which collides in name with safety rules S-1..S-8; it means scenarios S1..S4 (safe, per §15) but is ambiguous. Rename to `S1..S4 scenarios, S-1..S-8 rules` for clarity.
- **LOW-4 — No explicit statement that the LLM failure class in AD-12 covers a mid-confirmation provider outage** (overlaps MEDIUM-1; listed here as the naming of the specific carve-out).

## Open Architectural Decisions — Assessment

The section lists the right *classes* of genuinely open items (OQ-1 Annex overlap, PD-9 positive-schedule UI, OQ-11 runbook content owner, OQ-3 shared read API) and the Deferred table correctly parks the rest. It is **incomplete** for this gate: HIGH-1 (NFR-5 budget vs. sync stack) and HIGH-2 (UX-08 reset-mid-flow) are precisely the "conflict to flag, not silently assume" cases and are absent. Add both. Optionally add a "resolved here" note for PD-6.

## Coverage Summary

- FR-01..FR-16: 14/16 fully covered; FR-02 (UX-08), FR-10 (UX-06) partial.
- NFR-1..NFR-11: 8/11 covered; NFR-5/6/7 gap (HIGH-1).
- S-1..S-8, C-1..C-8, A-1..A-16, D1..D22: all honored (S-3 low; A-15 tied to HIGH-1).
- UX-01..UX-30: 27/30 honored or correctly delegated; UX-08 gap (HIGH-2), UX-05 (MEDIUM-1), UX-06 (MEDIUM-2).
- Scope integrity: no silent scope change; Open Decisions section needs the two HIGH items added.