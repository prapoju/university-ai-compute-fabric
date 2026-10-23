---
type: review
reviewer: adversarial-divergence-hunter
target: ARCHITECTURE.md (Module 12 — AI Operations Copilot, feature altitude)
sources-read:
  - ARCHITECTURE.md (full, AD-1..AD-13, §1 topology, §2 data model, §3 contracts, §4.3 flow, Consistency Conventions)
  - prd.md (FR-01..FR-16, NFR-1..NFR-11, §7.1.1 taxonomy, §13 safety, C-1..C-8)
  - ai-decision-log.md (D1..D22, PD-1..PD-9)
  - ux-plan-.../EXPERIENCE.md (Safety & Confirmation Model, Component Patterns, State Patterns)
date: 2026-09-28
verdict: FAIL-WITH-REVIEW — five unfrozen shared data shapes guarantee two-team divergence
---

# Adversarial Divergence-Hunter Review — pairs that obey every AD yet build incompatibly

## Method

For each finding, I construct **two units one level down** (team, component, or subsystem pair).
Each unit obeys **every AD-1..AD-13 and every stated contract to the letter**. I then show the
two units cannot be joined without rework. The closing AD is the exact new/amended rule that
forces them onto one shape.

Not an honesty review — an **interface-fidelity** review. The spine is unusually strong on
*rules that say what not to do*; it is weak on *freezing the shapes of the data that crosses
team boundaries*. Almost every critical finding is a "the schema is the replacement point" or
"verbatim" or "structured Claim" claim with no frozen definition underneath it.

---

## VERDICT

**The spine will diverge on five unfrozen shared data shapes — the citation/evidence identity
model, the executor contract schema, the affected-items selector and delta semantics, the
canonical-string and exact-id normalization contract, and the prose/citation-coverage
boundary — so two teams that each obey AD-1..AD-13 will produce incompatible builds that
cannot be merged without changing one team's contracts (and in two cases, a safety-critical
confirmation gate or a citation-integrity claim silently fails).**

---

## CRITICAL

### C-1. The Claim↔Evidence↔EvidenceSet citation identity is two different data models

**Pair:** the Claim/EvidenceSet emitter (deterministic core, §1.5) + evidence renderer, versus
the evidence persistence layer + `GET /api/v1/answers/{aid}/evidence` / `GET /api/v1/citations/{cid}`.

**The divergence.** The schema (§2.2) and ER (line 184) are self-contradictory and each team
resolves the contradiction differently:

- `Evidence` has a single FK column `claim_id` (line 211) → each Evidence row belongs to exactly
  one claim.
- `Claim` has `citation_ids[]` (line 212) → one claim cites many sources.
- ER line 184 says `CLAIM }o--|| EVIDENCE : cited_by` → *many* claims cite *one* evidence row.

Team A reads "many claims cite one evidence": a citation is a **unique** `(source_type,
source_id, snippet)` entry per answer, shared across claims; `Claim.citation_ids[]` references
it; the EvidenceSet returned by `GET /evidence` is the **unique set of sources** for the answer.
The `claim_id` column is a denormalized back-pointer (or dropped).

Team B reads the single `claim_id` FK as authoritative: **one Evidence row per (claim, source)
pair**; a claim citing three sources produces three Evidence rows; the EvidenceSet is the
**ordered list of (claim, citation) pairs**, possibly with the same source appearing once per
claim.

Both satisfy AD-8's rule ("every factual claim carries ≥ 1 `citation_id` that resolves to an
entry in the answer's EvidenceSet") — each team's EvidenceSet *contains* the other team's
citations, just shaped differently. Both pass the FR-13 data check and AD-2's determinism test
("identical evidence set") because "the set" is defined by each team's own model. The outputs
are structurally incompatible: the renderer, the evidence API, and the citation API
(`GET /citations/{cid}` — keyed on `citation_id`, which is itself ambiguous: is the id
`policy#catalog.4.2` the *source id* or a per-answer *citation instance id*? "All IDs are stable
strings matching the citation vocabulary" (§2) says source id; "citation_id" column says
instance).

**Closing AD — amend AD-8 (or add AD-14, "Citation identity"):** pin one model. Recommended:
`citation_id` is a stable **source** reference (`{type}#{id}`, the citation vocabulary of §2);
the EvidenceSet is a **unique, ordered set of sources** per answer (UNIQUE constraint on
`(answer_id, citation_id)`); claims bind to sources via a `claim_citations` join table, never a
single FK column; `Evidence.claim_id` is removed; the evidence API and citation API are defined
over source-level citations. State the ER cardinality correctly (`CLAIM }o--o{ EVIDENCE : cites`).
Also state that a source cited twice is rendered once with both claims' chips.

### C-2. The executor contract is declared "the replacement point" but has no schema — the dispatch payload and confirmation credential are free

**Pair:** the Proposal Dispatcher + executor port (application ring, §1.9/§1.11) versus the
simulated/real executor adapter (§1.10/§3.7).

**The divergence.** AD-3 guarantees "one executor call per confirmed proposal," AD-4 guarantees
"only on stored `confirmed` state," AD-6 guarantees "snapshot re-validated." But the **bytes
sent to the executor are never defined**. §1.11 (line 163) and §3.7 (line 272) say "the schema
is the replacement point" — i.e., they hand the schema to the two teams as homework. C-6 says
"the propose-only handoff schema must match the (simulated) executor contract" — but neither
schema exists in the document.

Team A defines the payload as a **re-projection of the Proposal row**: `{proposal_id,
affected_items, action: "delete_pending_jobs", targets: [job ids], confirmation: {confirmed_at,
gate_marker}}`.

Team B defines the payload as a **criteria-based instruction**: `{action: "delete_jobs",
selector: {group: "CS201", status: "pending"}}` and lets the executor re-enumerate the affected
set itself.

Both obey AD-3/4/6 to the letter. But the executor contract is the single most load-bearing
boundary in the system — the swap point for the real job-control subsystem — and AD-13 binds
"the API route table," yet nothing freezes the payload. Team A's executor trusts a snapshot;
Team B's executor re-resolves state, which silently **shifts the dry-run scope decision from
the Dry-Run Builder to the executor** (see C-3). Additionally, the confirmation credential is
unowned: AD-5 mentions a "gate token" but does not say it is passed to the executor, so Team A
sends the gate token and the executor validates it; Team B sends nothing (executor trusts the
caller). One executor "applies the mutation only after the confirmation gate" (FR-10); the
other cannot prove the gate happened.

**Closing AD — add AD-15, "Executor contract is frozen, not a replacement point":** pin the
exact JSON schema of `POST /executor/v1/proposals` — fields, types, and that it carries
`proposal_id`, a closed-verb `action`, the **persisted selector** (C-3), the confirmation
credential (gate token from AD-5, forwarded verbatim), and references the dry-run snapshot by
`proposal_id` (the executor must NOT re-enumerate the affected set). Pin the response shape
(`status`, `applied_count`, per-item results, `timestamp`). State that the "replacement point"
is the *adapter implementation*, never the contract.

### C-3. "Re-query the affected-item set" is unexecutable — the selector that defined the set is never persisted, and the delta semantics are undefined

**Pair:** the Dry-Run Builder (AD-6 first half) versus the Confirmation Gate (AD-6 second half).

**The divergence.** AD-6's Rule says "At confirmation time the server re-queries the
affected-item set from the read-only job provider and compares it to the dry-run snapshot."
But the `Proposal.dry_run_snapshot` stores **only `affected_items[]` and `snapshot_timestamp`**
(line 215). It does **not** store the **selection predicate** that produced the list (the
selector `{group: CS201, status: pending}` from "delete all pending jobs for CS201"). The
Confirmation Gate therefore cannot know *what to re-query*.

Team A re-derives the predicate at confirm time by re-parsing the intent + target from the
parent `Answer.query`/`intent` (the only other place the target lives).

Team B has the Dry-Run Builder persist the selector inside the snapshot (`selector: {status:
pending, group_id: CS201}`) and the Gate re-executes the stored selector.

Both literally "re-query the affected-item set." But Team A's re-derivation can drift (query
rewording, decomposed compound queries, a second destructive turn in the same session), and
neither team has a defined **delta semantics**: does "sets differ" mean a different **id set**
(a job added/removed) or a different **id+status set** (a job that was pending at dry-run is
now running)? If a CS201 job transitions pending→running between dry-run and confirm, Team A
(id-only compare) confirms a snapshot that enumerates a job the executor can no longer act on;
Team B (id+status compare) refuses. One team ships a confirmation gate that can confirm a
**stale-status** snapshot; the other refuses it. Both "obey AD-6." This is the safety gate of
the whole module — it cannot be left to per-team taste.

**Closing AD — amend AD-6:** the snapshot must persist (a) the **selector predicate** (the
exact provider query: method + parameters) that produced the affected list, and (b) the
**comparison key**: the Gate re-executes the stored selector and compares on
`(id, actionable status)` — any change in the id set **or** in any item's actionable field
refuses dispatch and re-renders the dry-run with the delta. Remove the possibility of
re-deriving the predicate from query text.

### C-4. Canonical strings and "exact id" have two valid owners — the literal vs the code, and byte-exact vs canonicalized-exact

**Pair:** the deterministic core emitters (AD-7, AD-8, AD-9, AD-12) versus the renderer +
console S-A (which "renders ... canonical strings verbatim," §1.1).

**The divergence, part 1 — who owns the literal.** AD-7/8/9/12 pin literal strings (`Entity
Not Found in State`, `Cannot confirm (insufficient evidence)`, `no runbook available for code
X`, `Action refused.`, `Provider unavailable — cannot answer.`). `Answer` is defined as carrying
"`diagnosis_class` **or** canonical response" (line 210) — ambiguous whether that field holds a
code or the literal.

Team A: the core emits the **literal string** as the canonical response; the console renders the
field as-is.

Team B: the core emits a **typed response code** (`entity_not_found`, `insufficient_evidence`),
and the renderer/console owns a string table that maps codes to literals.

Both "render canonical strings verbatim." But FR-14's determinism test and the audit `result_summary`
now differ in content (literal vs code), and the console S-A — which must not paraphrase — ends up
holding half the canonical vocabulary (Team B), so any future third team building a second client
must duplicate it. The consistency table (line 569) asserts "canonical strings verbatim" without
naming the owning module.

**The divergence, part 2 — exact-id normalization.** AD-7 says "matches each extracted reference
by **exact id**." Exact against *what normalized form*? The query says `alex`; the index key is
`user#alex`. Is the resolver expected to canonicalize bare names to typed keys? Is comparison
case-folded (`Alex` vs `alex`)?

Team A: byte-exact compare of the typed key after resolving bare references to `{type}#{id}`;
`alex` → `user#alex`; case-sensitive.

Team B: case-folded exact compare after the same canonicalization; `Alex` resolves too.

Both are "exact" (no fuzzy/typo tolerance — PD-3 holds). But FR-03's test condition ("≥ 10
non-existent references ... 100% return Entity Not Found") and the whole anti-fabrication
corpus change behavior: Team B resolves more surface forms, Team A returns Entity-Not-Found
for `Alex`. Since the same resolver is bound by AD-7 to both the diagnosis gate and (per
rubric-walker's C-2) should bind follow-ups, this is a corpus-visible behavioral fork.

**Closing AD — amend AD-7 (normalization) and the Consistency Conventions (string ownership):**
(a) define the resolver's normalization as: canonicalize every reference to a typed key
`{type}#{id}` (bare names type-scoped by intent requirements), then compare **exactly after a
defined case-folding rule** (recommend: case-fold, no fuzzy); pin which of the two is normative
so the FR-03 corpus is unambiguous. (b) Define canonical strings as **data owned by the
deterministic core**: the core emits the literal verbatim in the answer payload; the renderer
never re-words or maps codes; a single `canonical_strings` constant module (core-side) is the
only source, imported by adapters/tests — so there is exactly one owner and the "verbatim"
contract is machine-checkable.

### C-5. "Connective prose" is unenforceable as written — factual claims escape the Claim structure by design

**Pair:** the LLM prose adapter + prompt assembly (AD-2/AD-8/AD-11) versus the citation-coverage
check (FR-13 rubric, AD-8's rule).

**The divergence.** AD-8's Rule: "LLM prose is restricted to non-factual connective text and is
**excluded from citation coverage evaluation**. Citation coverage is a data check over the
`Claim` set." The FR-13 rubric defines a factual claim as "a declarative assertion in the answer
that states a property, relationship, value, or occurrence of a resolved entity, policy clause,
event, or clock-derived fact" — note **"in the answer"**, which includes prose.

Team A reads "non-factual connective" loosely: the LLM may restate claim content in connective
sentences ("Access to deepseek-coder is denied for role student by policy#catalog.4.2"), because
it is *derived from* the claims and AD-2 forbids *reading* claims from LLM output, not prose that
*echoes* them. The FR-13 data check passes (it only sees Claim objects).

Team B reads it strictly: prose may contain no entity ids, values, or policy references at all.

Both satisfy AD-8's letter — the divergence is that AD-8 *defines* the gap: by excluding prose
from coverage, a **factual assertion rendered in prose carries no citation** and the FR-13/NFR-3
guarantee ("100% of factual claims carry citations") silently weakens to "100% of *Claim
objects* carry citations." An adversarial or merely lazy prompt ships facts in prose with no
citations and **passes the entire verification suite**, because the check never scans prose.
The PRD rubric explicitly includes prose ("assertion in the answer"); AD-8 overrides it by
exemption.

**Closing AD — amend AD-8 (and the FR-13 mapping):** remove the prose exemption and make it
enforceable in the data check. Recommended: (a) the prose port prompt forbids any entity id,
policy-clause id, value, or clock-derived fact token (enforced by a prose-lexical guard in the
pipeline — the prose is scanned against the EvidenceSet token vocabulary; any hit is stripped or
rejected before render); (b) OR state explicitly that prose is allowed to echo claim content only
when it is rendered as an *inline evidence chip* bound to the claim's citation (which the console
already does, §1.1 "evidence chip"). Either way, the coverage check must scan the **rendered
answer text** for factual assertions, not just the Claim objects.

---

## HIGH

### H-1. The audit model's 1:1 ToolCall↔AuditRecord is contradicted by `actor=executor` rows, and the executor-result write-back path has two owners

**Pair:** the Audit Writer (§1.8, AD-10) versus the simulated executor adapter + the Proposal
store (executor_result write-back).

**Divergence A — schema.** ER line 186: `TOOL_CALL ||--|| AUDIT_RECORD : audited_as` — a
mandatory 1:1: every audit record *is* one tool call and vice versa. But AD-10's rule requires
"every executor-applied mutation is written with `actor = executor`" — an AuditRecord with **no
corresponding ToolCall** (the copilot made no call; the executor applied the mutation). The
schema table itself admits it: `tool_call_id?` is nullable (line 214). Two teams: Team A keeps
the ER's mandatory 1:1 and synthesizes a placeholder ToolCall for each executor mutation
(violating "one row per copilot tool call" in spirit); Team B makes `tool_call_id` nullable and
writes bare executor rows. The audit API shape and the "tool-call coverage 100%" metric (NFR-8)
diverge.

**Divergence B — who writes `executor_result` and the `actor=executor` audit row.** The
simulated executor is an in-process adapter. Two teams: Team A has the dispatcher receive the
executor's response and the **copilot-side** Audit Writer persists both the Proposal's
`executor_result` and the executor audit row. Team B lets the in-process simulated executor
write its own audit row directly to the SQLite audit store (it is, after all, the actor).
Both obey AD-10 ("every executor-applied mutation is written with actor = executor") and AD-1
(executor is the only mutation boundary). But under Team B, the Audit Writer is no longer the
single writer, the write-time redaction filter (AD-10) is bypassable by the executor path, and
the append-only trigger must be duplicated. §1.2 claims "It is the only process that owns
Module 12's own stores" — yet the executor writing its own rows violates that *unless* it's
stipulated, and nothing stipulates it.

**Closing AD — amend AD-10:** (a) `tool_call_id` is nullable; executor-mutation rows carry
`actor=executor` and `proposal_id` with no ToolCall (fix the ER to `TOOL_CALL |o--o| AUDIT_RECORD`).
(b) All persistence — Proposal `executor_result` **and** the `actor=executor` audit row — is
written by the copilot-side Audit Writer only, from the executor adapter's *return value*; the
executor adapter holds no write handle to Module-12 stores. This makes the redaction filter and
append-only trigger single-path.

### H-2. Re-dispatch (PD-6/AD-3) creates a second proposal with no supersession semantics — the old proposal's terminal state and the audit linkage are free

**Pair:** the re-dispatch route (`POST /api/v1/destructive/proposals/{pid}/re-dispatches`,
§3.6) + Proposal Dispatcher versus the Proposal store + audit + console delegation card.

**The divergence.** AD-3 rules "A re-dispatch is a new proposal with its own dry-run and
confirmation (PD-6)." But the Proposal state enum is `refused, dry_run, confirmed, dispatched,
executed, failed` — there is **no `superseded` state**, and there is **no
`replaces_proposal_id` linkage** between the new proposal and the old one.

Team A: leaves the old proposal in `dispatched`/`failed` (its executor failure) and lets the
console/audit infer "this was superseded by a re-dispatch."

Team B: adds an internal `superseded` terminal state and a `supersedes` FK.

Both obey AD-3's "new proposal with fresh dry-run + confirmation." But the audit's "proposal and
mutation distinguished" story and the delegation card's "proposal preserved, no auto-retry"
(EXPERIENCE) need to correlate parent→child proposals; without a linkage field, the audit rows
for the re-dispatch are orphaned from their parent, and the old proposal is left in a state that
the UI (which has no "superseded" state pattern) must fake. Also the session's `active_answer_ids`
— the destructive flow lives on the S-D surface and never goes through the query pipeline — so
whoever writes session context for the destructive flow (does anything?) is unowned: Team A
records the destructive intent/proposal into session context; Team B keeps destructive turns out
of session context entirely (AD-5 only *forbids* the gate consulting it). FR-02's follow-up
behavior then diverges for destructive turns.

**Closing AD — amend AD-3/AD-4:** add `superseded` to the Proposal state enum; add
`supersedes_proposal_id` (nullable, self-FK); rule that a re-dispatch sets the parent to
`superseded` (if it hasn't applied) or records the linkage regardless; define session-context
mutation for destructive turns (recommend: destructive turns are recorded in session context
like any other turn, but the confirmation gate still never consults it — AD-5 unchanged).

### H-3. The clock read's citable-ness is unspecified, so the schedule diagnosis's "first-class fact with its own citation" cannot be built consistently

**Pair:** the Window Calculator / schedule diagnoser (FR-05, AD-2) versus the EvidenceSet
assembler + FR-13 check.

**The divergence.** The EvidenceSet is "records + policy clauses + events + **clock read**"
(line 137, 341) — the clock read is *in* the EvidenceSet. But the Evidence entity schema
(line 211) has `source_type, source_id, snippet` — a clock read has no `source_id` in the
`{type}#{id}` vocabulary. UX Flow 2 requires the next-open-window value to render "as a
first-class fact with its own citation — not buried in prose ... citing the clock read"
(EXPERIENCE lines 224–225, 353). Team A synthesizes a citation entry for the clock read
(`source_type=clock`, `source_id=clock#read-<ts>`) so the window claim can carry a citation.
Team B treats the clock read as an input *to* the calculator, not a citable source, and cites
only the policy clause. Under Team B, the window claim's citation is to the policy clause only —
which does not "substantiate the clock-derived fact" per the FR-13 rubric ("the citation must
resolve to the specific retrieved record/field that substantiates the claim"). Team B's build
fails FR-13 on the S2 fixture even though it obeys AD-8's letter. The determinism input set
(AD-2: "query, resolved entities, state snapshot, policy content, configuration") does not list
"clock read" as a bound input, compounding it.

**Closing AD — amend AD-2 (determinism inputs) + AD-8 (citation identity):** list "clock read"
as a bound determinism input; rule that every EvidenceSet member, **including the clock read**,
has a stable `{type}#{id}` citation and is citable by claims; the window fact cites
`clock#<read_id>` (and the policy clause where applicable).

### H-4. "Fixed, ordered EvidenceSet" — ordered by whom, and does FR-14 compare order or membership?

**Pair:** the Evidence Assembler (AD-2) versus the determinism test (FR-14) + evidence strip
renderer.

**The divergence.** AD-2/§1.5 call the EvidenceSet "fixed, **ordered**." The FR-14/NFR-4 test
asserts "identical evidence set" across 3 runs — a **set** is order-insensitive. The console's
evidence strip renders citations top-down. Nothing defines the ordering key. Team A orders by
retrieval sequence (the order the assembler issued reads); Team B orders lexicographically by
citation id. Both produce "fixed, ordered" EvidenceSets and both pass "identical set" — but the
rendered evidence strip, the determinism test's byte-comparison (if the harness serializes the
set), and the citation-API paging diverge. The ordering is also the implicit definition of
"which entry is the 'specific retrieved record' a claim substantiates" in C-1.

**Closing AD — amend AD-2:** the assembler assigns a monotonic `position` per EvidenceSet entry
at assembly time; that position is part of the persisted Evidence row and the rendered order;
FR-14 compares (a) the membership set and (b) the position sequence as separate assertions.

---

## MEDIUM

- **M-1 — State-inspection entity-type vocabulary is incoherent (§3 vs §1.4/AD-13).** `{entity_type}`
  ∈ {users, models, nodes, jobs, groups, reservations, policy, events} (line 219) but the port
  surface is "users, model catalog + access policy, groups, jobs, nodes, reservations, policy
  windows, event log, clock, policy content" (AD-13 line 560) — "models" vs "catalog", "policy"
  vs "policy windows" vs "policy content" are not the same sets. Two teams diverge on whether
  `GET /api/v1/state/models/deepseek-coder` returns the catalog entry and on whether policy
  clauses and policy windows are the same endpoint. **Closing AD:** amend AD-13/§3 to one
  canonical entity-type enum that matches the port surface 1:1 (users, catalog, clauses,
  groups, jobs, nodes, reservations, windows, events), and map left-rail labels to it.

- **M-2 — AD-5's "gate token" has no issuer or validator.** AD-5 (line 464) says the
  confirmation payload "contains only a proposal reference and a gate token," but nothing issues
  or validates it. Team A issues a server-random token in the dry-run response and requires it
  echoed on confirm; Team B treats "gate token" as a constant. This compounds C-2 (the executor
  credential). **Closing AD:** fold into AD-15: the Dry-Run Builder issues a per-proposal opaque
  token; the confirm request must echo it; the dispatcher forwards it verbatim to the executor,
  which validates it. (Matches AD-5's "records no identity claim" — the token proves *flow
  continuity*, not identity.)

- **M-3 — A broken citation downgrades the whole answer, losing valid claims — unspecified.** AD-8:
  "on any such failure the answer downgrades to the literal `Cannot confirm (insufficient
  evidence)`." Is the downgrade total (drop all claims/evidence) or partial (drop only the
  broken citation's claim)? The renderer rule in EXPERIENCE says a broken citation downgrades
  the **answer**; the component pattern says "never renders as evidence if the source record
  cannot be resolved." Two teams: Team A discards the whole answer payload; Team B renders the
  valid claims and marks the broken citation's claim as downgraded. Both obey AD-8's letter
  (both end at the literal). The console's "states what was checked" pattern (EXPERIENCE) needs
  the partial version. **Closing AD:** amend AD-8 to define the downgrade as answer-level (the
  rendered diagnosis is replaced by the literal, listing what was checked), while the stored
  Answer retains claims/evidence for audit — one explicit rule.

- **M-4 — `answer_chain` stage representation is a free type.** `Answer.answer_chain` = "reached
  stages" (line 210) — is it an enum list, a bitmask, or an ordered stage array? Two teams
  diverge on the JSON shape the console's chain chips consume; the six-stage contract
  (Observation→…→Execution) is semantic, not structural. **Closing AD:** fix the shape in the
  Answer-resource contract (ordered array of stage codes from a closed enum).

- **M-5 — Runbook "verbatim" includes the provenance line or not.** AD-9: output is "the
  registered template's ordered step list, verbatim" + "provenance + version ... rendered and
  audited." Team A includes provenance inside the template payload; Team B appends it at render.
  Diverges the runbook API shape and the "verbatim" test. **Closing AD:** amend AD-9 to say the
  registry response has two sections — `steps` (template verbatim) and `provenance`
  (metadata object) — and provenance is never merged into steps.

---

## LOW

- **L-1 — Decomposition of compound queries: "independently validated sub-queries" vs a single
  EvidenceSet (FR-01 vs AD-2).** If a compound query decomposes into two intents, does each
  sub-query produce its own Answer/EvidenceSet, or one Answer with two diagnosis blocks? AD-2's
  "exactly once per answer" prose invariant and the "answer chain" assume one answer. Two teams
  diverge on the decomposition unit. Flag; suggest one AD-2 sentence: each decomposed sub-query
  is a full pipeline run with its own EvidenceSet and its own single prose invocation.
- **L-2 — `GET /api/v1/state/{entity_type}?q=` browse semantics** (FR-12) — the `q` matching rule
  (substring? exact? case-folded?) is free, reusing the C-4 normalization ambiguity. Fold into
  the AD-7 normalization rule.
- **L-3 — Redaction filter's trigger vocabulary** ("drops credentials, tokens, and secrets")
  is unlisted; two teams redact different token shapes, and the "0 secrets in sampled entries"
  test (NFR-11) passes on different corpora. Suggest listing the redaction patterns in AD-10.

---

## Coverage / scoring

| Focus area | Findings |
|---|---|
| Clashing shared-data shapes | C-1 (EvidenceSet/Claim/Citation), C-2 (executor vs dry_run_snapshot), H-3 (clock), H-4 (order), M-4 (answer_chain) |
| Two owners of one entity | C-4 (canonical strings/id), C-3 (affected items selector), H-1B (executor result write-back), C-2 (affected-items scope: builder vs executor) |
| Conflicting state-mutation paths | H-1 (audit writer vs executor writer), H-2 (proposal supersession/session context), H-3 (who writes executor_result) |
| Unenforceable/ambiguous AD rules | C-5 (connective prose), C-4 (exact id normalization), M-2 (gate token), M-3 (downgrade scope) |
| Boundary leaks (Copilot↔operational state / propose-only bypass) | C-2 (executor re-enumerates → scope decision leaks to executor), H-1B (executor writes Module-12 stores), M-2 (gate token absent → executor cannot prove gate) |

Suggested disposition: **block story decomposition** until C-1..C-5, H-1, H-2 are resolved by
the AD amendments above (they are all small, additive AD edits — no new architecture). H-3/H-4
and the mediums can ride into sprint 1 as tightened ADs.