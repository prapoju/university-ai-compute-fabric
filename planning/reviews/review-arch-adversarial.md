---
type: review
reviewer: adversarial-general (cynical)
target: ARCHITECTURE.md (Module 12 — AI Operations Copilot, feature altitude, final)
sources-read:
  - ARCHITECTURE.md (final, full)
  - prd.md (FR-01..FR-16, NFR-1..NFR-11, §7.1.1 taxonomy, C-1..C-8)
  - EXPERIENCE.md / DESIGN.md (Safety & Confirmation Model, answer anatomy, citation behavior)
  - C-UX-Scenarios/01 (S1 evidence chips), VALIDATION.md
date: 2026-09-27
verdict: disciplined spine, but a layer of interface and enforcement gaps the AD blocks do not reach
---

# Adversarial Review (General) — Finalized Module 12 Architecture

The document is unusually disciplined on the read-only / propose-only / determinism spine. That
discipline hides a layer of interface and enforcement gaps the AD blocks never touch. Findings
below, descriptions only, no severity, priority, or ranking.

- **Confirm and dispatch are fused in one route, defeating the ordered state machine.**
  `POST /api/v1/destructive/proposals` is documented as "procedural confirm + re-validate
  snapshot → confirmed proposal (**and dispatch**)" (§3.6). AD-4 and the UX both require
  `confirmed` to be a distinct, observable stage that the delegation card renders as a
  `Copilot proposal` line *before* the executor result (EXPERIENCE / Wireframe 02). With
  confirm+dispatch in one HTTP call, `confirmed` is a transient internal state, the proposal is
  never materialized for the operator, and the UJ-4 "a second confirm can still only dispatch"
  edge has no place to live. The API needs a separate `confirm` and a separate `dispatch` route
  (or a confirmed-but-not-yet-dispatched state that survives a round trip).

- **How a destructive query reaches the safety flow is unwired.** The composer submits to
  `POST /sessions/{sid}/queries`; the safety flow lives under `/destructive/*`. Nothing says
  whether a destructive query is rejected by `/queries` and then re-submitted to
  `/destructive/dry-runs`, or routed internally, or whether `/queries` itself spawns the
  dry-run. Two valid call sequences exist and the S4 audit sequence (refusal → dry-run →
  confirm → handoff) is never mapped to HTTP calls.

- **AD-10 contradicts itself on rotation.** The Audit Store "denies update and delete (enforced
  by a SQLite trigger)" yet "the log honors a configured retention cap by rotating the oldest
  entries first" — rotation is a DELETE. Either the rotation path is exempt from the trigger
  (unstated, and then the append-only guarantee has a hole anyone can widen) or rotation is
  impossible under the stated trigger. One of them has to give, and the document does not say
  which.

- **The clock read makes FR-14 determinism vacuous.** AD-2 now lists "clock read" as a bound
  determinism input. But a clock read is by definition not identical across the three FR-14
  runs — so "identical inputs" can never hold and the invariant becomes untestable. The fixture
  must freeze the clock for the determinism test; the document asserts the input without
  stating the freeze.

- **The clock citation is un-inspectable.** AD-14 makes clock reads citable as `clock#<read_id>`,
  but `clock` is absent from the canonical entity-type enum (§3, AD-13) and has no
  `GET /api/v1/state/clock/{id}` route. FR-13 and the UX require every citation card to open
  its source record in the Inspector. A `clock#` citation resolves to nothing addressable — the
  citation-click contract breaks on the S2 fixture's first-class window fact.

- **The citation vocabulary was renamed under the scenarios.** Scenario 01's evidence chips are
  `[S1:model#deepseek-coder]`, but the canonical enum replaced `models` with `catalog`
  (AD-13, §3). Either the scenario citations or the enum is wrong; a corpus built against the
  scenario chips will not match the addressable vocabulary.

- **NFR-6 and NFR-5 are never budgeted together.** Ollama serializes prose (default
  `OLLAMA_NUM_PARALLEL=1`). Five concurrent sessions each making a synchronous prose call means
  requests 2–5 queue behind request 1; at any realistic local-model token rate that collides
  with the p99 ≤ 8 s ceiling. §1.12 claims "FastAPI async handles ≥ 5 concurrent sessions" as
  if the bottleneck were the web framework. It is not, and nothing budgets the LLM
  serialization.

- **"Not on the critical path for evidence assembly" dodges the actual metric.** NFR-5's
  p95 ≤ 3 s is submit → *rendered cited answer* — which includes prose. The prose call is
  squarely on the user-perceived critical path; the sentence reassures about the fast part and
  ignores the part that fails the budget.

- **The executor gate-token validation is circular.** AD-15 requires the executor to "validate"
  the gate token, but the executor is a separate component with no write handle and (per the
  doc) no stated read handle to the Proposal store, and no shared secret is defined. The token
  can only be (a) trusted from the payload — defeating "prove the gate happened" — or
  (b) verified against a mechanism that is never specified.

- **Re-render after a scope delta leaves token/snapshot binding undefined.** When re-validation
  finds a delta, the gate "returns a re-rendered dry-run." Is that a new snapshot with a new
  gate token (invalidating the old confirm), or the same proposal re-rendered? AD-6 and AD-15
  are silent; a builder can either rotate the token (breaking the in-flight confirm) or keep it
  (allowing confirmation against a re-rendered list that was never re-validated).

- **The decomposed compound-query envelope is never fixed.** FR-01 allows a compound query to
  decompose into "two independently validated, cited answers." `POST /queries` returns "Answer
  resource" — one Answer with two diagnosis blocks, or two Answer resources, is unstated. L-1's
  per-sub-query pipeline runs are asserted but the API shape they produce is not.

- **A destructive turn has no resource representation.** The refusal + dry-run + delegation
  render as banner/panel/card, not answer anatomy. AD-3 says destructive turns are "recorded in
  session context like any other turn," but the doc never says whether a destructive turn is an
  Answer, a Proposal, or a separate turn type — and the audit mapping (which rows belong to it)
  follows from nothing.

- **Policy precedence between `allowed_roles[]` and the clause is undefined.**
  `ModelCatalogEntry` carries `allowed_roles[]` and `AccessPolicyClause` carries
  `rule`/`reason_class`. If they disagree (allowlist says ok, clause denies), the S1 diagnoser
  must pick one — and the 100% fixture-accuracy claim silently depends on that choice. No
  precedence rule exists.

- **`operator_role` is not NFR-11's "operator id (synthetic role id)."** The Session and audit
  carry `operator_role`; NFR-11 requires an *id* so operators are attributable. Two concurrent
  Nadia-class operators collapse to the same role and the audit trail cannot distinguish them —
  exactly the case A-15/NFR-6 says is in scope.

- **Request validation has no enforcement home.** The 1,000-char cap, UTF-8, non-empty, and
  malformed-input handling (FR-01, NFR-7 "0 hard crashes") are never allocated to a component
  or middleware. The console enforces a live count, but nothing in the API contract says the
  server validates; a builder who trusts the client ships an NFR-7 failure.

- **Prompt Assembly is bound but does not exist.** AD-11 binds "prompt assembly," yet the
  component topology (§1) and the structural seed (§Structural Seed) contain no prompt-assembly
  node. A builder cannot locate the very component the injection-parity invariant is stated
  against.

- **`GET /executor/v1/proposals/{pid}` is a dead contract.** The audit writer records the
  executor result from the POST response; no diagram or flow calls the GET. Either it is the
  status-poll path for re-dispatch (needs wiring) or it should be cut.

- **Sessions are uncapped while the audit is capped.** AD-10 caps and rotates the audit log;
  nothing bounds Session rows, and OQ-13 (session retention) is deferred. A single-process
  SQLite store with unbounded sessions and no expiry contradicts the "bounded prototype"
  posture everywhere else.

---

## Triage (added 2026-10-16)

This review targeted the 2026-09-27 architecture, which has since been superseded by the
2026-10-16 rewrite (`planning/ARCHITECTURE.md`, AD-1..AD-15). **Resolution** names where each
finding now lives. No separate `AD-16` batch was created; the material findings were folded into
`contracts.md` §0–§6, `dto.py`, `openapi.yaml`, and `001_module12_copilot_schema.sql` via
D52–D68, plus AD amendments.

| # | Finding (short) | Triage | Resolution | Fixed? |
|---|---|---|---|---|
| 1 | Confirm and dispatch fused in one route | Accept | D32/D47 · `contracts.md` §1 `confirm_and_dispatch` + AD-3/AD-4 materialized `confirmed` | ☑ |
| 2 | Destructive query path unwired | Accept | D55 · `contracts.md` §2 `POST /api/v1/destructive/dry-runs`; S4 sequence in `test/traceability-matrix.md` (FR-09) | ☑ |
| 3 | AD-10 rotation vs append-only trigger | Accept | D45/D66 · rotation is a single-writer path exempt from the delete trigger, logged | ☑ |
| 4 | Clock read makes FR-14 determinism vacuous | Accept | OP-10 `clock_port` freeze/advance; AD-2 amendment; `test-design.md` T-1 | ☑ |
| 5 | Clock citation un-inspectable | Accept | **OPEN** — no `GET /api/v1/state/clock/{id}` route; `test-design.md` T-11 / P0-G9 | ☐ |
| 6 | Citation vocabulary renamed (`models`→`catalog`) | Accept | D61 · `contracts.md` §0.2 entity-type enum owns the vocabulary | ☑ |
| 7 | NFR-6 and NFR-5 never budgeted together | Accept | D56 · one LLM budget; `contracts.md` §1 concurrency clause; NFR-6 bound to Story 1.2 | ☑ |
| 8 | "Not on the critical path" dodges the metric | Accept | D56 · budget measured submit→rendered; AD-2 amendment | ☑ |
| 9 | Executor gate-token validation circular | Accept | D47/D66 · `GateToken` + `proposals.gate_token` UNIQUE + shared read handle | ☑ |
| 10 | Re-render token/snapshot binding undefined | Accept | D47 · AD-6/AD-15 amendment (scope delta rotates token, disables confirm) | ☑ |
| 11 | Decomposed compound envelope never fixed | Accept | D54 · `AnswerEnvelope` (compound ⇒ `len(answers) ≥ 2`) | ☑ |
| 12 | Destructive turn has no resource representation | Accept | D55/AD-3 · destructive turn materialized as a `Proposal` resource (§2) | ☑ |
| 13 | Policy precedence `allowed_roles[]` vs clause undefined | Accept | `contracts.md` §1 `diagnose_access_denial` precedence (E10); AD-2 | ☑ |
| 14 | `operator_role` is not NFR-11's operator id | Accept | D66 · AD-10 amendment (`operator_role` synthetic id `^role-…`) | ☑ |
| 15 | Request validation has no enforcement home | Accept | D52/D64 · server-side validation in `contracts.md` §2 routes | ☑ |
| 16 | Prompt Assembly bound but does not exist | Accept | OP-14 `compose_prose_port` + `ComposeProse*` DTO; `ports-and-adapters.md` R1 | ☑ |
| 17 | `GET /executor/v1/proposals/{pid}` is a dead contract | Accept | AD-15 · wired as the status-poll path; trace FR-10 `test_executor_get_proposal_*` | ☑ |
| 18 | Sessions uncapped while audit capped | Accept (sessions) / Defer (answers) | D51/D66 · session expiry (`expired_at`) added; answer retention remains open → OQ-13 / `test-design.md` T-10 | ◐ |

**Summary:** 18 findings · 17 folded in · 1 open (clock-citation addressability, shared with
`review-arch-implementability.md` gap 21a) · answer-retention half deferred to OQ-13.