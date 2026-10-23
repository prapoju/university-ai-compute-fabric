---
title: Module 12 — AI Operations Copilot — Phase 1 Formal Behavioral Contracts (P, Q, I)
status: draft
created: 2026-10-16
updated: 2026-10-16
binds: [PRD FR-01..FR-16, NFR-1..NFR-11, ARCHITECTURE AD-1..AD-15, D1..D51]
sources:
  - planning/prd.md
  - planning/ARCHITECTURE.md
  - _bmad-output/planning-artifacts/prds/prd-plan-2-university-ai-fabric-2026-09-27/ai-decision-log.md
  - ai-log/decision-log-solu2.md
---

# Phase 1 — Formal Behavioral Contracts (P, Q, I)

**Goal.** Design-by-Contract specifications for every core operation and every permitted read operation, with zero elastic language.

**Banned words (enforced by the `no-elastic-language` lint over this file):** `efficiently, appropriately, securely, quickly, gracefully, reasonable, robust, properly, as needed, scalable, user-friendly, etc.` Each occurrence in the source drafts is replaced here by a number, a type, an enumeration, a status code, or a state name.

**Notation.** `P` = precondition, `Q` = postcondition, `I` = invariant. `->` separates a condition from its typed violation. `==>` separates a call from its transition. `[x, y)` is a half-open interval. All timestamps are ISO-8601 UTC. All ids are stable strings of the form `{type}#{id}`.

**Canonical strings (single owner: `service/core/strings/canonical_strings.py`, AD-1/Consistency Conventions).** These literals are emitted verbatim and never re-worded by the renderer:

| Symbol | Literal (emitted verbatim; `{...}` slots are filled, never reformatted) |
|---|---|
| `S_ENF` | `Entity Not Found in State: {ref_list}.` |
| `S_CNC` | `Cannot confirm (insufficient evidence): checked {checked_list}.` |
| `S_PUA` | `Provider unavailable — cannot answer.` |
| `S_ARF` | `Action refused.` |
| `S_RBX` | `no runbook available for code {code}.` |
| `S_CAP` | `This confirms a proposal for delegation. It does not grant or assert authorization.` |

Each literal above is byte-identical to its §4 template (D57); the table is the single source of truth and §4 must not re-word it.

---

## 0. Type & Enum Vocabulary

Referenced by every contract below. A contract that names a type here does not restate it.

### 0.1 Scalar and value types

| Type | Definition |
|---|---|
| `QueryText` | `string`, UTF-8. Normalized once as `q = query_text.strip()`; the empty/length tests run on that same trimmed value: `len(q) == 0` -> `VALIDATION_EMPTY_QUERY`; `len(q) > 1000` -> `VALIDATION_QUERY_TOO_LONG`; accepted domain `1 <= len(q) <= 1000`. |
| `SessionId` | `string` matching `^sess-[0-9a-f]{16}$`. |
| `OperatorRole` | synthetic string, `^role-[a-z0-9_-]{1,32}$` (NFR-11). |
| `Instant` | `string`, ISO-8601 UTC, `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z$`. |
| `ClockRead` | `{read_id: string, instant: Instant, source: "clock"}`. Citation id `clock#{read_id}`. |
| `EntityKey` | `string` of the form `{type}#{id}`. |
| `RawRef` | `string`, `1 <= len <= 200`, the operator's literal reference text. A literal `#` inside operator text is escaped as `\#`; the parser splits on the first unescaped `#` only, so operator text is never mis-read as the `{type}#{id}` separator (D61). |
| `Snippet` | `string`, `1 <= len <= 500`; for `policy`/`runbook` sources `len <= 2000`. |
| `Page` | `integer`, `>= 1`. |
| `PageSize` | `integer`, `1 <= page_size <= 100` (cap, D46). |
| `GateToken` | opaque `string`, `^gt-[0-9a-f]{32}$`. |
| `ActionVerb` | closed enum `{delete_jobs, cancel_jobs, cordon_node, drain_node}`. |
| `ReasonClass` | closed enum `{not-in-allowlist, quota, window}`. |
| `IdKind` | closed enum `{session, answer, claim, tool_call, audit, proposal, gate_token, event}`. `evidence` is intentionally **not** an `IdKind`: an `Evidence` row is keyed by `(answer_id, citation_id)` and `citation_id` is a provider key (`{type}#{id}` or `clock#id`), never minted by `idgen_port` (D67, X-02). |
| `IdString` | `string` matching the per-kind format: `sess|ans|clm|tc|aud|prop|evt`-`[0-9a-f]{16}`, `gt-[0-9a-f]{32}`. |
| `ResolvedEntity` | `{key: EntityKey, entity_type: string, source: string, record: Record}`. |
| `ResolvedEntitySet` | ordered `ResolvedEntity[]`, one entry per input `RawRef`; each `key` resolves to exactly one `Record`. |
| `IntentCode` | registered intent identifier — closed set owned by the intent registry, e.g. `diagnose_access_denial`, `diagnose_schedule_window`, `diagnose_retrospective`, `diagnose_node_triage`, `propose_destructive_action`. |
| `EventQuery` | `{entity_ref: EntityKey, type in {access_denied, job_cancelled, node_cordoned}, window: {start: Instant, end: Instant}}`. |

### 0.2 Entity types

| Context | Enum |
|---|---|
| Entity resolver / citation type (`{type}`) | `{user, group, model, policy, node, job, reservation, window, event}` |
| Inbound route param `{entity_type}` | `{users, catalog, policy, groups, jobs, nodes, reservations, windows, events}` (the two enumerations are 1:1; `model` <-> `catalog`, `window` <-> `windows`) |

Any value outside the enum -> `VALIDATION_BAD_ENTITY_TYPE`.

### 0.3 Records (returned by read ports)

| Type | Fields (exact; extra fields are a contract violation) |
|---|---|
| `UserRecord` | `id, display_name, role in {student, staff, faculty, privileged}` |
| `GroupRecord` | `id, name, members: EntityKey[]` |
| `ModelCatalogEntry` | `id, name, allowed_roles: Role[]` |
| `AccessPolicyClause` | `clause_id, model_id, rule, reason_class: ReasonClass, text` |
| `JobRecord` | `id, group_id, course, status in {pending, running, succeeded, cancelled, failed}, scheduling_constraint: string|null, created_at: Instant` |
| `NodeRecord` | `id, hostname, gpu_memory_gb: integer, status in {available, reserved, active, fault}, cordoned: boolean, error_code: string|null, health: string` |
| `ReservationRecord` | `id, node_id, start: Instant, end: Instant, purpose: string`; provider invariant `start < end` (D66). |
| `PolicyWindow` | `window_id, applies_to, start: Instant, end: Instant, timezone: string`; provider invariant `start < end` (D66). |
| `OperationalEvent` | `event_id, type in {access_denied, job_cancelled, node_cordoned}, entity_ref: EntityKey, timestamp: Instant, outcome: string, recorded_reason: string` |
| `Record` | the union of the nine rows above, keyed by `{entity_type}`. |

### 0.4 Answer composition

| Type | Definition |
|---|---|
| `Evidence` | `{citation_id: EntityKey\|clock#id, source_type: string, snippet: Snippet, position: integer >= 0}` |
| `EvidenceSet` | ordered, `citation_id`-unique `Evidence[]`; `(answer_id, citation_id)` is UNIQUE. |
| `Claim` | `{claim_id, text: string, claim_citations: citation_id[]}`; `len(trim(text)) >= 1` and `len(claim_citations) >= 1`. |
| `DiagnosisClass` | closed enum `{access_denial_not_in_allowlist, access_denial_quota, access_denial_window, schedule_window_restricted, schedule_no_constraint, event_denied, event_cancelled, event_cordoned, node_triage_runbook, no_runbook_available}` |
| `Diagnosis` | `{diagnosis_class: DiagnosisClass, claims: Claim[], recommendation: object\|null}`; `diagnosis_class` is a pure function of the `EvidenceSet` (AD-2). |
| `AnswerChain` | ordered array over closed enum `[observation, evidence, diagnosis, recommendation, proposal, execution]`; contiguous prefix, never reordered, never skipped. |
| `Answer` | `{answer_id, session_id, query, intent, answer_chain: AnswerChain, diagnosis_class: DiagnosisClass\|null, canonical: CanonicalCode\|null, claims: Claim[], evidence: EvidenceSet, recommendation: object\|null, proposal_ref: string\|null, prose: string}` |
| `CanonicalCode` | closed enum `{ENTITY_NOT_FOUND, CANNOT_CONFIRM, CLARIFICATION, INTENT_NOT_SUPPORTED, ACTION_REFUSED}`; every member maps 1:1 to a §4 code returned as an HTTP-200 canonical (D54). `PROVIDER_UNAVAILABLE` and `VALIDATION_ERROR` are **not** canonical codes: provider failure produces no `Answer` (`S_PUA`, HTTP 503) and validation errors return HTTP 400. |
| `AnswerEnvelope` | `{answers: Answer[]}`; `len >= 1`. A single-intent query yields `len == 1`; a query classified as decomposed compound (D37) yields `len >= 2` — a compound classification with `len == 1` is a contract violation (D54). |
| `ProsePrompt` | `{evidence_sections: string[], instruction: string}` — evidence sections are delimited data copied verbatim (AD-11). |
| `ProseText` | `string` of connective prose containing zero evidence-vocabulary tokens (AD-8). |

### 0.5 Safety / proposal types

| Type | Definition |
|---|---|
| `Selector` | `{method: string, params: object}` — the exact provider query (method + parameters) that produced the affected set. |
| `AffectedItem` | `{key: EntityKey, actionable: boolean, actionable_field: string, actionable_value: string}` |
| `DryRunSnapshot` | `{selector: Selector, affected_items: AffectedItem[], snapshot_timestamp: Instant}` |
| `ProposalState` | closed enum `{refused, dry_run, confirmed, dispatched, executed, failed, superseded}` |
| `Proposal` | `{proposal_id, session_id, state: ProposalState, action: ActionVerb, supersedes_proposal_id: string\|null, dry_run_snapshot: DryRunSnapshot, gate_token: GateToken, confirmation: {confirmed_at: Instant, caption: string}\|null, executor_result: {status: ExecutorStatus, applied_records: EntityKey[], applied_count: integer, timestamp: Instant, source: "executor"}\|null}`. Cross-field rule: `executor_result` is non-null iff `state in {executed, failed}`; `confirmation.caption` always carries the `S_CAP` literal. |
| `ExecutorStatus` | closed enum `{applied, partial, failed}` |
| `ExecutorRequest` | `{proposal_id, action: ActionVerb, selector: Selector, gate_token: GateToken, dry_run_ref: {proposal_id}}` (frozen, AD-15). Invariant: `dry_run_ref.proposal_id == proposal_id`; a mismatch is `VALIDATION_MALFORMED_BODY` (HTTP 400). |
| `Intent` | `{intent_code: IntentCode, confidence: number, matched_rule_id: string}` — rule-based classifier output (AD-11), never LLM-derived. |
| `Session` | `{session_id: SessionId, created_at: Instant, operator_role: OperatorRole, context: {resolved_entities: EntityKey[], prior_intents: IntentCode[], active_answer_ids: string[]}, status in {active, reset, expired}, turns: Turn[]}`. |
| `Turn` | `{turn_id: string, at: Instant, query: QueryText, answer_ids: string[]}`. |
| `ToolCall` | `{tool_call_id: string, session_id: SessionId, name: string, at: Instant, actor in {copilot, executor}, proposal_id: string\|null}`; an `actor == executor` row carries `tool_call_id == null`. |

### 0.6 Layer legend

`Inbound Port` = REST adapter entrypoint (`/api/v1`, `/executor/v1`). `Core Domain` = pure deterministic functions (`service/core`), no I/O, no LLM, no HTTP. `Outbound Port` = read-only provider interface (`service/ports`), implemented by a mock/real adapter.

---

## 1. Core Domain Contracts

**Invariant scoping (D60).** Throughout this document, operation/route/port-local invariants are written `L1, L2, …`; the global invariant table in §5 uses `I1…I22`. A bare `In` always means the §5 global invariant; a local clause is always written `L…`.

**Diagnoser input contract (AD-2 amendment).** Every `diagnose_*` operation is a pure function of the `EvidenceSet` and, where noted, `now`; any additional typed parameter (`windows`, `events`, a `RunbookTemplate`) is exactly the record set cited by that `EvidenceSet`. The same `EvidenceSet` therefore yields the same `diagnosis_class` regardless of how the records were fetched.

### Operation: `answer_query(query_text: QueryText, session_id: SessionId, now: ClockRead) -> AnswerEnvelope`

- **Layer:** Application orchestrator (drives Core Domain pure functions and Outbound Ports; this contract is the pipeline result). It is **not** a pure Core Domain function — §0.6 defines Core Domain as I/O-free, while this operation reads provider ports and calls `llm_prose_port` (D53).
- **Precondition (P):**
  - P1: `query_text` is `QueryText`. Let `q = query_text.strip()`; both tests run on that same value: `len(q) == 0` -> violation `VALIDATION_EMPTY_QUERY` (HTTP 400); `len(q) > 1000` -> violation `VALIDATION_QUERY_TOO_LONG` (HTTP 400).
  - P2: `session_id` resolves to a `Session`. Absent -> violation `SESSION_NOT_FOUND` (HTTP 404). Idle age is `now.instant - coalesce(last_turn_at, created_at)`; `status == reset` or `status == expired`, or idle age `> 30 min`, -> the session is persisted as `status == expired` (idempotently) and the violation is `SESSION_EXPIRED` (HTTP 410) (D51).
  - P3: `now.source == "clock"` and `now.read_id` is a value actually issued by the Clock port for this call -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400).
- **Postcondition (Q):**
  - Q1: returns `AnswerEnvelope` with `len(answers) >= 1`; each `Answer` schema-valid per §0.4; for a single-intent query `len(answers) == 1`; for a decomposed compound query each sub-answer carries its own `answer_chain` and `canonical` (D37).
  - Q2: state predicate `session.context.resolved_entities` is a superset of the pre-call set; `session.context.prior_intents` and `session.context.active_answer_ids` each gain exactly one appended entry **per returned `Answer`** (so a compound query appends `>= 2`, not one per query) (D51); no operational-state predicate changes: `operational_state_before == operational_state_after` (AD-1).
  - Q3: audit event `toolcall.answer_query` emitted exactly once per call, plus one audit row per port read performed (AD-10); metric `m12.answer_query.count` and `m12.answer_query.latency_ms` emitted once. Transaction boundary: tool calls and audit rows are committed atomically with the `Answer`; if a later stage fails, the turn's tool calls are voided (marked non-effective) so no orphan audit rows describe a turn that produced no `Answer` (AD-10).
  - Q4: for every `Claim` in the returned answers, `len(claim.claim_citations) >= 1` and every `citation_id` resolves to exactly one `EvidenceSet` entry; `diagnosis_class` and `canonical` are emitted by deterministic code, never read from LLM output (AD-2, AD-8).
  - Q-fail: if `P1`, `P2`, or `P3` fails, no `Answer` is created, `session.context` is unchanged, and no `Answer` row is written; the typed error is returned and the `query` turn is not appended.
- **Invariant (I):**
  - L1: every rendered factual claim in `claim.text` or `prose` is bound to >= 1 `EvidenceSet` citation; prose is scanned against the `EvidenceSet` token vocabulary and on a hit the whole output is rejected and retried once, never stripped (D48). Bound to: AD-8.
  - L2: `answer_query` performs zero writes to any operational-state store; the only writes are to Module-12-owned stores (Session, Answer, Evidence, Claim, ToolCall, AuditRecord). Bound to: AD-1, AD-13.
  - L3: given identical `(query_text, resolved entities, state snapshot, policy content, config, now.instant)`, `EvidenceSet` membership, `EvidenceSet.position` sequence, citation set, `diagnosis_class`, and runbook step list are identical across runs; `prose` may differ. Bound to: AD-2, AD-14.
- **Concurrency / idempotency:** not idempotent by design — a repeated identical call creates a new `answer_id` and a new turn. Under the chosen store every write serializes on the single SQLite writer (WAL, AD-10); concurrent calls for distinct sessions therefore **queue** on that writer rather than writing in parallel — the claim is queued write latency, not non-blocking parallelism. No shared mutable pipeline state exists across sessions (NFR-6). A `reset_session` for the same session takes the writer first; if it commits before the in-flight turn's write, the turn aborts without appending context (D51).
- **Time:** Clock port `clock_port.now()` only (DP-5). The core never calls `datetime.now()`/`time.time()` (I-CLK-1). `now` is passed once per call and reused for the window calculator, dry-run `snapshot_timestamp`, and audit timestamps of that turn. The executor adapter takes its **own** Clock read for the executor result `timestamp` (AD-15).
- **Latency budget (NFR):** p95 <= 3000 ms, p99 <= 8000 ms submit->rendered cited answer at 5 concurrent sessions, 50 queries/hour sustained (NFR-5, NFR-6). Sub-budget: `resolve_entities` < 20 ms, `assemble_evidence` < 100 ms, each `diagnose_*` < 10 ms, single LLM prose call p95 <= 3000 ms (OP-14); the LLM is not on the evidence critical path.

---

### Operation: `resolve_entities(references: RawRef[], session_id: SessionId) -> ResolvedEntitySet | CanonicalCode`

- **Layer:** Core Domain
- **Precondition (P):**
  - P1: `references` is a non-empty array with `len(references) <= 32`; each element length `1..200` -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400) (D68).
  - P2: `session_id` resolves to an active `Session` (or `references` carries an explicit type that fixes resolution) -> violation: `SESSION_NOT_FOUND` (HTTP 404).
  - P3: each reference has either an intent-fixed `EntityType` or an unambiguous bare type after provider-index lookup -> violation: `CLARIFICATION_REQUIRED` (HTTP 200 canonical) for a bare reference with `>= 2` candidate types (D36).
- **Postcondition (Q):**
  - Q1: returns `ResolvedEntitySet` = `EntityKey[]`, one entry per input reference, each `key = {type}#{id}` resolving to exactly one `Record`, each with `source` provider name.
  - Q2: state predicate: provider indexes unchanged (`index_before == index_after`); session context is read for follow-up resolution first, then each context-resolved entity is re-resolved against the provider before use (D35).
  - Q3: audit event `toolcall.resolve_entities` emitted once; one audit row per provider index read.
  - Q4: on any unresolved reference the return is the literal `S_ENF` naming every unresolved `RawRef` in input order; no partial `ResolvedEntitySet` is returned.
  - Q-fail: if any reference is unresolved, no diagnosis proceeds, no `Answer` is composed, and session context is unchanged.
- **Invariant (I):**
  - L1: resolution canonicalizes to `{type}#{id}` then compares exactly under case-fold; no fuzzy, no edit-distance, no LLM invocation (AD-7, D26). Bound to: AD-7.
  - L2: every returned `EntityKey` resolves to exactly one existing record; the fabricated-entity rate is 0 over the defined corpus. Bound to: AD-7, NFR-2.
- **Concurrency / idempotency:** pure function over a given provider snapshot; idempotent: identical `(references, snapshot)` returns an identical `ResolvedEntitySet`.
- **Time:** no time read. (Event time-window matching is owned by `event_store_port.query`, not here.)
- **Latency budget (NFR):** p95 < 20 ms at 5 concurrent (allocated from NFR-5).

---

### Operation: `assemble_evidence(intent: IntentCode, resolved: ResolvedEntitySet, now: ClockRead) -> EvidenceSet`

- **Layer:** Core Domain
- **Precondition (P):**
  - P1: `intent` is a registered `IntentCode` -> violation: `INTENT_NOT_SUPPORTED` (HTTP 200 canonical; `CanonicalCode.INTENT_NOT_SUPPORTED`, D54).
  - P2: `resolved` is a complete `ResolvedEntitySet` (no unresolved references) -> violation: `ENTITY_NOT_FOUND` (HTTP 200 canonical).
  - P3: every required provider port for `intent` is reachable -> violation: `PROVIDER_UNAVAILABLE` (HTTP 503).
- **Postcondition (Q):**
  - Q1: returns `EvidenceSet` whose entries are unique by `citation_id`, each with `position` a strictly increasing integer starting at 0; includes the `clock#{read_id}` entry when the intent uses time (AD-14).
  - Q2: state predicate: all provider stores unchanged (`stores_before == stores_after`).
  - Q3: audit event `toolcall.assemble_evidence` emitted once; one audit row per provider read issued.
  - Q4: evidence entries cite only sources required by `intent`; each entry's `source_type` is one of `{user, group, model, policy, node, job, reservation, window, event, clock}`.
  - Q-fail: if any provider read returns `failure`, the entire `EvidenceSet` is discarded and `S_PUA` is returned; no partial evidence is emitted (AD-12).
- **Invariant (I):**
  - L1: `position` is assigned at assembly time and is monotonic; `(answer_id, citation_id)` is UNIQUE. Bound to: AD-14.
  - L2: identical `(intent, resolved, snapshot, policy, config, now.instant)` yields identical membership and position sequence. Bound to: AD-2.
- **Concurrency / idempotency:** pure over a snapshot; idempotent for identical inputs.
- **Time:** `now` is passed in; no internal clock read. Window calculations use half-open `[start, end)` (D38).
- **Latency budget (NFR):** p95 < 100 ms at 5 concurrent (allocated from NFR-5).

---

### Operation: `diagnose_access_denial(user: ResolvedEntity, model: ResolvedEntity, evidence: EvidenceSet) -> Diagnosis | CanonicalCode`

- **Layer:** Core Domain
- **Precondition (P):**
  - P1: `user.entity_type == user` and `model.entity_type == model` -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400).
  - P2: `evidence` contains a matching `AccessPolicyClause` when the reason is policy-based, and a matching `OperationalEvent` (`type == access_denied`) when a denial occurred -> violation: `CANNOT_CONFIRM` (HTTP 200 canonical) when the entity exists but the clause/event is absent.
- **Postcondition (Q):**
  - Q1: returns `Diagnosis` = `{diagnosis_class: ReasonClass mapped to {access_denial_not_in_allowlist, access_denial_quota, access_denial_window}, claims: Claim[], recommendation: null}`; the `policy` clause id and text are cited. When more than one clause matches, the class is chosen by fixed precedence `not-in-allowlist > quota > window` so the class is deterministic (AD-2 amendment).
  - Q2: state predicate: stores unchanged.
  - Q3: audit event `toolcall.diagnose_access_denial` emitted once.
  - Q4: every claim cites the `user` record, the `policy` clause, and (when present) the denial `event`; the diagnosis class is one of the three access-denial classes.
  - Q-fail: on P1/P2 violation no `Diagnosis` is produced; the answer carries `canonical = CANNOT_CONFIRM` or `ENTITY_NOT_FOUND` and `diagnosis_class = null`.
- **Invariant (I):**
  - L1: the returned `diagnosis_class` is a pure function of the `EvidenceSet`; no LLM-derived value. Bound to: AD-2.
- **Concurrency / idempotency:** pure function; idempotent.
- **Time:** no time read (event timestamp is read from the event record).
- **Latency budget (NFR):** p95 < 10 ms (allocated from NFR-5).

---

### Operation: `diagnose_schedule_window(group: ResolvedEntity, job: ResolvedEntity, windows: PolicyWindow[], now: ClockRead) -> Diagnosis | CanonicalCode`

- **Layer:** Core Domain
- **Precondition (P):**
  - P1: `group.entity_type == group`, `job.entity_type == job`, `job.record.status == pending` -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400).
  - P2: `now` is a valid `ClockRead` -> violation: `CLOCK_UNAVAILABLE` (HTTP 503) if the clock read is absent or failed.
  - P3: `windows` is the full set returned by `windows_port.list()` for `job.scheduling_constraint`; an empty set is legal -> violation: `PROVIDER_UNAVAILABLE` (HTTP 503) only if the read itself failed.
- **Postcondition (Q):**
  - Q1: returns `Diagnosis` = `{diagnosis_class, claims, recommendation}` where `diagnosis_class in {schedule_window_restricted, schedule_no_constraint}` and, when restricted, `recommendation.next_open_window = {start: Instant, end: Instant, timezone: string}` computed over half-open `[start, end)` (D38), with an explicit date + timezone on both edges (D39). If `windows` is empty, the class is `schedule_no_constraint` and no `next_open_window` is computed (D55). If no window satisfies `start > now.instant`, `next_open_window == null` and an explicit no-future-window state is rendered — never a value derived from an empty future set (D55).
  - Q2: state predicate: stores unchanged.
  - Q3: audit event `toolcall.diagnose_schedule_window` emitted once; the clock read is a citable `clock#{read_id}` evidence member.
  - Q4: when `job.scheduling_constraint is null`, `diagnosis_class == schedule_no_constraint` and NO window is rendered (D30); the answer never implies a window policy did not grant.
  - Q-fail: if P2/P3 fails, `S_PUA` is returned; no window is computed from a failed read (AD-12).
- **Invariant (I):**
  - L1: window membership predicate is exactly `start <= t < end`; a boundary `t == end` is not open. Bound to: AD-2.
  - L2: the next open window is a deterministic function of `(windows, now.instant)`; identical inputs yield an identical `(start, end) | null`. Bound to: AD-2.
- **Concurrency / idempotency:** pure; idempotent.
- **Time:** Clock port only; `[start, end)` semantics; both edges carry explicit date + timezone.
- **Latency budget (NFR):** p95 < 10 ms (allocated from NFR-5).

---

### Operation: `diagnose_retrospective(query: EventQuery, events: OperationalEvent[]) -> Diagnosis | CanonicalCode`

- **Layer:** Core Domain
- **Precondition (P):**
  - P1: `query.entity_ref` is a resolved `EntityKey`, `query.type in {access_denied, job_cancelled, node_cordoned}`, `query.window` is a half-open `[start, end)` instant pair -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400).
  - P2: `events` is the full result of `event_store_port.query(entity_ref, type, window)` -> violation: `PROVIDER_UNAVAILABLE` (HTTP 503).
- **Postcondition (Q):**
  - Q1: returns `Diagnosis` with `diagnosis_class in {event_denied, event_cancelled, event_cordoned}`, one `Claim` per matched event citing `event#{event_id}`, carrying `timestamp`, `outcome`, and `recorded_reason`. When a window contains more than one event type, the class is chosen by fixed precedence `event_denied > event_cancelled > event_cordoned` so the class is deterministic (AD-2 amendment).
  - Q2: state predicate: stores unchanged.
  - Q3: audit event `toolcall.diagnose_retrospective` emitted once.
  - Q4: when `len(events) == 0`, the return is `S_CNC` (the entity may exist; the evidence is insufficient) and no event is invented.
  - Q-fail: on P1/P2 violation, no `Diagnosis`; answer carries the applicable canonical code.
- **Invariant (I):**
  - L1: event matching is a half-open `[start, end)` interval in `timestamp`. Bound to: AD-2.
  - L2: `recorded_reason` is read from the event record; no policy-version replay is performed (D25). Bound to: AD-2.
- **Concurrency / idempotency:** pure; idempotent.
- **Time:** matching uses `timestamp` on `[start, end)`; no wall-clock read.
- **Latency budget (NFR):** p95 < 10 ms (allocated from NFR-5).

---

### Operation: `diagnose_node_triage(node: ResolvedEntity, error_code: string, template: RunbookTemplate|null) -> Diagnosis | CanonicalCode`

- **Layer:** Core Domain
- **Precondition (P):**
  - P1: `node.entity_type == node`, `node.record.cordoned == true` -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400).
  - P2: `error_code is not null` and `error_code == node.record.error_code` (the node must report the queried code); a null code, or a code that does not match the node's recorded code, is a miss -> violation: `RUNBOOK_NOT_FOUND` (HTTP 200 canonical `no runbook available for code {code}.`, `{code}` = the recorded code or `null`) (D43). A *present matching* code is accepted; the miss case is the null or non-matching code (A1 correction).
  - P3: when non-null, `error_code` matches `^[A-Za-z0-9._-]{1,64}$` (sanitized before it is interpolated into the canonical string) -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400) (E46).
- **Postcondition (Q):**
  - Q1: returns `Diagnosis` with `diagnosis_class == node_triage_runbook`, `recommendation.runbook = {steps: string[] (verbatim template order), required_tools: string[], safety_warnings: string[], provenance: {source: string, version: string}}`.
  - Q2: state predicate: stores unchanged; no cordon/uncordon is performed (AD-13).
  - Q3: audit event `toolcall.diagnose_node_triage` emitted once; the template `provenance`/`version` is audited.
  - Q4: every step originates from the registered template; when no template exists or the code mismatches, `diagnosis_class == no_runbook_available` and `recommendation == null`.
  - Q-fail: on P1/P2/P3 violation no runbook is rendered; no step is invented.
- **Invariant (I):**
  - L1: runbook steps are the registered template's ordered step list, verbatim; a template whose physical-intervention steps lack approved-source metadata renders unavailability, not steps. Bound to: AD-9.
- **Concurrency / idempotency:** pure; idempotent.
- **Time:** no time read by this function.
- **Latency budget (NFR):** this function p95 < 10 ms (allocated from NFR-5); the end-to-end runbook operation budget is the inbound `get_runbook` budget.

---

### Operation: `lookup_runbook(error_code: string) -> RunbookTemplate | CanonicalCode`

- **Layer:** Core Domain
- **Precondition (P):**
  - P1: `error_code` matches `^[A-Za-z0-9._-]{1,64}$` (non-empty, `len <= 64`, no markup/control characters) -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400). This format is enforced before the code is interpolated into any canonical string (E46).
- **Postcondition (Q):**
  - Q1: returns `RunbookTemplate` = `{template_id, error_code, steps: string[], required_tools: string[], safety_warnings: string[], physical_intervention: boolean, approved_source: string|null, version: string}`; `len(steps) >= 1`.
  - Q2: state predicate: registry unchanged.
  - Q3: audit event `toolcall.lookup_runbook` emitted once.
  - Q4: lookup is by exact `error_code`; a miss returns the literal `no runbook available for code {error_code}.` (byte-identical to `S_RBX`, D57); `steps` and `provenance` are returned as two separate sections and never merged (AD-9).
  - Q-fail: on P1 violation, `VALIDATION_MALFORMED_BODY`; no registry mutation.
- **Invariant (I):**
  - L1: a template with `len(steps) == 0` is rejected at registration (D44); no registered template has an empty step list. Bound to: AD-9.
  - L2: a `physical_intervention == true` template with `approved_source == null` renders unavailability. Bound to: AD-9.
- **Concurrency / idempotency:** pure read; idempotent.
- **Time:** no time read.
- **Latency budget (NFR):** p95 < 5 ms (allocated from NFR-5).

---

### Operation: `propose_destructive_action(query_text: QueryText, action: ActionVerb, target_refs: RawRef[], session_id: SessionId, now: ClockRead) -> Proposal (state == dry_run) | CanonicalCode`

- **Layer:** Core Domain
- **Precondition (P):**
  - P1: `action in ActionVerb` (closed enum) -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400).
  - P2: `session_id` resolves to an active `Session` -> violation: `SESSION_NOT_FOUND` (HTTP 404).
  - P3: every `target_refs` reference resolves via `resolve_entities` and the `(action, resolved entity_type)` pair is compatible (`delete_jobs`/`cancel_jobs` require `job`; `cordon_node`/`drain_node` require `node`) -> violation: `ENTITY_NOT_FOUND` (HTTP 200 canonical) for an unresolved reference, `VALIDATION_BAD_ACTION` (HTTP 400) for an incompatible type (AD-4, D55). Validation precedes any dry-run build.
  - P4: the compound-query check confirms `query_text` holds exactly one destructive intent -> violation: `CLARIFICATION_REQUIRED` (HTTP 200 canonical) when a destructive verb is combined with another intent (AD-4).
- **Postcondition (Q):**
  - Q1: returns a `Proposal` with `state == dry_run`, `dry_run_snapshot.selector` = the exact provider query `{method, params}` executed, `dry_run_snapshot.affected_items` enumerating every matching item with `{key, actionable, actionable_field, actionable_value}`, `dry_run_snapshot.snapshot_timestamp == now.instant`, and a fresh `gate_token`. The selector source is fixed by action: job actions use `jobs_port.select(selector)`; node actions use `nodes_port.select(selector)` (OP-6), where the resolved `target_refs` populate `Selector.params.node_ids` (D55). Items whose record is already in a terminal status are enumerated with `actionable == false`; they are never counted as available actions (D55).
  - Q2: state predicate `operational_state_before == operational_state_after` (zero mutations, NFR-8); exactly one `Proposal` row inserted with `state == dry_run`.
  - Q3: audit events emitted in order: `toolcall.answer_query` (refusal turn), `toolcall.propose_destructive_action`; metric `m12.destructive.refused.count` incremented once.
  - Q4: the returned refusal carries the literal `S_ARF`; the snapshot carries the selector predicate and the timestamp; the affected set is the dry-run enumeration.
  - Q-fail: if `len(affected_items) == 0`, `state == dry_run` with an empty set and confirmation disabled (no dispatch path); the proposal is flagged non-re-dispatchable, and `post_re_dispatch` requires a fresh dry-run that produced a non-empty affected set (D55). On P1–P4 violation no `Proposal` is created and no mutation occurs.
- **Invariant (I):**
  - L1: the descriptor persists the selector predicate that produced the set; the selector is never re-derived from query text at confirm time (AD-6). Bound to: AD-6.
  - L2: the Copilot performs zero operational-state writes; a `Proposal` row is Module-12-owned. Bound to: AD-1, AD-3.
- **Concurrency / idempotency:** each call creates a distinct `proposal_id` and a distinct `gate_token`; not idempotent. Concurrent dry-runs for one session are serialized by the single writer.
- **Time:** Clock port only; `snapshot_timestamp = now.instant`.
- **Latency budget (NFR):** p95 <= 2000 ms at 5 concurrent (allocated from NFR-5; dry-run is part of the destructive request path).

---

### Operation: `confirm_and_dispatch(proposal_id: string, gate_token: GateToken) -> Proposal (state in {dispatched, executed, failed}) | CanonicalCode`

- **Layer:** Core Domain (Confirmation Gate + Proposal Dispatcher; the only caller of the executor port)
- **Precondition (P):**
  - P1: `proposal_id` resolves to a `Proposal` -> violation: `PROPOSAL_NOT_FOUND` (HTTP 404). If the state is not `dry_run`, the idempotency clause of P5 decides the outcome before any state-invalid rejection (D47 amendment).
  - P2: `gate_token == proposal.gate_token` and the snapshot is fresh (`now.instant - dry_run_snapshot.snapshot_timestamp <= 15 min`, the token TTL) -> violation: `GATE_TOKEN_INVALID` (HTTP 403) on mismatch; `CONFIRMATION_STALE` (HTTP 409) on an expired token (AD-3, D47).
  - P3: the stored `selector` re-executes and re-queries the same `(id, actionable status)` set as `dry_run_snapshot.affected_items` -> violation: `CONFIRMATION_STALE` (HTTP 409) with the delta surfaced and confirmation disabled.
  - P4: `len(dry_run_snapshot.affected_items) >= 1` -> violation: `DRY_RUN_EMPTY_SET` (HTTP 409).
  - P5: idempotency and conflict: if a prior dispatch exists for `proposal_id`, an **identical** `(proposal_id, gate_token)` is idempotent — it returns the persisted `Proposal` state with no second executor call; any **differing** confirm against an already-dispatched proposal is -> violation: `CONFIRMATION_CONFLICT` (HTTP 409) (D47). This clause is evaluated before P1's state-invalid branch so the idempotent path is reachable.
  - P6: the executor port is reachable -> violation: `EXECUTOR_UNAVAILABLE` (HTTP 503) and `state == failed` after 5 s without a response (D31). A late executor response that arrives after the timeout is recorded as an `executor_result` without changing the `failed` state, or is rejected by the executor's `ux_audit_executor_apply` idempotency key — it never triggers a second apply (AD-3, D31).
- **Postcondition (Q):**
  - Q1: returns the `Proposal` with `confirmation.confirmed_at == now.instant`, `state == dispatched` on dispatch; on executor response `state in {executed, failed}` and `executor_result = {status, applied_records[], applied_count, timestamp, source: "executor"}`.
  - Q2: state transition predicate: `dry_run ==> confirmed ==> dispatched ==> (executed | failed)`; exactly one `dry_run ==> confirmed` transition and exactly one `confirmed ==> dispatched` transition per `proposal_id`; `applied_count != len(affected_items)` (either fewer or **more**) `==> state == failed` and per-item results recorded (D33, D15-amendment). The `failed`/`executed` state and `executor_result` are written by the Dispatcher (Module-12-owned), never by the executor adapter (AD-13).
  - Q3: audit events emitted in order: `toolcall.confirm_and_dispatch`, `executor.dispatch`; on executor return the Audit Writer writes exactly one row with `actor == executor`, `proposal_id`, and `tool_call_id == null` (AD-10); metric `m12.proposal.dispatch.count` incremented.
  - Q4: the confirmation records no identity or role claim; the confirmation payload contains only `{proposal_id, gate_token}`; session context is never consulted (AD-5). The caption `S_CAP` is carried in `Proposal.confirmation.caption` (AD-5 amendment).
  - Q-fail: on any P1–P6 violation, no dispatch occurs, no executor call is made, and `state` is unchanged except `EXECUTOR_UNAVAILABLE` which sets `state == failed` (no auto-retry).
- **Invariant (I):**
  - L1: a proposal is dispatchable only from `state == confirmed`; each confirmed proposal yields exactly one executor call; a second dispatch of the same `proposal_id` is rejected (D32). Bound to: AD-3, AD-4, AD-15.
  - L2: a re-dispatch is a new `Proposal` (fresh dry-run + confirmation) with `supersedes_proposal_id` set to a parent in `state == failed`; superseding a parent in `state == dispatched` is rejected (D23, D32). Bound to: AD-3.
  - L3: dispatch requires `re-validated set == stored snapshot on (id, actionable status)`; if the provider is unavailable during re-validation, the safe-failure response returns and no dispatch occurs (AD-6, AD-12). Bound to: AD-6.
- **Concurrency / idempotency:** exactly-once per `proposal_id`; identical `(proposal_id, gate_token)` confirm is idempotent; any differing confirm against an already-dispatched proposal is rejected with HTTP 409 (D47). Two concurrent confirms race on the single writer; the first advances `state`, the second returns the persisted state.
- **Time:** Clock port for `confirmed_at`, executor `timestamp`, and the 5 s dispatch timeout (D31); timeout measured on the clock adapter.
- **Latency budget (NFR):** p95 <= 5500 ms including the 5 s executor timeout ceiling at 5 concurrent (allocated from NFR-5/NFR-7).

---

## 2. Inbound Port Contracts

Shared preamble for every inbound read route unless overridden:

- **P1:** path/query parameters match their declared type; a body, when present, validates against the named schema -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400).
- **P2:** referenced `session_id`/`{id}`/`{cid}` exists or is created per route -> violation: `SESSION_NOT_FOUND`/`ENTITY_NOT_FOUND`/`PROPOSAL_NOT_FOUND` (HTTP 404) unless the route is a conversational query (canonical `S_ENF`, HTTP 200).
- **Q2:** `operational_state_before == operational_state_after` (AD-1).
- **Q3:** one `ToolCall` audit row per underlying core/port call (AD-10).
- **Q-fail:** on P1/P2 violation the operation returns the typed error and performs no state change and no audit row for the rejected call; `operational_state_before == operational_state_after` and, for session-scoped routes, `session.context` is unchanged. Every route in this section inherits this Q-fail clause.
- **Canonical wire shape (D58):** a 200 canonical response is returned as an `ErrorBody` object whose `error_code` is the canonical code and whose `message` is the literal from the canonical-strings table. A bare unquoted string is never the response body.
- **L1:** the route exposes no state-mutating operation outside `/api/v1/destructive/*` and `/executor/v1/*` (route-local; AD-13, S-6).
- **Time:** Clock port only.
- **Latency budget:** as allocated per route below from NFR-5.

### Operation: `create_session(operator_role: OperatorRole) -> Session` — `POST /api/v1/sessions`

- **Layer:** Inbound Port
- **Precondition (P):** P1: `operator_role` matches `^role-[a-z0-9_-]{1,32}$` -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400).
- **Postcondition (Q):** Q1: returns `201` + `Session{session_id, created_at, operator_role, context: {resolved_entities: [], prior_intents: [], active_answer_ids: []}, status: active}`; Q2: exactly one `Session` row inserted; Q4: `session_id` matches `^sess-[0-9a-f]{16}$`.
- **Invariant (I):** L1: `session_id` unique (DB UNIQUE constraint). Bound to: AD-10.
- **Concurrency / idempotency:** not idempotent; each call creates a new session.
- **Time:** Clock port for `created_at`.
- **Latency budget (NFR):** p95 < 50 ms (allocated from NFR-5).

### Operation: `submit_query(session_id, query_text) -> AnswerEnvelope` — `POST /api/v1/sessions/{sid}/queries`

- **Layer:** Inbound Port
- **Precondition (P):** delegates `answer_query` P1–P3 plus body-schema validation (`query_text` required) -> violation: `VALIDATION_EMPTY_QUERY`/`VALIDATION_QUERY_TOO_LONG` (HTTP 400); `SESSION_NOT_FOUND` (HTTP 404) when the session is absent; `SESSION_EXPIRED` (HTTP 410) when `status in {reset, expired}` or idle `> 30 min` (the write-back to `expired` is idempotent); `PROVIDER_UNAVAILABLE` (HTTP 503).
- **Postcondition (Q):** Q1: HTTP 200 + `AnswerEnvelope`; Q3: audit rows for the turn; Q4: canonical codes (`ENTITY_NOT_FOUND`, `CANNOT_CONFIRM`, `CLARIFICATION`, `INTENT_NOT_SUPPORTED`, `ACTION_REFUSED`) return HTTP 200 with an `ErrorBody` whose `message` is the canonical literal (D58), not an error status and not a bare string.
- **Invariant (I):** inherits `L1–L3` of `answer_query`. Bound to: AD-8, AD-1, AD-2.
- **Concurrency / idempotency:** not idempotent; serialized per `session_id`.
- **Time:** Clock port; single `now` per request.
- **Latency budget (NFR):** p95 <= 3000 ms, p99 <= 8000 ms (NFR-5).

### Operation: `get_session(session_id) -> Session` — `GET /api/v1/sessions/{sid}`

- **Layer:** Inbound Port
- **Precondition (P):** P2: `session_id` exists -> violation: `SESSION_NOT_FOUND` (HTTP 404).
- **Postcondition (Q):** Q1: HTTP 200 + `Session` with full `context` and `turns[]`; Q4: fields rendered field-for-field.
- **Invariant (I):** read-only. Bound to: AD-1.
- **Concurrency / idempotency:** idempotent read.
- **Time:** none.
- **Latency budget (NFR):** p95 < 50 ms.

### Operation: `reset_session(session_id) -> void` — `DELETE /api/v1/sessions/{sid}`

- **Layer:** Inbound Port
- **Precondition (P):** P2: `session_id` exists -> violation: `SESSION_NOT_FOUND` (HTTP 404).
- **Postcondition (Q):** Q1: HTTP 204 No Content; Q2: `context == {resolved_entities: [], prior_intents: [], active_answer_ids: []}` and `status == reset`; in-flight requests are cancelled and any destructive flow returns to its refusal/dry-run stage; dispatched proposals remain tracked and their late executor result is surfaced (D34). Q3: audit `toolcall.reset_session`.
- **Invariant (I):** reset never authorizes a destructive action and never auto-continues a destructive flow (AD-4, AD-5). Bound to: AD-4.
- **Concurrency / idempotency:** idempotent; a second reset on a reset session returns 204.
- **Time:** Clock port for the reset timestamp.
- **Latency budget (NFR):** p95 < 100 ms.

### Operation: `get_state_record(entity_type, id) -> Record | CanonicalCode` — `GET /api/v1/state/{entity_type}/{id}`

- **Layer:** Inbound Port
- **Precondition (P):** P1: `{entity_type}` in the §0.2 route enum -> violation: `VALIDATION_BAD_ENTITY_TYPE` (HTTP 400); P1b: `{id}` matches the `{type}#{id}` `EntityKey` shape (id segment `^[A-Za-z0-9._-]{1,200}$`) before lookup -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400) (E15); P2: the record exists -> violation: `ENTITY_NOT_FOUND` (HTTP 404 with body `S_ENF`).
- **Postcondition (Q):** Q1: HTTP 200 + the record rendered field-for-field (FR-12); Q3: audit `toolcall.state.get`.
- **Invariant (I):** L1: response fields equal the provider record field-for-field on sampled records; no redaction of simulated-state identifiers (NFR-11). Bound to: AD-1.
- **Concurrency / idempotency:** idempotent read.
- **Time:** none.
- **Latency budget (NFR):** p95 < 50 ms.

### Operation: `browse_state(entity_type, q, page, page_size) -> {items: Record[], page, page_size, total} | CanonicalCode` — `GET /api/v1/state/{entity_type}?q=&page=&page_size=`

- **Layer:** Inbound Port
- **Precondition (P):** P1: `page >= 1`, `1 <= page_size <= 100`, and `page <= 10_000 / page_size` (bounded OFFSET) -> violation: `PAGINATION_INVALID` (HTTP 400) (E13). P2: `q` is compared case-folded on both sides against the stored id (`q.strip().casefold() == stored_id.casefold()`); an empty `q` returns the capped first page (AD-7, E25).
- **Postcondition (Q):** Q1: HTTP 200 + `items` with `len(items) <= page_size`; a page beyond `total` returns `items: []` together with the same `total` (no error, E13); `total` is the matched count clamped to the store cap, never an unbounded count beyond it (E49); Q3: audit `toolcall.state.browse`.
- **Invariant (I):** L1: the result is capped and paginated; unbounded lists are impossible (D46). Bound to: AD-13.
- **Concurrency / idempotency:** idempotent read.
- **Time:** none.
- **Latency budget (NFR):** p95 < 100 ms.

### Operation: `get_answer_evidence(answer_id) -> EvidenceSet` — `GET /api/v1/answers/{aid}/evidence`

- **Layer:** Inbound Port
- **Precondition (P):** P2: `answer_id` exists -> violation: `ENTITY_NOT_FOUND` (HTTP 404).
- **Postcondition (Q):** Q1: HTTP 200 + ordered `EvidenceSet` (`position` ascending); Q3: audit `toolcall.evidence.get`.
- **Invariant (I):** L1: returned entries are a subset of the stored answer `EvidenceSet`, unchanged. Bound to: AD-14.
- **Concurrency / idempotency:** idempotent read.
- **Time:** none.
- **Latency budget (NFR):** p95 < 50 ms.

### Operation: `get_citation(citation_id) -> {source_record: Record, snippet: Snippet} | CanonicalCode` — `GET /api/v1/citations/{cid}`

- **Layer:** Inbound Port
- **Precondition (P):** P2: `citation_id` resolves to an existing source -> violation: `ENTITY_NOT_FOUND` (HTTP 404 with body `S_ENF`).
- **Postcondition (Q):** Q1: HTTP 200 + the source record and the stored snippet; the source record must be a member of the answer's `EvidenceSet` (AD-8); Q3: audit `toolcall.citation.get`.
- **Invariant (I):** L1: a citation whose source is absent from the `EvidenceSet` never renders; the answer downgrades to `S_CNC` at answer level. Bound to: AD-8.
- **Concurrency / idempotency:** idempotent read.
- **Time:** none.
- **Latency budget (NFR):** p95 < 50 ms.

### Operation: `get_runbook(error_code) -> RunbookTemplate | CanonicalCode` — `GET /api/v1/runbooks/{error_code}`

- **Layer:** Inbound Port
- **Precondition (P):** P1: `error_code` matches `^[A-Za-z0-9._-]{1,64}$` -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400); P2: a template exists for the exact code -> violation: `RUNBOOK_NOT_FOUND` (HTTP 404 with body `no runbook available for code {error_code}.`, byte-identical to `S_RBX`, D57).
- **Postcondition (Q):** Q1: HTTP 200 + `{steps, provenance}` as two separate sections (AD-9); Q3: audit `toolcall.runbook.get`.
- **Invariant (I):** inherits `lookup_runbook` `L1–L2`. Bound to: AD-9.
- **Concurrency / idempotency:** idempotent read.
- **Time:** none.
- **Latency budget (NFR):** p95 < 50 ms — a pure registry lookup delegating to `lookup_runbook` (< 5 ms); no generation happens on the read path (D56).

### Operation: `get_audit_page(session_id, page, page_size) -> {entries: AuditRecord[], page, page_size}` — `GET /api/v1/sessions/{sid}/audit?page=&page_size=`

- **Layer:** Inbound Port
- **Precondition (P):** P1: pagination valid -> violation: `PAGINATION_INVALID` (HTTP 400); P2: `session_id` exists -> violation: `SESSION_NOT_FOUND` (HTTP 404).
  - **Postcondition (Q):** Q1: HTTP 200 + entries in chronological order (ordered by `(timestamp, audit_id)` ascending for a deterministic tiebreak), `len(entries) <= page_size`, and page depth never exceeds the 10,000-row retention cap; a page beyond the retained rows returns `entries: []` together with the retained total (D50, E14, E47); Q3: the audit read itself is not audited (read of the audit log).
- **Invariant (I):** L1: no update/delete path is exposed; entries contain no credentials (key-name-driven redaction, D45). Bound to: AD-10.
- **Concurrency / idempotency:** idempotent read.
- **Time:** none.
- **Latency budget (NFR):** p95 < 100 ms.

### Operation: `post_dry_run(query_text, action, target_refs, session_id) -> Proposal` — `POST /api/v1/destructive/dry-runs`

- **Layer:** Inbound Port
- **Precondition (P):** delegates `propose_destructive_action` P1–P4 -> violations: `VALIDATION_MALFORMED_BODY` (400), `SESSION_NOT_FOUND` (404), `ENTITY_NOT_FOUND` (200 canonical `S_ENF`), `CLARIFICATION_REQUIRED` (200 canonical).
- **Postcondition (Q):** Q1: HTTP 200 + `Proposal` with `state == dry_run`, `gate_token`, `dry_run_snapshot`; Q3: audit + `m12.destructive.refused.count`; Q4: refusal body carries `S_ARF`.
- **Invariant (I):** inherits `propose_destructive_action` `L1–L2`. Bound to: AD-4, AD-6.
- **Concurrency / idempotency:** not idempotent; new `proposal_id` per call.
- **Time:** Clock port for `snapshot_timestamp`.
- **Latency budget (NFR):** p95 <= 2000 ms.

### Operation: `post_confirm(proposal_id, gate_token) -> Proposal` — `POST /api/v1/destructive/proposals`

- **Layer:** Inbound Port
- **Precondition (P):** delegates `confirm_and_dispatch` P1–P6; the confirmation request is a distinct HTTP request from the original query and the payload carries only `{proposal_id, gate_token}` (no identity/role) -> violation: `PROPOSAL_NOT_FOUND` (404), `GATE_TOKEN_INVALID` (403), `CONFIRMATION_STALE` (409), `DRY_RUN_EMPTY_SET` (409), `CONFIRMATION_CONFLICT` (409), `EXECUTOR_UNAVAILABLE` (503).
- **Postcondition (Q):** Q1: HTTP 200 + `Proposal` in `{dispatched, executed, failed}`; if the executor result is `partial`, the dispatcher additionally returns HTTP 502 `EXECUTOR_PARTIAL_APPLY` with the `Proposal` body (AD-15 amendment, A16); Q3: audit rows per AD-10; Q4: caption `S_CAP` is carried in `Proposal.confirmation.caption` (AD-5 amendment, A15).
- **Invariant (I):** inherits `confirm_and_dispatch` `L1–L3`; no identity/role is recorded; session context is never consulted. Bound to: AD-3, AD-4, AD-5, AD-6, AD-15.
- **Concurrency / idempotency:** identical `(proposal_id, gate_token)` is idempotent; differing confirm on a dispatched proposal -> HTTP 409 (D47).
- **Time:** Clock port; 5 s dispatch timeout.
- **Latency budget (NFR):** p95 <= 5500 ms.

### Operation: `get_proposal(proposal_id) -> Proposal` — `GET /api/v1/destructive/proposals/{pid}`

- **Layer:** Inbound Port
- **Precondition (P):** P2: `proposal_id` exists -> violation: `PROPOSAL_NOT_FOUND` (HTTP 404).
- **Postcondition (Q):** Q1: HTTP 200 + `Proposal` with `executor_result` when resolved.
- **Invariant (I):** read-only. Bound to: AD-1.
- **Concurrency / idempotency:** idempotent read.
- **Time:** none.
- **Latency budget (NFR):** p95 < 50 ms.

### Operation: `post_re_dispatch(parent_proposal_id, query_text, action, target_refs) -> Proposal` — `POST /api/v1/destructive/proposals/{pid}/re-dispatches`

- **Layer:** Inbound Port
- **Precondition (P):** P1: `parent.state == failed` -> violation: `PROPOSAL_STATE_INVALID` (HTTP 409); P2: `parent.state != dispatched` -> violation: `PROPOSAL_STATE_INVALID` (HTTP 409) (D32); P3: parent resolves -> violation: `PROPOSAL_NOT_FOUND` (HTTP 404); P4: the parent's dry-run affected set was non-empty (a zero-actionable dry-run is never re-dispatchable) -> violation: `DRY_RUN_EMPTY_SET` (HTTP 409) (E4).
- **Postcondition (Q):** Q1: HTTP 200 + a NEW `Proposal` with `state == dry_run`, `supersedes_proposal_id == parent_proposal_id`; Q2: parent `state` is unchanged if already applied else `superseded`; Q3: audit for the new dry-run.
- **Invariant (I):** L1: re-dispatch is a new proposal through the full confirmation gate; never a second dispatch of a confirmed proposal. Bound to: AD-3.
- **Concurrency / idempotency:** each call creates a distinct proposal.
- **Time:** Clock port.
- **Latency budget (NFR):** p95 <= 2000 ms.

### Operation: `executor_post_proposal(body: ExecutorRequest) -> ExecutorResult` — `POST /executor/v1/proposals` (simulated executor)

- **Layer:** Outbound Port (external/simulated executor adapter; replacement point)
  - **Precondition (P):** P1: `body` validates against the frozen schema `{proposal_id, action, selector, gate_token, dry_run_ref}` and `dry_run_ref.proposal_id == proposal_id` -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400); P2: `gate_token` validates against the stored proposal -> violation: `GATE_TOKEN_INVALID` (HTTP 403); P3: no prior applied record exists for `proposal_id` -> an **identical retry** of an already-processed proposal returns the stored `ExecutorResult` (HTTP 200) instead of an error; a **differing** second apply is -> violation: `EXECUTOR_DUPLICATE_APPLY` (HTTP 409) (E35).
  - **Postcondition (Q):** Q1: applies exactly the referenced snapshot's `affected_items` (the executor never re-enumerates scope) and returns HTTP 200 `{status in {applied, partial, failed}, applied_records[], applied_count, timestamp, source: "executor"}`; Q2: applied state predicate: for each `item.key` in the snapshot, the item's actionable field is set exactly once; Q3: result written by the Audit Writer with `actor == executor` and `tool_call_id == null`; Q4: `applied_count < len(affected_items) ==> status == partial`; `applied_count > len(affected_items)` is rejected as executor failure/`partial`, never a larger-than-scope success (E5). The executor does **not** write proposal state — the Dispatcher records `state == failed` (AD-13, A17).
- **Invariant (I):** L1: the contract schema is frozen; the adapter is the only replacement point (AD-15). Bound to: AD-15.
- **Concurrency / idempotency:** exactly-once per `proposal_id`; a second applied record for the same `proposal_id` surfaces as executor failure, never a second success. Bound to: AD-3.
- **Time:** the executor adapter takes its **own** injected Clock read for the result `timestamp` (never reuses the turn's `now`), so `applied` can never appear before `dispatched` (AD-15, E44).
- **Latency budget (NFR):** responds within 5000 ms or the dispatcher marks `failed` (D31).

### Operation: `executor_get_proposal(proposal_id) -> ExecutorResult` — `GET /executor/v1/proposals/{pid}`

- **Layer:** Outbound Port
- **Precondition (P):** `proposal_id` resolves in the executor -> violation: `PROPOSAL_NOT_FOUND` (HTTP 404).
- **Postcondition (Q):** Q1: HTTP 200 + the stored executor result.
- **Invariant (I):** read-only. Bound to: AD-1.
- **Concurrency / idempotency:** idempotent read.
- **Time:** Clock port.
- **Latency budget (NFR):** p95 < 50 ms.

---

## 3. Outbound Port Read Contracts (all permitted read operations)

These are the only read paths to operational state and policy (AD-1, AD-13). **Shared preamble — `ReadPortOp` base:** every operation below has

- **P-port-1:** each parameter matches its declared type; `id` non-empty `len <= 200` -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400).
- **P-port-2:** the adapter is reachable and its fixture/store loads -> violation: `PROVIDER_UNAVAILABLE` (HTTP 503 with body `S_PUA`).
- **Q-port-1:** returns the declared type(s) with the exact field set of §0.3; for a single-record miss returns `null`.
- **Q-port-2 (state predicate):** `store_before == store_after` — no write path exists in the interface (AD-1).
- **Q-port-3:** emits exactly one `ToolCall` audit row named `toolcall.<port>.<method>` per call (redacted at write, NFR-11).
- **Q-fail:** on P-port-2 failure, returns `PROVIDER_UNAVAILABLE`; the caller aborts the pipeline before prose (AD-12).
- **I-port-1:** the interface declares only query methods and no mutating method (static import audit). Bound to: AD-1, AD-13.
- **Time:** operations that take no `Instant` read no time; operations with a time predicate receive the window from the caller (Clock port owns `now`).
- **Latency:** every read op p95 < 5 ms at 5 concurrent (allocated from NFR-5, in-process fixtures).

### OP-1 `users_port`
- **Operations:** `get(id) -> UserRecord|null`; `browse(q, page, page_size) -> UserRecord[]`; `by_ids(ids: EntityKey[]) -> UserRecord[]`.
- **Distinct P:** `by_ids` requires every `EntityKey.type == user` -> violation: `VALIDATION_BAD_ENTITY_TYPE` (400).
- **Distinct Q:** `browse` returns `len <= page_size` (cap 100, D46) matching the case-folded exact-id rule.
- **I:** user `id` unique in the fixture index. Bound to: AD-7.

### OP-2 `catalog_port` (model catalog)
- **Operations:** `get(model_id) -> ModelCatalogEntry|null`; `browse(q, page, page_size) -> ModelCatalogEntry[]`.
- **Distinct Q:** `allowed_roles` is a subset of `{student, staff, faculty, privileged}`.
- **I:** `model_id` unique. Bound to: AD-7.

### OP-3 `policy_port`
- **Operations:** `get(clause_id) -> AccessPolicyClause|null`; `for_model(model_id) -> AccessPolicyClause[]`; `browse(q, page, page_size)`.
- **Distinct P:** `for_model` requires `model_id` to exist in `catalog_port` -> violation: `ENTITY_NOT_FOUND` (200 canonical `S_ENF`).
- **Distinct Q:** `reason_class in {not-in-allowlist, quota, window}`.
- **I:** `clause_id` unique; clauses returned in stable `clause_id` order for determinism. Bound to: AD-2, AD-14.

### OP-4 `groups_port`
- **Operations:** `get(group_id) -> GroupRecord|null`; `browse(q, page, page_size)`.
- **Distinct P:** every `members` entry is a `user` `EntityKey` at the provider boundary -> violation: `VALIDATION_BAD_ENTITY_TYPE` (HTTP 400) for any non-user member (E45).
- **Distinct Q:** `members` entries are `user` `EntityKey`s.

### OP-5 `jobs_port`
- **Operations:** `get(job_id) -> JobRecord|null`; `select(selector: Selector) -> JobRecord[]`; `browse(q, page, page_size)`.
- **Distinct Q:** `select` returns every record matching `selector`, bounded by the operational-store cap of 10,000 rows (D50); it is the dry-run enumeration source and is therefore exempt from the browse `page_size <= 100` cap **but not** from the store cap — an unbounded `select` is impossible (D46, A6). Ordering is by `id` ascending for determinism; `status in {pending, running, succeeded, cancelled, failed}`.
- **I:** the result of `select` is the exact input to `dry_run_snapshot.affected_items`; identical `(selector, snapshot)` yields an identical ordered set. Bound to: AD-2, AD-6.

### OP-6 `nodes_port`
- **Operations:** `get(node_id) -> NodeRecord|null`; `select(selector: Selector) -> NodeRecord[]`; `browse(q, page, page_size)`.
- **Distinct Q:** `cordoned` is `boolean`; `error_code` may be `null` (D43). `select` is the enumeration source for `cordon_node`/`drain_node` dry-runs, bounded by the store cap; the resolved `target_refs` populate `Selector.params.node_ids` (D55, A7).

### OP-7 `reservations_port`
- **Operations:** `get(reservation_id) -> ReservationRecord|null`; `browse(q, page, page_size)`.
- **Distinct Q:** `[start, end)` is a half-open interval.

### OP-8 `windows_port`
- **Operations:** `get(window_id) -> PolicyWindow|null`; `list() -> PolicyWindow[]`.
- **Distinct Q:** `list` returns all windows in stable `window_id` order for the window calculator.
- **I:** `window_id` unique. Bound to: AD-2, AD-14.

### OP-9 `event_store_port`
- **Operations:** `query(entity_ref: EntityKey, type: EventType, window: {start: Instant, end: Instant}) -> OperationalEvent[]`.
- **Distinct P:** `type in {access_denied, job_cancelled, node_cordoned}` -> violation: `VALIDATION_MALFORMED_BODY` (400); `start < end` (half-open) -> violation: `VALIDATION_MALFORMED_BODY` (400).
- **Distinct Q:** returns every event with `timestamp` in `[start, end)` and matching `entity_ref`/`type`, ordered by `timestamp` ascending then `event_id` ascending; `recorded_reason` read directly (D25).
- **I:** event matching is half-open `[start, end)` (D40). Bound to: AD-2.

### OP-10 `clock_port`
- **Operations:** `now() -> ClockRead`.
- **Distinct P:** none (always available); a simulated/adapter failure -> violation: `CLOCK_UNAVAILABLE` (HTTP 503 with body `S_PUA`).
- **Distinct Q:** returns a unique `read_id` (`^clk-[0-9a-f]{16}$`), `instant` ISO-8601 UTC, `source == "clock"`.
- **I:** every component with time rules receives this port; the deterministic core never calls `datetime.now()`/`time.time()`. Bound to: AD-2, DP-5.

### OP-11 `policy_content_port`
- **Operations:** `get(source_id) -> {source_id, text, version}`.
- **Distinct P:** `source_id` resolves in the curated policy-content set -> violation: `ENTITY_NOT_FOUND` (200 canonical `S_ENF`).
- **Distinct Q:** `text` length `1 <= len <= 2000`; content treated as data, never control (AD-11).

### OP-12 `runbook_registry_port`
- **Operations:** `get(error_code) -> RunbookTemplate|null`; `register(template) -> void` (registration-time validation, D44).
- **Distinct P:** `register` requires `len(template.steps) >= 1` -> violation: `RUNBOOK_TEMPLATE_EMPTY` (HTTP 422); `template.physical_intervention == true` requires `approved_source != null` -> violation: `RUNBOOK_TEMPLATE_UNSOURCED` (HTTP 422).
- **Distinct Q:** `get` returns the registered template with `steps` and `provenance` as separate sections; exact-code lookup.
- **I:** no registered template has an empty step list; a physical-intervention template without an approved source is never served. Bound to: AD-9.

### 3.1 Outbound Generation & Prose Port Contracts (OP-13, OP-14, OP-15)

The non-read outbound ports. Like the read ports, they are dependency-inverted: `service/core` and `service/application` import only the interface; the adapter is injected (R3). No other component may generate an id, call the LLM directly, or dispatch to the executor.

#### OP-13 `idgen_port`
- **Operations:** `new_id(kind: IdKind) -> IdString`.
- **Distinct P:** `kind in IdKind` -> violation: `VALIDATION_BAD_ID_KIND` (HTTP 400).
- **Distinct Q:** returns a fresh `IdString` matching the per-kind format of §0.1; the value is unique within the prototype store.
- **Distinct Q2:** successive calls never return the same value; the seeded simulated adapter persists its counter (or seeds it from the current store maximum) so a process restart never reissues an already-persisted id (E43). Under seed, the sequence is fixed so FR-14 runs reproduce the same ids.
- **I:** no component draws ids from `uuid4`/`random` directly; every generated id crosses this port (R2). Bound to: AD-2, DP-5.
- **Latency:** < 1 ms at 5 concurrent.

#### OP-14 `llm_prose_port`
- **Operations:** `compose(prompt: ProsePrompt) -> ProseText`.
- **Distinct P:** `prompt.evidence_sections` carry only §0.4 evidence tokens and are delimited as data (AD-11). Composition is attempted at most twice — one initial call plus at most one retry after a lexical-guard rejection (D48); a rejection after the retry fails the answer.
- **Distinct Q:** returns `ProseText` containing zero evidence-vocabulary tokens (entity ids, clause ids, observed values, clock-derived facts). On any hit the port rejects the whole prose and retries once; it never strips mid-sentence (D48). A second rejection -> violation: `LLM_PROSE_REJECTED` (HTTP 503).
- **Distinct Q2:** a call exceeding 5000 ms -> violation: `LLM_UNAVAILABLE` (HTTP 503).
- **I:** prose is connective only; no diagnosis, claim, citation, or recommendation field is ever read from prose output (AD-2). Bound to: AD-2, AD-8, AD-11, AD-12.
- **Latency:** p95 <= 3000 ms for the single prose call (allocated from NFR-5; identical to the `answer_query` sub-budget, D56).

#### OP-15 `executor_port`
- **Operations:** `dispatch(request: ExecutorRequest) -> ExecutorResult`; `get(proposal_id) -> ExecutorResult`.
- **Distinct P:** `request.dry_run_ref.proposal_id == request.proposal_id`; the port is called only by `confirm_and_dispatch` -> violation: `VALIDATION_MALFORMED_BODY` (HTTP 400).
- **Distinct Q:** returns the frozen `ExecutorResult` = `{status: ExecutorStatus, applied_records: EntityKey[], applied_count: integer, timestamp: Instant, source: "executor"}`; `applied_count != len(affected_items)` yields `status == partial` (or `failed`), never a larger-than-scope success. The port performs **zero** writes to Module-12-owned proposal state (AD-13).
- **Distinct Q2:** the adapter takes its own Clock read for `timestamp` (never reuses the caller's `now`).
- **I:** the interface is the frozen AD-15 replacement point; only a driving adapter (`service/api/executor/`) and the dispatcher may touch it. Bound to: AD-15, AD-3.
- **Latency:** responds within 5000 ms or the dispatcher marks `failed` (D31).

---

## 4. Typed Error Catalog (shared by all operations)

| CODE | HTTP / exit | Trigger | Human-readable explanation template | Retryable |
|---|---|---|---|---|
| `VALIDATION_EMPTY_QUERY` | 400 | `len(trim(query_text)) == 0` | `Query must contain between 1 and 1000 characters; received 0.` | N |
| `VALIDATION_QUERY_TOO_LONG` | 400 | `len(trim(query_text)) > 1000` | `Query exceeds 1000 characters; received {n}.` | N |
| `VALIDATION_MALFORMED_BODY` | 400 | body fails JSON/schema validation | `Request body does not match schema {schema_id}.` | N |
| `VALIDATION_BAD_ENTITY_TYPE` | 400 | `{entity_type}`/`EntityKey.type` outside §0.2 | `Unknown entity type {value}; expected one of {enum}.` | N |
| `VALIDATION_BAD_ACTION` | 400 | `action` outside `ActionVerb` | `Unknown action {value}; expected one of {delete_jobs,cancel_jobs,cordon_node,drain_node}.` | N |
| `VALIDATION_BAD_ID_KIND` | 400 | `kind` outside `IdKind` | `Unknown id kind {value}; expected one of {enum}.` | N |
| `PAGINATION_INVALID` | 400 | `page < 1` or `page_size > 100` | `Invalid pagination: page_size {v} exceeds cap 100.` | N |
| `SESSION_NOT_FOUND` | 404 | `session_id` absent | `Session {sid} not found.` | N |
| `SESSION_EXPIRED` | 410 | idle `> 30 min` (D51) | `Session {sid} expired after 30 minutes idle.` | N (start new) |
| `ENTITY_NOT_FOUND` | 404 (state/citation/proposal routes); 200 canonical (query/dry-run routes) | reference unresolved | `Entity Not Found in State: {ref_list}.` | N |
| `CANNOT_CONFIRM` | 200 | entity exists, evidence insufficient | `Cannot confirm (insufficient evidence): checked {checked_list}.` | N |
| `CLARIFICATION_REQUIRED` | 200 | no intent match, ambiguous bare type, or compound destructive | `Clarification required: {reason}.` | N |
| `INTENT_NOT_SUPPORTED` | 200 | intent not registered | `Clarification required: intent not supported.` | N |
| `PROVIDER_UNAVAILABLE` | 503 | any provider read raises/timeouts | `Provider unavailable — cannot answer.` | Y |
| `CLOCK_UNAVAILABLE` | 503 | clock port read fails | `Provider unavailable — cannot answer.` | Y |
| `LLM_UNAVAILABLE` | 503 | Ollama prose call timeout | `Provider unavailable — cannot answer.` | Y |
| `LLM_PROSE_REJECTED` | 503 | forbidden token in prose on both attempts (D48) | `Provider unavailable — cannot answer.` | Y |
| `AUDIT_WRITE_FAILED` | 500 | audit insert fails after a tool call succeeded (D41) | `Audit write failed for tool call {tool_call_id}.` | Y |
| `ACTION_REFUSED` | 200 | destructive intent classified | `Action refused.` | N |
| `PROPOSAL_NOT_FOUND` | 404 | `proposal_id` absent | `Proposal {pid} not found.` | N |
| `PROPOSAL_STATE_INVALID` | 409 | transition not permitted from current state | `Proposal {pid} in state {state}; {action} not permitted.` | N |
| `GATE_TOKEN_INVALID` | 403 | `gate_token != proposal.gate_token` | `Gate token invalid for proposal {pid}.` | N |
| `CONFIRMATION_STALE` | 409 | re-queried `(id, actionable status)` set differs from snapshot (AD-6) | `Snapshot stale: {delta}.` | N |
| `DRY_RUN_EMPTY_SET` | 409 | `len(affected_items) == 0` at confirm | `0 affected items; confirmation disabled.` | N |
| `CONFIRMATION_CONFLICT` | 409 | differing confirm on an already-dispatched proposal (D47) | `Proposal {pid} already {state}; confirmation rejected.` | N |
| `EXECUTOR_UNAVAILABLE` | 503 | executor no response within 5000 ms or unreachable (D31) | `Provider unavailable — cannot answer.` | Y |
| `EXECUTOR_PARTIAL_APPLY` | 502 surfaced by the dispatcher `post_confirm`; the executor route itself returns HTTP 200 with `status: partial` | `applied_count != len(affected_items)` (D33, E5) | `Executor applied {applied_count} of {n} items.` | N |
| `EXECUTOR_DUPLICATE_APPLY` | 409 | second applied record for the same `proposal_id` | `Duplicate apply for proposal {pid}.` | N |
| `RUNBOOK_NOT_FOUND` | 404 route; 200 canonical query | unknown code or code/node mismatch or null code (D43) | `no runbook available for code {code}.` | N |
| `RUNBOOK_TEMPLATE_EMPTY` | 422 | registration of a template with `len(steps) == 0` (D44) | `Runbook template {template_id} rejected: steps list is empty.` | N |
| `RUNBOOK_TEMPLATE_UNSOURCED` | 422 | physical-intervention template without `approved_source` | `Runbook template {template_id} rejected: physical-intervention steps lack an approved source.` | N |

---

## 5. Invariant Binding Table

Every invariant below has an enforcement point other than "the developer must remember it". A row whose enforcement point is a DB constraint, a state-machine guard, or a pure-function property is admissible; an invariant with only a review rule is not listed.

| Invariant | AD-n it enforces | Enforcement point | Test that turns RED if removed |
|---|---|---|---|
| I1 `answer_query` zero operational-state writes | AD-1, AD-13 | Provider port interfaces declare no mutating method; static import audit over `service/core` and `service/application`; instrumentation counter on operational stores | `tests/safety_instrumentation` (NFR-8): copilot-originated mutations `== 0` |
| I2 `answer_query` deterministic evidence/citation/class/runbook | AD-2, AD-14 | `EvidenceSet` UNIQUE `(answer_id, citation_id)` + `position NOT NULL`; pure-function diagnosers; single LLM prose call | `tests/determinism` (FR-14): 3× identity of membership, position sequence, citation set, class, steps |
| I3 every factual claim cited | AD-8, AD-14 | `claim_citations` join `>= 1` per claim; renderer guard refusing a citation absent from `EvidenceSet` | `tests/citation_coverage` (FR-13): 0 uncited claims; 100% resolve |
| I4 `resolve_entities` exact, no fabrication | AD-7, NFR-2 | Resolver pure function; provider index UNIQUE id; case-fold compare | `tests/anti_fabrication` (FR-03): 100% `S_ENF`, fabricated rate `== 0` |
| I5 `EvidenceSet` unique + monotonic `position` | AD-14 | DB UNIQUE `(answer_id, citation_id)`; `position` NOT NULL, assigned at assembly | `tests/determinism` (FR-14) position-sequence assertion |
| I6 window half-open `[start, end)` | AD-2, D38 | `diagnose_schedule_window` pure predicate `start <= t < end` | `tests/window_boundary`: `t == end` yields next window, not open |
| I7 event match half-open `[start, end)` | AD-2, D40 | `event_store_port.query` predicate | `tests/event_window`: boundary timestamp matched once |
| I8 runbook steps only from registered template | AD-9 | Registry exact-code lookup; `register` rejects `len(steps) == 0` (422); unsourced physical template renders unavailability | `tests/runbook` (FR-07/08): 100% step-match, 0 fabricated steps |
| I9 dispatch only from `confirmed` | AD-3, AD-4 | Proposal state-machine guard in `confirm_and_dispatch`; DB CHECK on `state` enum | `tests/safety_instrumentation`: dispatch from non-confirmed rejected |
| I10 exactly-once dispatch per confirmed proposal | AD-3, AD-15 | `confirm_and_dispatch` single-call guard; Audit Writer rejects a second applied record for `proposal_id` | `tests/safety_instrumentation`: exactly one dispatch + one applied mutation (FR-10) |
| I11 snapshot re-validation on `(id, actionable status)` | AD-6 | Confirmation Gate re-executes stored `selector`; compares to snapshot | `tests/dryrun_revalidation`: changed set refuses dispatch with delta |
| I12 confirmation records no identity; session context not consulted | AD-5 | Confirmation payload schema `{proposal_id, gate_token}` only; code path has no role read | `tests/confirmation_semantics`: no role/identity field stored or read |
| I13 re-dispatch is a new proposal | AD-3, D23/D32 | `supersedes_proposal_id` self-FK; guard allows supersede only from `failed` | `tests/re_dispatch`: parent `dispatched` cannot be superseded |
| I14 exactly one audit row per tool call; append-only | AD-10 | `AuditRecord` delete/update-denying SQLite trigger; single Audit Writer | `tests/audit` (FR-11): 50-call session, 1 row each; delete/edit fail |
| I15 audit secret-free (key-name driven) | AD-10, NFR-11, D45 | Write-time redaction filter on credential-named keys | `tests/audit_redaction`: 0 secrets in sampled entries |
| I16 content/query are data, never control | AD-11 | Rule-based classifier; delimited data sections in prompt; bounded renderer | `tests/injection_corpus` (FR-15): 100% behavioral parity; 0 destructive triggers |
| I17 safe failure on any dependency | AD-12 | Typed `ok|failure` result at each pipeline stage; abort before prose | `tests/fault_injection` (FR-16): 100% explicit degradation, 0 fabricated detail |
| I18 no control-plane expansion | AD-13 | Port interface declarations; API route table; static route audit | `tests/route_audit` + import audit: no mutating route outside destructive/executor |
| I19 time reads only via Clock port | AD-2, DP-5 | Injected `clock_port`; static check banning `datetime.now()`/`time.time()` in `service/core` | `tests/determinism`: frozen clock yields identical output |
| I20 stores capped 10,000 rows, oldest-first rotation | AD-10, D50 | Retention job; delete-denying trigger exemption for the rotation-writer identity (D42) | `tests/retention`: cap honored, oldest evicted first, rotation logged |
| I21 executor contract frozen; adapter is replacement point | AD-15 | `ExecutorRequest` schema validation on ingress; fixed response shape | `tests/executor_contract`: schema conformance; double-apply surfaces failure |
| I22 browse is capped/paginated | AD-13, D46 | `browse_state` `page_size <= 100` guard | `tests/browse_cap`: unbounded list impossible |

---

## 6. Operation → FR / AD Coverage

| Operation | Layer | FRs | ADs |
|---|---|---|---|
| `answer_query` | Application (orchestrator) | FR-01, FR-04–06, FR-13, FR-14 | AD-1, AD-2, AD-8, AD-11, AD-12, AD-14 |
| `resolve_entities` | Core Domain | FR-03 | AD-7 |
| `assemble_evidence` | Core Domain | FR-13, FR-14 | AD-2, AD-14, AD-12 |
| `diagnose_access_denial` | Core Domain | FR-04 | AD-2, AD-8 |
| `diagnose_schedule_window` | Core Domain | FR-05 | AD-2, D38, D39, D30 |
| `diagnose_retrospective` | Core Domain | FR-06 | AD-2, D25, D40 |
| `diagnose_node_triage` | Core Domain | FR-07, FR-08 | AD-9 |
| `lookup_runbook` | Core Domain | FR-07, FR-08 | AD-9, D43, D44 |
| `propose_destructive_action` | Core Domain | FR-09 | AD-3, AD-4, AD-6 |
| `confirm_and_dispatch` | Core Domain | FR-09, FR-10 | AD-3, AD-4, AD-5, AD-6, AD-15 |
| Inbound read routes (`create_session`…`get_audit_page`) | Inbound Port | FR-02, FR-11, FR-12, FR-13 | AD-1, AD-10, AD-13 |
| `post_dry_run` / `post_confirm` / `post_re_dispatch` / `get_proposal` | Inbound Port | FR-09, FR-10 | AD-3, AD-4, AD-5, AD-6 |
| `executor_post_proposal` / `executor_get_proposal` | Outbound Port | FR-10 | AD-15, AD-3 |
| Outbound read ports OP-1…OP-12 | Outbound Port | FR-03, FR-05, FR-06, FR-07, FR-12 | AD-1, AD-2, AD-7, AD-9, AD-13, AD-14 |
| Outbound generation/prose/executor ports OP-13 `idgen_port`, OP-14 `llm_prose_port`, OP-15 `executor_port` | Outbound Port | FR-01, FR-02 (ids); FR-13, FR-15 (prose); FR-10 (executor) | AD-2, AD-8, AD-11, AD-12, AD-15, DP-5 |

**Read-operation inventory (permitted reads, complete):** OP-1 users, OP-2 catalog, OP-3 policy, OP-4 groups, OP-5 jobs, OP-6 nodes, OP-7 reservations, OP-8 windows, OP-9 event log, OP-10 clock, OP-11 policy content, OP-12 runbook registry — plus the inbound read routes `get_session`, `get_state_record`, `browse_state`, `get_answer_evidence`, `get_citation`, `get_runbook`, `get_audit_page`, `get_proposal`, `executor_get_proposal`. Writes are confined to the Module-12-owned stores (Session, Answer, Evidence, Claim, ToolCall, AuditRecord, Proposal) and the single executor boundary.
