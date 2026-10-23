---
type: review
reviewer: rubric-walker
target: ARCHITECTURE.md (Module 12 — AI Operations Copilot, feature altitude)
sources-read:
  - prd.md (FR-01..FR-16, NFR-1..NFR-11, §15 scenarios)
  - ai-decision-log.md (D1..D22, PD-1..PD-9)
  - ux-plan-.../EXPERIENCE.md, DESIGN.md, SPECIFICATIONS.md, VALIDATION.md, review-ux-edge-cases.md (UX-01..UX-30)
date: 2026-09-27
verdict: PASS-WITH-CONDITIONS
---

# Rubric-Walker Review — GOOD-SPINE CHECKLIST

## Gate verdict

**PASS-WITH-CONDITIONS** — the spine decisively fixes the safety/determinism/read-only divergence points and its named tech is verified current, but it ships a silent operational/environmental envelope (NFR-5/6/7), a real contradiction with PRD FR-02 follow-up resolution inside AD-7, and an undecided entity-extension path (NFR-10) that must be closed before story decomposition.

---

## CRITICAL

### C-1. The operational/environmental envelope is silent (checklist #6, #5)

**What:** The spine decides topology ("one process + one SPA", §0/§1.2, lines 31–35, 124) and infra/provider posture ("standalone, offline, no external cluster", §1.10 line 159, C-5/A-12), but the rest of the envelope is absent: no deployment & environments section, no operations story, and no concurrency/persistence strategy. Specifically **bound but never decided, deferred, or flagged open**:

- **NFR-5 latency (p95 ≤ 3 s cited answer, ≤ 5 s runbook):** not addressed, not deferred; PRD OQ-8 ("measure latency feasibility on chosen LLM runtime") is not carried into the architecture even though the doc pins the local Ollama runtime.
- **NFR-6 concurrency (≥ 5 concurrent sessions, ≥ 50 queries/hr):** no threading/async model for the single FastAPI process, no SQLite write-contention strategy (WAL/connection mode) even though sessions, evidence, proposals, and audit all write to SQLite on the one process.
- **NFR-7 cold-start recovery ≤ 60 s:** never mentioned. AD-12 covers graceful *in-flight* failure but nothing covers process start/seed/recovery.
- **Operations:** where SQLite files live, how fixtures seed on first start, how a demo/run is started, whether a restart re-seeds or persists state — all silent. The Deferred table explicitly punts "Session retention window / context lifetime (OQ-13)" to "Prototype config," but even that config location is undefined.

**Where:** no dedicated section; bound in frontmatter line 10 (`binds: … NFR-1..NFR-11`); latent in Stack (lines 572–587) and §1.10.

**Why it matters:** two story teams will diverge on process/async model, SQLite mode, and seed/reset semantics — and the NFR-5/6/7 measurements the evaluator runs have no architectural owner.

**Fix:** add a short "Deployment & Operations" section (or fold into Stack): single local environment, one FastAPI process (state the async model), SQLite in a documented path with WAL noted, fixtures seeded at first start, cold-start ≤ 60 s accepted as a design target, and an explicit "deferred to build" for anything left (e.g., exact retention cap values). Carry OQ-8 as an open item tied to NFR-5.

### C-2. AD-7 contradicts PRD FR-02 on follow-up (session-context) resolution (checklist #1, #5)

**What:** PRD FR-02 (prd.md lines 139–144) requires follow-up references to "resolve against session context first, then against state via FR-03," with a measurable bar (≥ 95% of follow-up references resolve). The spine's resolver does no such thing: §1.3 (line 129) says the Query Planner + Entity Resolver "extracts entity references and resolves them by exact id against the read-only provider index," and AD-7 (lines 480–490) rules "The resolver matches each extracted reference by exact id against the provider index. Any unresolved reference yields the literal response `Entity Not Found in State`." Session context is only mentioned in §1.7 (line 147) to say it "never authorizes a destructive action." So a follow-up like "and what about that node?" (context-referential) is architecturally guaranteed to return Entity-Not-Found, failing FR-02's own test condition.

**Where:** §1.3 line 129, §1.7 line 147, AD-7 lines 480–490; contradicts prd.md FR-02 (lines 139–144); the Deferred row (line 637) claims "FR-02 semantics already enforced," which this gap falsifies.

**Fix:** extend AD-7's Rule to a two-stage lookup — resolve context-referential references against the session's resolved-entity index first, then exact-id against the provider index — bind the Session store into AD-7, and update §1.3's description and the Deferred note. Determinism inputs in AD-2 (line 428) should list "session context" as a bound input since resolution order now depends on it.

---

## HIGH

### H-1. NFR-10 entity-extension path is claimed but never designed (checklist #5, #1)

**What:** NFR-10 promises "adding a new entity type to the state model ≤ 1 dev-day with no console change; adding a runbook template is config-only." The spine cites C-4/D6 in §1.4 (line 133) and AD-13 (lines 552–562), and AD-13 rules that "adding a capability beyond this surface is a PRD-scope change." But no mechanism is specified for how a new entity type enters the provider index, gains a port method, gets fixtures, appears in the console quick-nav, or hits the 1-dev-day bar. As written, AD-13's "fixed port surface" reading can be read to *forbid* the very extension NFR-10 promises, leaving teams to guess.

**Where:** §1.4 line 133, AD-13 lines 552–562, Deferred rows lines 633–639 (none cover the extension path); NFR-10 in prd.md line 332, D6/C-4 in prd.md lines 107–115, 385.

**Fix:** add one AD or a subsection "Entity-extension path": new entity type = add provider port method + fixture + index registration + left-rail entry; template addition = config-only registry insert (FR-08). Reconcile AD-13's "fixed port surface" wording so a *new entity type* is an NFR-10-style extension while a *control-plane method* stays a PRD-scope change.

### H-2. Executor double-apply (UX-06) has no architectural representation (checklist #5, #2)

**What:** UX-06 (review-ux-edge-cases.md lines 51–55) requires a second executor-applied record to surface as executor-failure, never success. The spine enforces the *copilot* side (AD-3: one dispatch per confirmed proposal) but the data model cannot represent a double-apply: `Proposal.executor_result` is a single record (§2.2 line 215), and AD-10 (lines 516–526) logs "every executor-applied mutation" as `AuditRecord` 1:1 with a `ToolCall` *or* an executor mutation — there is no cardinality or rule for a second applied record on the same proposal.

**Where:** §2.2 line 215 (`executor_result`), §1.8 line 151, AD-10 lines 516–526, AD-3 lines 432–442.

**Fix:** state the invariant at the audit/proposal layer: the Proposal store records at most one applied result; a duplicate executor-applied event (matching `proposal_id` + `actor=executor`) is written as an executor-failure audit row and never updates the proposal to a second success. This makes UX-06 machine-enforceable.

### H-3. Audit coverage of the safety-flow steps is ambiguous (checklist #1, #2)

**What:** AD-10's rule is "exactly one audit record is written per copilot tool call," and §1.8 says "one append-only row per copilot tool call." But FR-09's measurable condition (5) and the spine's own sequence 4.3 (line 384) audit "refusal, dry-run, confirmation, handoff, executor result." Refusal, dry-run-build, and confirmation are state-machine events, not obviously "tool calls," so it is underspecified whether they are audited as `ToolCall` rows (`tool_name = guardrail.refuse`, etc.) or only visible via the Proposal record.

**Where:** §1.8 line 151, AD-10 lines 516–526, §2.2 lines 213–214, sequence 4.3 line 384; FR-09 in prd.md line 235.

**Fix:** define the audit surface explicitly: every safety step is a `ToolCall` row (refuse / dry-run / confirm / dispatch), plus the executor mutation row with `actor=executor`. One line in AD-10 resolves the ambiguity.

---

## MEDIUM

- **M-1 — TypeScript "5.x" is not current at authoring (checklist #4).** The Stack table (line 581) claims "verified current at authoring (2026-09-27)"; TS 6.0 is the current major (5.9 was the last 5.x). Fix: pin `TypeScript 6.x` or state `5.x (≤ 5.9)` explicitly. All other pins verified: FastAPI 0.141.x ✓, Vite 8.x ✓, Ollama 0.34.x ✓, Python 3.11.15 ✓ (note 3.11 is security-only/maintenance until Oct 2027), React 19.x ✓.
- **M-2 — ER diagram cardinality is backwards for claims↔evidence (checklist #7).** Line 184 `CLAIM }o--|| EVIDENCE : cited_by` says "many claims are cited by one evidence," but the model has `Evidence.claim_id` as a single FK — each evidence row belongs to exactly one claim, and a claim cites many evidences. Fix: `CLAIM ||--o{ EVIDENCE : cites` (and keep `ANSWER ||--o{ EVIDENCE : cites` for the answer attribution). Syntactically the four Mermaid blocks (flowchart LR/TD, 2× sequenceDiagram, erDiagram) are otherwise well-formed.
- **M-3 — AD-2's "LLM invoked exactly once per answer" conflicts with the classifier's LLM-assist (checklist #2).** §1.3 (line 128) allows an LLM-assist for ambiguous clarification; AD-2 (line 428) says the LLM is "invoked exactly once per answer." An ambiguous query could hit the LLM at classification *and* at prose. Fix: scope the invariant to the answer path ("exactly one prose invocation per answered query; clarification-assist is a separate, non-factual call") so the FR-14 test doesn't guard a false invariant.
- **M-4 — NFR-1 (diagnosis accuracy, 100%/≥90%) has no architectural owner (checklist #5).** AD-2/AD-7/AD-9 give the structure determinism and anti-fabrication rely on, but nothing says how accuracy is evaluated architecturally (fixture corpus is the PRD's). Acceptable to leave, but because it is bound in the frontmatter it should at least be named as a validation-domain concern rather than silent.

---

## LOW

- **L-1 — EXPERIENCE.md:33 (a cited source) still carries the D17-contradicting line** ("Destructive flow never lives on the Console surface itself — it always moves to the Confirmation surface"), while D17 (decision log lines 303–318) corrected it to "confirmation dialog is a distinct surface; the surrounding safety flow renders inline." The architecture cites EXPERIENCE.md (line 14) and is silent on placement. Fix: AD-4 or §1.1 should ratify D17 explicitly (refusal/dry-run/delegation render inline on the console thread; only the confirmation is a distinct dialog) so the build doesn't resurrect the IA contradiction.
- **L-2 — AD-5's "gate token" is undefined** (line 464: confirmation payload "contains only a proposal reference and a gate token"). No issuer or validation rule is given. Since AD-5 accepts anyone-with-console-access may confirm, simplest fix: define it as an opaque token returned by the dry-run response and echoed on confirm (or drop the term).
- **L-3 — D16–D22 are bound collectively, not traced** (line 406). Only D17 is architecturally load-bearing; the rest are UI/process. Acceptable, but one sentence mapping D17 → AD-4/§1.1 (see L-1) and noting the rest are UI-domain would make the claim honest.

---

## Checklist quick-score

| # | Check | Verdict |
|---|---|---|
| 1 | Fixes real divergence points for level below | ✅ strong on safety/determinism; ❌ FR-02 follow-up (C-2), entity-extension (H-1), audit surface (H-3) |
| 2 | Every AD rule enforceable & prevents its divergence | ✅ mostly; ⚠ AD-2 exactly-once (M-3), AD-5 gate token (L-2), double-apply (H-2) |
| 3 | Nothing under Deferred lets units diverge | ✅ none of the 7 deferred rows is a live divergence risk |
| 4 | Named tech verified-current | ✅ FastAPI/Vite/Ollama/Python/React; ⚠ TypeScript (M-1) |
| 5 | Ratifies PRD/UX (FR/NFR/D/UX coverage) | ⚠ FRs all mapped (FR-02 gapped); NFR-5/6/7/10/1 silent (C-1, H-1, M-4); D17 unratified (L-1); UX-01..30 mapped, UX-06 unrepresented (H-2) |
| 6 | No dimension left silent | ❌ operational/environmental envelope silent (C-1) |
| 7 | Mermaid syntax + structure | ✅ syntactically valid; ⚠ ER cardinality (M-2) |

**Coverage matrix (bound set):** FR-01..16 — 16/16 mapped, FR-02 partially. NFR-2/3/4/8/11 ✓; NFR-5/6/10 ✗; NFR-7 partial; NFR-1 unowned; NFR-9 UI-domain. D1–D15 ✓; D16–D22 collective only. UX-01–05/07/09/11–14/17–23/25/26/29/30 ✓; UX-06 ✗ (H-2); UX-08/10/15/16/24/27/28 UI-domain.