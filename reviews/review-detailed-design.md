---
type: review
reviewer: adversarial-general (cynical), edge-case-hunter (path tracer)
target: planning/detailed-design/ (contracts.md, ports-and-adapters.md, schemas/*)
focus: two lenses — adversarial (what is missing/wrong) and edge-case-hunter (unhandled paths and boundaries)
scope: contracts.md §0–§6; ports-and-adapters.md; schemas/001_module12_copilot_schema.sql, dto.py, events.md, events.schema.json, openapi.yaml, phase-2.3-cross-check.md
sources-read:
  - planning/detailed-design/contracts.md (full)
  - planning/detailed-design/ports-and-adapters.md (full)
  - planning/detailed-design/schemas/001_module12_copilot_schema.sql (full)
  - planning/detailed-design/schemas/dto.py (full)
  - planning/detailed-design/schemas/events.md (full)
  - planning/detailed-design/schemas/events.schema.json (full)
  - planning/detailed-design/schemas/openapi.yaml (full)
  - planning/detailed-design/schemas/phase-2.3-cross-check.md (full)
date: 2026-10-16
verdict: contracts are unusually disciplined, but the two lenses surface 80 reconcilable defects — an inverted condition, unreachable states, enum/schema gaps, and boundary conditions with no guard
---

# Dual-Lens Review — Module 12 Detailed Design

Two lenses, findings recorded raw and then triaged:

- **Lens 1 — Adversarial (cynical).** Descriptions only, no severity/priority/ranking. IDs `A1…A30`.
- **Lens 2 — Edge-case hunter (path tracer).** Only unhandled paths/boundaries, emitted in the lens output format (JSON). IDs `E1…E29`.

Triage is per finding: **Accept / Defer / Reject**, with reason, owner #, and the exact target section(s). "Corrected?" flips to ☑ only when the change lands.

---

## Lens 1 — Adversarial (raw findings)

- **A1** — `contracts.md:248-254` `diagnose_node_triage` P3 is logically inverted: it states "`error_code is not null` -> violation: `RUNBOOK_NOT_FOUND` … X = `null`", meaning a *present* code is rejected, while the miss case it describes requires the code to be *absent*. The condition should be `error_code is null`.
- **A2** — `contracts.md:312-320` In `confirm_and_dispatch`, P1 requires `state == dry_run` and raises `PROPOSAL_STATE_INVALID` for any other state, yet P5 promises an "identical `(proposal_id, gate_token)` repeated confirm is treated as idempotent". After the first dispatch the state is `dispatched`, so P1 fires before P5; the idempotent path is unreachable as ordered.
- **A3** — `contracts.md:116-137` `answer_query` is filed under "1. Core Domain Contracts" and claims a core-domain layer, but §0.6 defines Core Domain as "no I/O, no LLM, no HTTP" while `answer_query` calls provider ports and the LLM prose port. The layer assignment contradicts the layer definition.
- **A4** — `contracts.md:93,130` `Answer.canonical` is typed `CanonicalCode`, which includes `PROVIDER_UNAVAILABLE`, but Q-fail states that on provider failure no `Answer` is created. A value that can only occur when no answer exists is allowed in the answer schema.
- **A5** — `contracts.md:93,626-627` `INTENT_NOT_SUPPORTED` is specified as an HTTP-200 canonical response ("Clarification required: intent not supported.") but is absent from the `CanonicalCode` enum, so it cannot be carried in `Answer.canonical`. `VALIDATION_ERROR` is in the enum but no error code maps to it.
- **A6** — `contracts.md:549-551` OP-5 `jobs_port.select` returns "every record matching selector with **no cap**", directly contradicting §5 I22 ("browse is capped/paginated… unbounded lists are impossible", D46). The dry-run enumeration is the one place the cap is dropped.
- **A7** — `contracts.md:289-308,549` `propose_destructive_action` supports `cordon_node`/`drain_node`, but the only selector-bearing read is `jobs_port.select` (OP-5); `nodes_port` (OP-6) exposes only `get`/`browse`. The mechanism that produces `affected_items` for node actions is undefined, and the relationship between `target_refs` and `Selector.params` is never specified.
- **A8** — `contracts.md:137,607` LLM prose latency is given twice inconsistently: `answer_query` sub-budget says the single prose call p95 ≤ 1500 ms, while OP-14 says "p95 < 3 s for the single prose call".
- **A9** — `contracts.md:431-439` `get_runbook` (a pure registry lookup) carries a p95 ≤ 5000 ms budget labeled "runbook generation end-to-end", while `lookup_runbook` — the operation it delegates to — is budgeted p95 < 5 ms. A single GET cannot inherit an end-to-end generation budget three orders of magnitude larger than its own.
- **A10** — `contracts.md:30,434,643` Canonical literals and error templates disagree: `S_RBX` is `no runbook available for code X` (no period) but the §4 template is `no runbook available for code {code}.`; `S_ENF` is `Entity Not Found in State` but the `ENTITY_NOT_FOUND` template is `Entity Not Found in State: {ref_list}.`. The table asserts these literals are emitted verbatim.
- **A11** — `contracts.md:205-222` `diagnose_schedule_window` and `diagnose_retrospective` take `windows`/`events` arrays as direct arguments, while `diagnose_access_denial` I1 asserts "the returned `diagnosis_class` is a pure function of the `EvidenceSet`". The diagnosers do not share a consistent input contract.
- **A12** — `contracts.md:123,385` Session status enum includes `expired`, and P2 tests a 30-minute idle rule, but no operation ever writes `status = 'expired'` (SQL C2 only checks `status = 'active'`); an expired session is therefore reported as `active` by `get_session`.
- **A13** — `contracts.md:105,596-597` `ProposalState` includes `refused`, and `proposal_lifecycle` enumerates `refused`, but no operation transitions a proposal into `refused`; `propose_destructive_action` Q1 only ever produces `state == dry_run`. The state and its event are unreachable.
- **A14** — `contracts.md:365` §2 says canonical codes return "the literal string in the body", but `openapi.yaml` models the 200 canonical response as a structured `ErrorBody` object (`oneOf: AnswerEnvelope|ErrorBody`). A raw literal string does not validate against `ErrorBody`.
- **A15** — `contracts.md:326,465` `confirm_and_dispatch` Q4 and `post_confirm` Q4 require the caption `S_CAP` to be "emitted", but no field in `Proposal`, `Answer`, `ErrorBody`, or any DTO carries it. The required output has no representation.
- **A16** — `contracts.md:495,640-642` `executor_post_proposal` Q1 returns HTTP 200 with `status: partial`, while §4 defines `EXECUTOR_PARTIAL_APPLY` as HTTP 502; `openapi.yaml:326-331` maps the same condition to a 502, and the DTO `ExecutorPostProposalResponse` omits the `source` field that §0.5 and `ExecutorResultDTO` require.
- **A17** — `contracts.md:495` `executor_post_proposal` Q4 says the executor "sets the proposal `failed` (D33)", writing proposal state that §0.5/AD-13 declares Module-12-owned. The executor is described as mutating the copilot's proposal store.
- **A18** — `contracts.md:135` `answer_query` claims concurrent calls for distinct sessions "do not block", but the chosen store is SQLite with a single writer (WAL). Any two turns writing `sessions`/`answers`/`evidence` contend on that single writer, so the non-blocking claim is false.
- **A19** — `contracts.md:127` `answer_query` Q2 says `prior_intents` gains "exactly one appended entry per answer", but the SQL C2 example appends exactly one intent and one answer id per query — diverging for decomposed compound queries (`len(answers) >= 2`, D37).
- **A20** — `contracts.md:55-57`, `schemas/events.md:11` `IdKind`/`IdString` cover `session|answer|evidence|claim|tool_call|audit|proposal|gate_token` only, but `events.md` defines `eventId` as a `{type}#{id}` or `evt-` ULID. Event ids cannot therefore originate from `idgen_port`, violating R2's "every generated id crosses this port".
- **A21** — `contracts.md:655-676` The §5 binding table numbers invariants I1–I22, but §1 operations reuse I1/I2/I3 for entirely different local invariants (`answer_query` I1 "every claim cited" vs §5 I1 "zero operational-state writes"). References like "I1" are ambiguous without a scope qualifier.
- **A22** — `contracts.md:39-57` §0.1's vocabulary does not define several types the contracts reference by name: `ResolvedEntity`, `ResolvedEntitySet`, `Diagnosis`, `IntentCode`, `EventQuery`, `Session`, `ToolCall`, `Intent`. A contract that names undefined types is not a closed vocabulary.
- **A23** — `ports-and-adapters.md:61-65` R1 is titled "`domain/` imports no…" but the rule and enforcement point are scoped to `service/core/`. The heading names a directory that does not exist in the component table.
- **A24** — `ports-and-adapters.md:46,144` The outbound-port table lists `executor_port` alongside OP-13/OP-14 but assigns it no OP number and no interface signature; §4 says "its wire form is §2 `executor_post_proposal`". The numbering scheme is incomplete and the port's contract lives in the driving-adapter section.
- **A25** — `ports-and-adapters.md:98-127` In the diagram, `PORTSOUT --> ADB/ASIM/ALLM` asserts the outbound path depends on the driven adapters, inverting the dependency-inversion rule that adapters depend on the port. As drawn, "depends on" contradicts hex architecture and the document's own R3.
- **A26** — `schemas/dto.py:425-428,468-473` `SubmitQueryRequest` includes `session_id` in the DTO while `openapi.yaml:695-699` defines the request body as `{query_text}` only (sid is a path param); symmetrically, `GetStateRecordRequest`/`BrowseStateRequest` embed path parameters as body fields. The DTO and the wire contract disagree.
- **A27** — `schemas/openapi.yaml:598-604` `SessionWithTurns` composes `Session` (which sets `additionalProperties: false`) via `allOf` and then adds `turns`. Under JSON Schema 2020-12 the base schema rejects the extra `turns` property, making `SessionWithTurns` unsatisfiable.
- **A28** — `schemas/001_module12_copilot_schema.sql:207-221` `audit_events.session_id` is nullable and unconstrained, so the schema cannot enforce the schema-level `required: [sessionId]` for `tool_call`/`answer_produced` event types.
- **A29** — `schemas/001_module12_copilot_schema.sql:176-193` `audit_records.tool_call_id` references `tool_calls` with `ON DELETE RESTRICT` while `tool_calls.session_id` cascades from `sessions`; deleting a session would attempt a cascade that the RESTRICT FK blocks. The referential paths are mutually inconsistent (unexercised only because no delete route exists).
- **A30** — `schemas/phase-2.3-cross-check.md:17,31` The cross-check leaves hard decisions open (X-02: "Decide whether `evidence` `IdKind`… should map to `citation_id` or be dropped"; X-16: "Decide the surfacing route"), yet `ports-and-adapters.md` is marked `status: final` and the schemas are presented as a frozen contract. Unresolved decisions contradict the "zero elastic language / finalized" posture.

---

## Lens 2 — Edge-case hunter (raw findings)

Only unhandled paths and boundaries; handled cases discarded silently.

```json
[
  {
    "location": "contracts.md:43,122",
    "trigger_condition": "query raw length > 1000 but trimmed length <= 1000",
    "guard_snippet": "Normalize once: let q = query_text.strip(); test len(q)==0 and len(q)>1000 on the same value.",
    "potential_consequence": "Whitespace-padded valid query rejected or empty query accepted."
  },
  {
    "location": "contracts.md:211",
    "trigger_condition": "job.scheduling_constraint set but windows_port.list() returns zero windows",
    "guard_snippet": "If windows is empty, return schedule_no_constraint or a typed no-window canonical; never compute next_open_window.",
    "potential_consequence": "Restricted diagnosis with an undefined next_open_window."
  },
  {
    "location": "contracts.md:213",
    "trigger_condition": "all windows for the constraint are in the past",
    "guard_snippet": "When no window satisfies start > now, set next_open_window = null and render an explicit no-future-window state.",
    "potential_consequence": "next_open_window computed from an empty future set is undefined."
  },
  {
    "location": "contracts.md:302",
    "trigger_condition": "re-dispatch requested for a parent whose dry_run had an empty affected set",
    "guard_snippet": "Define behavior when parent.state==dry_run and affected_items==[]; either forbid re-dispatch or require a fresh non-empty dry-run.",
    "potential_consequence": "Undefined proposal created or silent empty dispatch path."
  },
  {
    "location": "contracts.md:324,495",
    "trigger_condition": "executor returns applied_count greater than len(affected_items)",
    "guard_snippet": "Reject applied_count > len(affected_items) as executor failure; treat as EXECUTOR_PARTIAL_APPLY/failed.",
    "potential_consequence": "Larger-than-scope mutation accepted as success."
  },
  {
    "location": "contracts.md:321",
    "trigger_condition": "executor responds after the 5 s timeout, after copilot marked failed",
    "guard_snippet": "On late response, record executor result without changing failed, or reject via ux_audit_executor_apply idempotency key.",
    "potential_consequence": "Copilot reports failed while the estate was mutated; double apply on re-dispatch."
  },
  {
    "location": "contracts.md:123",
    "trigger_condition": "session created but never had a turn (last_turn_at is NULL)",
    "guard_snippet": "Define idle age for last_turn_at IS NULL (use created_at) in the P2 predicate.",
    "potential_consequence": "Age comparison against NULL undefined; fresh session rejected or accepted arbitrarily."
  },
  {
    "location": "contracts.md:123",
    "trigger_condition": "query submitted to a session with status=reset",
    "guard_snippet": "Map reset to a specific typed response (SESSION_NOT_FOUND vs SESSION_EXPIRED) and document it.",
    "potential_consequence": "Reset session returns an ambiguous 404/410 contract."
  },
  {
    "location": "contracts.md:234",
    "trigger_condition": "window contains events of more than one type for the same entity",
    "guard_snippet": "Define diagnosis_class precedence when event_denied/event_cancelled/event_cordoned co-occur.",
    "potential_consequence": "Non-deterministic diagnosis_class for a mixed event window."
  },
  {
    "location": "contracts.md:192",
    "trigger_condition": "user matches both a not-in-allowlist clause and a quota clause",
    "guard_snippet": "Define clause precedence for diagnosis_class selection when multiple reason_class clauses match.",
    "potential_consequence": "Ambiguous denial reason rendered as if unique."
  },
  {
    "location": "contracts.md:295",
    "trigger_condition": "target_refs resolve to an entity whose type is incompatible with the action verb",
    "guard_snippet": "Validate (action, resolved entity type) compatibility before dry-run; reject with VALIDATION_BAD_ACTION.",
    "potential_consequence": "delete_jobs applied to a node reference; arbitrary selector built."
  },
  {
    "location": "contracts.md:295",
    "trigger_condition": "target_refs resolve but the record is already in a terminal status",
    "guard_snippet": "Define actionable=false handling and whether a zero-actionable dry-run is still emitted.",
    "potential_consequence": "Dry-run proposes actions on records that cannot change."
  },
  {
    "location": "contracts.md:405",
    "trigger_condition": "requested page lies beyond total, or page*page_size overflows",
    "guard_snippet": "Define out-of-range page behavior (empty items + total) and an upper bound on page.",
    "potential_consequence": "Off-by-one pagination or unbounded OFFSET computation."
  },
  {
    "location": "contracts.md:445",
    "trigger_condition": "requested audit page lies beyond the 10,000-row retention cap",
    "guard_snippet": "Clamp page depth to the retention cap and return an empty page with the retained-total.",
    "potential_consequence": "Operator paginates into evicted rows or an unhandled empty shape."
  },
  {
    "location": "contracts.md:394",
    "trigger_condition": "path id does not match the {type}#{id} EntityKey shape",
    "guard_snippet": "Validate the id against the EntityKey format before lookup; return VALIDATION_MALFORMED_BODY.",
    "potential_consequence": "Malformed id falls through to an unspecified 404/500."
  },
  {
    "location": "contracts.md:108,494",
    "trigger_condition": "ExecutorRequest.dry_run_ref.proposal_id differs from proposal_id",
    "guard_snippet": "Require dry_run_ref.proposal_id == proposal_id in the frozen schema or reject as VALIDATION_MALFORMED_BODY.",
    "potential_consequence": "Executor applies a snapshot other than the named proposal."
  },
  {
    "location": "contracts.md:94",
    "trigger_condition": "a decomposed compound query produces a single Answer",
    "guard_snippet": "Enforce len(answers) >= 2 when the query is classified compound (D37), or record the compound flag.",
    "potential_consequence": "Compound intent silently collapses to one answer."
  },
  {
    "location": "dto.py:290",
    "trigger_condition": "answer_chain is non-contiguous, reordered, or skipped",
    "guard_snippet": "Validate the chain against the contiguous-prefix rule of [observation,evidence,diagnosis,recommendation,proposal,execution].",
    "potential_consequence": "An illegal chain passes DTO validation (finding X-04)."
  },
  {
    "location": "001_module12_copilot_schema.sql:32",
    "trigger_condition": "operator_role is exactly the prefix 'role-' with empty suffix",
    "guard_snippet": "Tighten the GLOB to require >= 1 suffix char within [a-z0-9_-]: 'role-[a-z0-9_-]*' plus length bounds.",
    "potential_consequence": "Empty-suffix role accepted by SQL but rejected by the DTO."
  },
  {
    "location": "001_module12_copilot_schema.sql:93",
    "trigger_condition": "a claim row has text = '' (empty string)",
    "guard_snippet": "Add CHECK (length(trim(text)) >= 1) to claims.text (or constrain claim text in the composer).",
    "potential_consequence": "Empty factual claim stored and rendered."
  },
  {
    "location": "001_module12_copilot_schema.sql:83",
    "trigger_condition": "evidence positions do not start at 0 or contain gaps",
    "guard_snippet": "Assert the 0..n-1 contiguous sequence in the composer; keep UNIQUE(answer_id,position) as a backstop (X-07).",
    "potential_consequence": "Rendered evidence order has gaps but no error."
  },
  {
    "location": "001_module12_copilot_schema.sql:146",
    "trigger_condition": "two proposals are issued the same gate_token",
    "guard_snippet": "Add UNIQUE(gate_token) or scope the token to the proposal row explicitly.",
    "potential_consequence": "One proposal's token confirms another."
  },
  {
    "location": "events.schema.json:176",
    "trigger_condition": "answer_produced carries answer_chain = []",
    "guard_snippet": "Add minItems: 1 to answer_chain items in the answerProduced payload schema.",
    "potential_consequence": "Answer emitted with no pipeline stages."
  },
  {
    "location": "events.schema.json:196",
    "trigger_condition": "claim_count >= 1 while evidence_count = 0",
    "guard_snippet": "Add a cross-field rule evidence_count >= 1 when claim_count >= 1 (or explain the zero-evidence answer).",
    "potential_consequence": "Uncited claims advertised on the event bus."
  },
  {
    "location": "contracts.md:404",
    "trigger_condition": "browse q matches an id only under a different case than stored",
    "guard_snippet": "Define whether q normalizes both sides under case-fold; state the stored-case rule.",
    "potential_consequence": "Exact-id browse misses a record that resolve_entities would find."
  },
  {
    "location": "001_module12_copilot_schema.sql:197-201",
    "trigger_condition": "rotation gate is read/flipped while another connection writes audit rows",
    "guard_snippet": "Hold the gate inside BEGIN IMMEDIATE and document that only one rotation writer may exist.",
    "potential_consequence": "Delete trigger bypassed or rotation blocked under concurrency."
  },
  {
    "location": "contracts.md:106",
    "trigger_condition": "executor_result is present while state is dry_run or confirmed",
    "guard_snippet": "State the cross-field rule at contract level: executor_result non-null only in executed/failed.",
    "potential_consequence": "Non-terminal proposal advertises an executor result."
  },
  {
    "location": "dto.py:282",
    "trigger_condition": "claim_citations reference a citation_id absent from the answer's evidence",
    "guard_snippet": "Validate claim citations against the stored EvidenceSet at composition or read time.",
    "potential_consequence": "Claim cites evidence the answer does not carry."
  },
  {
    "location": "openapi.yaml:392",
    "trigger_condition": "timestamp uses a non-3-digit fractional second (e.g. .5 or .123456)",
    "guard_snippet": "Confirm ms-or-none is intentional; if not, relax the pattern to (\\.\\d{1,6})?.",
    "potential_consequence": "Valid ISO-8601 instants rejected by the pattern."
  }
]
```

### Extended pass (`/bmad-review --lens edge-case-hunter`, E30–E50)

Second path-tracing pass over the same artifacts; only newly unhandled paths.

```json
[
  {
    "location": "contracts.md:145",
    "trigger_condition": "references array has no maximum element count",
    "guard_snippet": "Cap len(references) (e.g. <= 32) and reject excess with VALIDATION_MALFORMED_BODY.",
    "potential_consequence": "Unbounded resolution work per request; latency and DoS."
  },
  {
    "location": "contracts.md:49,145",
    "trigger_condition": "a RawRef contains '#' or already looks like {type}#{id}",
    "guard_snippet": "Define RawRef escaping so '#' in operator text is not read as a type separator.",
    "potential_consequence": "Reference mis-parsed into a bogus entity type/id."
  },
  {
    "location": "contracts.md:106,312-320",
    "trigger_condition": "a dry_run proposal is confirmed arbitrarily long after the snapshot",
    "guard_snippet": "Give gate_token a TTL or bind confirmation to snapshot freshness; expire stale tokens.",
    "potential_consequence": "Stale snapshot dispatched as if fresh."
  },
  {
    "location": "contracts.md:135,381-389",
    "trigger_condition": "reset_session runs while a submit_query for the same session is mid-pipeline",
    "guard_snippet": "Define ordering: reset wins or the turn aborts; reset must not leave a half-written context.",
    "potential_consequence": "Session context left inconsistent or an answer appends after reset."
  },
  {
    "location": "contracts.md:128,130",
    "trigger_condition": "a tool call and its audit row are written, then a later stage fails",
    "guard_snippet": "Define the transaction boundary: annotate or void the turn's tool calls on failure.",
    "potential_consequence": "Orphan tool-call audit rows for a turn that produced no Answer."
  },
  {
    "location": "contracts.md:494",
    "trigger_condition": "executor POST retried after a timeout on the same proposal_id",
    "guard_snippet": "Return the stored result for an identical retry instead of EXECUTOR_DUPLICATE_APPLY.",
    "potential_consequence": "A safe retry is rejected as a duplicate apply."
  },
  {
    "location": "openapi.yaml:755-762",
    "trigger_condition": "operator paginates the audit log and needs the last page",
    "guard_snippet": "Add a total (or has_more/next_page) field to GetAuditPageResponse.",
    "potential_consequence": "Client cannot determine when to stop paging."
  },
  {
    "location": "events.schema.json:152-153",
    "trigger_condition": "from_state/to_state encode an illegal transition (e.g. refused -> executed)",
    "guard_snippet": "Constrain from_state/to_state to the legal transition set, or validate in the emitter.",
    "potential_consequence": "Event log records impossible lifecycle jumps."
  },
  {
    "location": "001_module12_copilot_schema.sql:36-38",
    "trigger_condition": "context_* JSON array holds non-string or non-EntityKey elements",
    "guard_snippet": "Validate element types at write time (JSON1 json_type or app guard).",
    "potential_consequence": "Malformed context read back into resolve_entities."
  },
  {
    "location": "001_module12_copilot_schema.sql:143",
    "trigger_condition": "proposals.selector.method names a non-allowlisted provider method",
    "guard_snippet": "Allowlist selector.method to the vetted provider queries before persisting.",
    "potential_consequence": "Arbitrary provider query persisted and re-executed at confirm."
  },
  {
    "location": "001_module12_copilot_schema.sql:144",
    "trigger_condition": "affected_items is valid JSON but not an array of AffectedItem",
    "guard_snippet": "Enforce json_type = 'array' (and item shape) for affected_items.",
    "potential_consequence": "Dry-run enumeration read back in the wrong shape."
  },
  {
    "location": "contracts.md:78",
    "trigger_condition": "a ReservationRecord has end <= start",
    "guard_snippet": "Require start < end for reservations as a provider invariant.",
    "potential_consequence": "Empty/negative reservation window; boundary math undefined."
  },
  {
    "location": "contracts.md:79,205-223",
    "trigger_condition": "a PolicyWindow has end <= start",
    "guard_snippet": "Require start < end for policy windows before the calculator consumes them.",
    "potential_consequence": "Open-window calculation over an inverted interval."
  },
  {
    "location": "contracts.md:597",
    "trigger_condition": "seeded idgen restarts and reissues ids already persisted",
    "guard_snippet": "Persist the id counter or seed from the current max so restarts do not reuse ids.",
    "potential_consequence": "Primary-key collisions after a process restart."
  },
  {
    "location": "contracts.md:136,498",
    "trigger_condition": "executor result timestamp equals the turn's now rather than a fresh clock read",
    "guard_snippet": "Require the executor adapter to take its own clock read for the result timestamp.",
    "potential_consequence": "Ordering anomalies: applied appears before dispatched."
  },
  {
    "location": "contracts.md:73",
    "trigger_condition": "GroupRecord.members contains a non-user EntityKey",
    "guard_snippet": "Validate members are user EntityKeys at the provider boundary.",
    "potential_consequence": "Resolution walks a group member of the wrong type."
  },
  {
    "location": "contracts.md:253,278",
    "trigger_condition": "error_code carries markup/control chars into the canonical runbook string",
    "guard_snippet": "Restrict error_code to ^[A-Za-z0-9._-]{1,64}$ before interpolation.",
    "potential_consequence": "Unsafe text rendered as if it were canonical copy."
  },
  {
    "location": "001_module12_copilot_schema.sql:193",
    "trigger_condition": "two audit rows share the same timestamp",
    "guard_snippet": "Add audit_id as a deterministic secondary sort key in the chronology index/query.",
    "potential_consequence": "Non-deterministic page order across reads."
  },
  {
    "location": "dto.py:426,openapi.yaml:52",
    "trigger_condition": "path {sid} differs from the body session_id",
    "guard_snippet": "Reject a mismatch with VALIDATION_MALFORMED_BODY, or drop session_id from the body.",
    "potential_consequence": "Turn written to a session other than the addressed one."
  },
  {
    "location": "contracts.md:405",
    "trigger_condition": "browse total returns the full matched count beyond the cap",
    "guard_snippet": "Define total semantics under the cap (capped count vs true count).",
    "potential_consequence": "Unbounded count information disclosed."
  },
  {
    "location": "events.schema.json:176",
    "trigger_condition": "answer_chain is non-contiguous or reordered on the event",
    "guard_snippet": "Validate the contiguous-prefix order in the emitter; schema minItems alone is insufficient.",
    "potential_consequence": "Event log advertises an illegal chain."
  }
]
```

---

## Triage table

Legend — Triage: **A**ccept / **D**efer / **R**eject. Owner #: the decision, AD amendment, or Phase-2 artifact that owns the fix. "Corrected?" = ☑ when the change has landed in the artifact.

| ID | Lens | Finding (short) | Triage | Reason | Owner # | Target section(s) | Corrected? |
|---|---|---|---|---|---|---|---|
| A1 | adversarial | `diagnose_node_triage` P3 inverted | A | Logic bug; a present code must not be rejected | new D52 | `contracts.md` §1 `diagnose_node_triage` P3 (253-254) | ☑ |
| A2 | adversarial | P1/P5 idempotent-confirm unreachable | A | Ordering conflict; D47 intent not expressible | amend D47 / AD-3 | `contracts.md` §1 `confirm_and_dispatch` P1+P5 (312-320) | ☑ |
| A3 | adversarial | `answer_query` labeled Core Domain though I/O+LLM | A | Layer definition contradicts placement | new D53 | `contracts.md` §1 header (116-137) + §0.6 | ☑ |
| A4 | adversarial | `PROVIDER_UNAVAILABLE` in `CanonicalCode` yet no Answer on failure | A | Value reachable only when answer cannot exist | new D54 | `contracts.md` §0.4 `CanonicalCode` (93) + §1 Q-fail (130) | ☑ |
| A5 | adversarial | `INTENT_NOT_SUPPORTED` missing from `CanonicalCode`; `VALIDATION_ERROR` unused | A | 200 canonical code cannot be carried in Answer | new D54 | `contracts.md` §0.4 (93) + §4 (627) | ☑ |
| A6 | adversarial | OP-5 `select` uncapped vs I22 | A | Direct contradiction with D46/AD-13 | amend AD-13 / D46 | `contracts.md` §3 OP-5 (549-551) + §5 I22 (676) | ☑ |
| A7 | adversarial | node-action dry-run has no selector source | A | `cordon_node`/`drain_node` enumeration undefined | new D55 | `contracts.md` §3 OP-6 (553-556) + §1 `propose_destructive_action` (289-308) | ☑ |
| A8 | adversarial | LLM prose latency 1500 vs 3000 ms | A | Numeric contradiction | new D56 | `contracts.md` §1 (137) + §3.1 OP-14 (607) | ☑ |
| A9 | adversarial | `get_runbook` 5000 ms budget | A | Mismatched budget on a pure read | new D56 | `contracts.md` §2 `get_runbook` (431-439) | ☑ |
| A10 | adversarial | canonical literals vs §4 templates differ | A | Verbatim-emission guarantee broken | new D57 | `contracts.md` canonical-strings table (24-31) + §4 (624,643) | ☑ |
| A11 | adversarial | diagnosers take inconsistent inputs | A | Undermines "pure function of EvidenceSet" | amend AD-2 | `contracts.md` §1 `diagnose_*` (185-244) | ☑ |
| A12 | adversarial | `expired` status never written | A | Idle/expiry rule unpersisted | amend AD-10 / D51 | `contracts.md` §2 (123,371-379) + `001_module12_copilot_schema.sql` `sessions.status` | ☑ |
| A13 | adversarial | `ProposalState.refused` unreachable | D | Reserved state; no refusal row required in this scope | note only | `contracts.md` §0.5 (105) | ☐ |
| A14 | adversarial | 200 canonical "literal string" vs `ErrorBody` object | A | Wire shape undefined for canonical responses | new D58 | `contracts.md` §2 (365) + `openapi.yaml` 200 `oneOf` (submit_query, post_dry_run) | ☑ |
| A15 | adversarial | `S_CAP` caption has no carrier field | A | Required output not representable | amend AD-5 | `contracts.md` §2 `post_confirm` Q4 (465) + `dto.py` `ProposalDTO` (385-394) | ☑ |
| A16 | adversarial | executor partial 200 vs 502 + missing `source` | A | Conflicting status and DTO field set | amend AD-15 | `contracts.md` §2 (495) + §4 (641) + `dto.py` `ExecutorPostProposalResponse` (608-612) + `openapi.yaml` `ExecutorResult` (650-659) | ☑ |
| A17 | adversarial | executor writes proposal state (AD-13 breach) | A | Ownership boundary violated | amend AD-13 / D33 | `contracts.md` §2 `executor_post_proposal` Q4 (495) + §1 `confirm_and_dispatch` Q2 (324) | ☑ |
| A18 | adversarial | "distinct sessions do not block" false under SQLite single writer | A | Concurrency claim contradicts storage decision | amend AD-10 | `contracts.md` §1 concurrency (135) | ☑ |
| A19 | adversarial | `prior_intents` per-answer vs SQL one-per-query | A | Compound answers diverge from SQL C2 | amend AD-10 | `contracts.md` §1 Q2 (127) + `001_module12_copilot_schema.sql` C2 (290-298) | ☑ |
| A20 | adversarial | event ids cannot come from `idgen_port` | A | R2 id-monopoly violated | new D59 | `contracts.md` §0.1 `IdKind`/`IdString` (56-57) + `schemas/events.md` (11) | ☑ |
| A21 | adversarial | invariant numbering collision (local I1 vs §5 I1) | A | Ambiguous references | new D60 | `contracts.md` §1 per-op I-clauses + §5 table (655-676) | ☑ |
| A22 | adversarial | undefined referenced types | A | Vocabulary not closed | new D61 | `contracts.md` §0.1–§0.5 (39-108) | ☑ |
| A23 | adversarial | R1 heading says `domain/` | A | Names a non-existent component | new D62 | `ports-and-adapters.md` R1 (61-65) | ☑ |
| A24 | adversarial | `executor_port` has no OP number/signature | A | Numbering incomplete | new D63 | `ports-and-adapters.md` §1 (46) + §4 (144) | ☑ |
| A25 | adversarial | diagram arrows invert dependency | A | Contradicts R3 and hexagonal direction | new D62 | `ports-and-adapters.md` §3 (98-135) | ☑ |
| A26 | adversarial | DTO embeds path params as body fields | A | DTO vs OpenAPI divergence | new D64 | `dto.py` `SubmitQueryRequest`/`GetStateRecordRequest`/`BrowseStateRequest` (425-473) | ☑ |
| A27 | adversarial | `SessionWithTurns` `allOf` + `additionalProperties:false` unsatisfiable | A | `turns` rejected by base schema | new D65 | `openapi.yaml` (598-604) | ☑ |
| A28 | adversarial | `audit_events.session_id` not enforced | A | Envelope requirement unenforceable | new D66 | `001_module12_copilot_schema.sql` `audit_events` (207-221) | ☑ |
| A29 | adversarial | CASCADE vs RESTRICT FK path inconsistent | D | No delete route exercises it; prototype re-creates DB | note only | `001_module12_copilot_schema.sql` (176-193) | ☐ |
| A30 | adversarial | open X-02/X-16 vs "final" status | A | Unresolved decisions block 2.3 | new D67 | `schemas/phase-2.3-cross-check.md` X-02/X-16 (17,31) | ☑ |
| E1 | edge | trim-vs-raw length boundary | A | Empty/long check on different values | new D52 | `contracts.md` §0.1 `QueryText` (43) + §1 P1 (122) | ☑ |
| E2 | edge | empty windows list for a constraint | A | `next_open_window` undefined | new D55 | `contracts.md` §1 `diagnose_schedule_window` P3 (211) | ☑ |
| E3 | edge | no future window exists | A | `next_open_window` undefined | new D55 | `contracts.md` §1 `diagnose_schedule_window` Q1 (213) | ☑ |
| E4 | edge | re-dispatch of empty-set dry-run | A | Undefined lifecycle path | amend AD-3 | `contracts.md` §1 `propose` Q-fail (302) + §2 `post_re_dispatch` (481-489) | ☑ |
| E5 | edge | applied_count > snapshot length | A | Out-of-scope success | amend AD-15 | `contracts.md` §1 `confirm_and_dispatch` Q2 (324) + §2 executor Q4 (495) | ☑ |
| E6 | edge | late executor response after timeout | A | Failed-vs-applied race | amend AD-3 / D31 | `contracts.md` §1 `confirm_and_dispatch` P6 (321) | ☑ |
| E7 | edge | fresh session `last_turn_at` NULL | A | Age predicate over NULL | amend D51 | `contracts.md` §1 P2 (123) + `001_module12_copilot_schema.sql` `sessions` (31) | ☑ |
| E8 | edge | reset-session query 404 vs 410 | A | Ambiguous status mapping | amend D51 | `contracts.md` §1 P2 (123) + §2 `submit_query` (361-369) | ☑ |
| E9 | edge | multi event-type diagnosis precedence | A | Non-deterministic class | amend AD-2 | `contracts.md` §1 `diagnose_retrospective` Q1 (234) | ☑ |
| E10 | edge | multi policy-clause diagnosis precedence | A | Non-deterministic class | amend AD-2 | `contracts.md` §1 `diagnose_access_denial` Q1 (192) | ☑ |
| E11 | edge | action verb vs entity-type mismatch | A | Arbitrary selector | new D55 | `contracts.md` §1 `propose` P3 (295) | ☑ |
| E12 | edge | target refs already in terminal status | A | `actionable=false` handling undefined | new D55 | `contracts.md` §1 `propose` P3/Q1 (295-298) | ☑ |
| E13 | edge | page beyond total / overflow | A | Pagination boundary undefined | new D64 | `contracts.md` §2 `browse_state` (401-409) | ☑ |
| E14 | edge | audit page beyond 10k cap | A | Retention boundary undefined | new D66 | `contracts.md` §2 `get_audit_page` (441-449) | ☑ |
| E15 | edge | malformed id on `get_state_record` | A | Only bad entity_type handled | new D52 | `contracts.md` §2 `get_state_record` P1 (394) | ☑ |
| E16 | edge | `dry_run_ref.proposal_id` mismatch | A | Wrong snapshot could apply | amend AD-15 | `contracts.md` §0.5 `ExecutorRequest` (108) + §2 executor P1 (494) | ☑ |
| E17 | edge | compound query yields single Answer | A | D37 not enforced | new D54 | `contracts.md` §0.4 `AnswerEnvelope` (94) + `dto.py` `AnswerEnvelopeDTO` (300-301) | ☑ |
| E18 | edge | `answer_chain` contiguity unenforced | A | X-04; chain rule not validated | new D60 | `dto.py` `AnswerDTO.answer_chain` (290) | ☑ |
| E19 | edge | `operator_role` GLOB allows empty suffix | A | SQL weaker than DTO | new D66 | `001_module12_copilot_schema.sql` `sessions.operator_role` (32) | ☑ |
| E20 | edge | empty `claims.text` allowed | A | Empty factual claim | new D66 | `001_module12_copilot_schema.sql` `claims.text` (93) + `contracts.md` §0.4 `Claim` (89) | ☑ |
| E21 | edge | evidence position gaps / start != 0 | A | X-07; ordering unasserted | new D66 | `001_module12_copilot_schema.sql` `evidence` (83) + `dto.py` `EvidenceDTO` (265) | ☑ |
| E22 | edge | duplicate `gate_token` unconstrained | A | Token could confirm wrong proposal | new D66 | `001_module12_copilot_schema.sql` `proposals.gate_token` (146) | ☑ |
| E23 | edge | empty `answer_chain` on event | A | Stage-free answer emitted | new D59 | `events.schema.json` `answerProduced` (176-179) | ☑ |
| E24 | edge | `claim_count>=1` with `evidence_count=0` | A | Uncited claims on bus | new D59 | `events.schema.json` `answerProduced` (196-197) | ☑ |
| E25 | edge | browse case-fold vs stored case | A | Inconsistent exact-id semantics | amend AD-7 | `contracts.md` §2 `browse_state` (404) + §3 OP-5 | ☑ |
| E26 | edge | rotation-gate concurrency race | A | Delete trigger bypassable | new D66 | `001_module12_copilot_schema.sql` `audit_rotation_gate` (197-201) | ☑ |
| E27 | edge | `executor_result` on non-terminal state | D | SQL all-or-nothing CHECK already covers the shape | note only | `contracts.md` §0.5 `Proposal` (106) | ☐ |
| E28 | edge | claim citations absent from evidence | D | Covered by `tests/citation_coverage` runtime | note only | `dto.py` `ClaimDTO` (279-282) | ☐ |
| E29 | edge | non-3-digit fractional seconds rejected | R | Contract `Instant` pattern intentionally requires ms-or-none | — | `dto.py`/`openapi.yaml` `Instant` (84,392) | ☐ |
| E30 | edge | `resolve_entities` reference count unbounded | A | Unbounded work per request | new D68 | `contracts.md` §1 `resolve_entities` P1 (145) | ☑ |
| E31 | edge | RawRef `#` collides with EntityKey syntax | A | Parsing ambiguity | new D61 | `contracts.md` §0.1 `RawRef` (49) | ☑ |
| E32 | edge | `gate_token` has no expiry/TTL | A | Stale snapshot confirmable | amend AD-3 / D47 | `contracts.md` §1 `confirm_and_dispatch` P2 (316) + §0.5 `gate_token` (106) | ☑ |
| E33 | edge | reset vs in-flight query race | A | Context could be half-written | amend AD-10 | `contracts.md` §1 concurrency (135) + §2 `reset_session` Q2 (385) | ☑ |
| E34 | edge | tool calls written then answer fails | A | Orphan audit rows | amend AD-10 | `contracts.md` §1 Q3 (128) + Q-fail (130) | ☑ |
| E35 | edge | executor retry after timeout rejected as duplicate | A | Safe retry mis-handled | amend AD-15 | `contracts.md` §2 executor P3 (494) | ☑ |
| E36 | edge | audit page response has no `total` | A | Client cannot stop paging | new D58 | `openapi.yaml` `GetAuditPageResponse` (755-762) + `dto.py` (518-521) | ☑ |
| E37 | edge | `proposal_lifecycle` transition legality unguarded | A | Impossible transitions loggable | new D59 | `events.schema.json` `proposalLifecycle` (152-153) | ☑ |
| E38 | edge | `context_*` element types unvalidated | A | Malformed context read back | new D66 | `001_module12_copilot_schema.sql` `sessions.context_*` (36-38) | ☑ |
| E39 | edge | `selector.method` not allowlisted | A | Arbitrary provider query persisted | new D55 | `001_module12_copilot_schema.sql` `proposals.selector` (143) + §3 OP-5 | ☑ |
| E40 | edge | `affected_items` JSON shape unenforced | A | Wrong shape read back | new D66 | `001_module12_copilot_schema.sql` `proposals.affected_items` (144) | ☑ |
| E41 | edge | reservation `end <= start` unguarded | A | Inverted interval | new D66 | `contracts.md` §0.3 `ReservationRecord` (78) | ☑ |
| E42 | edge | policy window `end <= start` unguarded | A | Inverted interval in calculator | new D66 | `contracts.md` §0.3 `PolicyWindow` (79) | ☑ |
| E43 | edge | idgen sequence reused after restart | A | PK collisions | new D59 | `contracts.md` §3.1 OP-13 Q2 (597) | ☑ |
| E44 | edge | executor timestamp reused from turn `now` | A | Ordering anomalies | amend AD-15 | `contracts.md` §1 Time (136) + §2 executor (498) | ☑ |
| E45 | edge | group members may be non-user keys | A | Wrong-type resolution | new D61 | `contracts.md` §3 OP-4 (545-546) | ☑ |
| E46 | edge | `error_code` interpolated unsanitized | A | Unsafe canonical copy | amend AD-11 | `contracts.md` §1 `diagnose_node_triage` (253) + `lookup_runbook` Q4 (278) | ☑ |
| E47 | edge | audit chronology tie ordering undefined | A | Non-deterministic page order | new D66 | `001_module12_copilot_schema.sql` `ix_audit_session_ts` (193) + §2 `get_audit_page` | ☑ |
| E48 | edge | path sid vs body session_id mismatch | A | Turn written to wrong session | new D64 | `dto.py` `SubmitQueryRequest` (426) + `openapi.yaml` (52,57) | ☑ |
| E49 | edge | `browse total` leaks uncapped count | D | Count semantics cosmetic; cap already bounds items | note only | `contracts.md` §2 `browse_state` (405) | ☐ |
| E50 | edge | event `answer_chain` order unguarded | A | Illegal chain logged | new D60 | `events.schema.json` `answerProduced` (176) | ☑ |

---

## Accepted — exact sections to touch

Grouped by artifact. Each line is a required edit for an Accepted finding.

### `planning/detailed-design/contracts.md`

- §0.1 `QueryText` (43): run the empty/length test on the same trimmed value. **E1**
- §0.1 `IdKind`/`IdString` (56-57): add an `event` kind (or a documented non-`idgen` event-id rule). **A20**
- §0.1–§0.5 (39-108): define `ResolvedEntity`, `ResolvedEntitySet`, `Diagnosis`, `IntentCode`, `EventQuery`, `Session`, `ToolCall`, `Intent`. **A22**
- §0.4 `CanonicalCode` (93): reconcile with §4 (`INTENT_NOT_SUPPORTED` in/out, `PROVIDER_UNAVAILABLE`, unused `VALIDATION_ERROR`). **A4, A5**
- §0.4 `AnswerEnvelope` (94): enforce `len>=2` for decomposed compound (D37). **E17**
- §0.4 `Claim` (89): non-empty claim text. **E20**
- §0.5 `ExecutorRequest` (108): require `dry_run_ref.proposal_id == proposal_id`. **E16**
- §0.5 `Proposal` (106): cross-field rule for `executor_result` (note). **E27**
- §1 header (116-137): layer of `answer_query` consistent with §0.6. **A3**
- §1 P1 (122) / Q2 (127) / Q-fail (130) / concurrency (135): trim boundary, per-answer context append, canonical/answer conflict, single-writer wording. **E1, A19, A4, A18**
- §1 `diagnose_access_denial` (185-203), `diagnose_schedule_window` (205-223), `diagnose_retrospective` (227-244): unified inputs + clause/type precedence + empty/no-future windows. **A11, E2, E3, E9, E10**
- §1 `diagnose_node_triage` P3 (248-254): correct the inversion. **A1**
- §1 `propose_destructive_action` (289-308): node-action selector source, verb/entity-type compatibility, terminal-status handling, empty-set re-dispatch. **A7, E4, E11, E12**
- §1 `confirm_and_dispatch` (312-334): P1/P5 idempotency ordering, `applied_count > len` guard, late-executor result. **A2, E5, E6**
- §1 latency (137) and §3.1 OP-14 (607): one LLM prose budget. **A8**
- §1 per-op I-clauses + §5 table (655-676): scope invariant IDs. **A21**
- Canonical-strings table (24-31) + §4 (624,643): literal/template agreement. **A10**
- §2 shared preamble (340-349) + `submit_query` (361-369): canonical response wire shape + reset/expiry mapping. **A14, E8**
- §2 `get_state_record` P1 (394): id-shape guard. **E15**
- §2 `get_runbook` (431-439): latency budget. **A9**
- §2 `get_audit_page` (441-449): out-of-cap page behavior. **E14**
- §2 `browse_state` (401-409): page bound/overflow. **E13**
- §2 `browse_state` (404) + §3 OP-5: case-fold rule. **E25**
- §2 `post_confirm` (461-469): `S_CAP` carrier. **A15**
- §2 `executor_post_proposal` (491-499): partial status code, `source` field, no proposal-state write. **A16, A17**
- §3 OP-5 (549-551) + §5 I22 (676): cap/justify the uncapped `select`. **A6**
- §3 OP-6 (553-556): node selector for cordon/drain. **A7**
- §0.1 `RawRef` (49): escape `#` so it is not read as a type separator. **E31**
- §0.3 `ReservationRecord` (78) and `PolicyWindow` (79): require `start < end`. **E41, E42**
- §0.3 `GroupRecord`/§3 OP-4 (545-546): validate `members` are `user` keys. **E45**
- §1 `resolve_entities` P1 (145): cap `len(references)`. **E30**
- §1 `confirm_and_dispatch` P2 (316) + §0.5 `gate_token` (106): token TTL/freshness. **E32**
- §1 Q3/Q-fail (128,130): transaction boundary for tool-call audit rows. **E34**
- §1 Time (136) + §2 executor (498): executor takes its own clock read. **E44**
- §1 `diagnose_node_triage` (253) + `lookup_runbook` Q4 (278): sanitize `error_code`. **E46**
- §2 `reset_session` Q2 (385) + §1 concurrency (135): reset vs in-flight ordering. **E33**
- §2 `browse_state` (405): define `total` semantics under the cap (note). **E49**
- §3.1 OP-13 Q2 (597): persistent/seeded id sequence across restarts. **E43**

### `planning/detailed-design/ports-and-adapters.md`

- R1 (61-65): rename heading `domain/` → `service/core/`. **A23**
- §1 component table (46) + §4 (144): give `executor_port` an OP number/signature or move its contract out of §2. **A24**
- §3 diagram (98-135): reverse adapter arrows to point at the port. **A25**

### `planning/detailed-design/schemas/dto.py`

- `SubmitQueryRequest`/`GetStateRecordRequest`/`BrowseStateRequest` (425-473): separate path params from body fields. **A26**
- `AnswerDTO.answer_chain` (290): validate contiguous-prefix chain. **E18**
- `AnswerEnvelopeDTO` (300-301): compound min-items / compound flag. **E17**
- `ProposalDTO` (385-394): add caption/`S_CAP` carrier. **A15**
- `ExecutorPostProposalResponse` (608-612): add `source`; align with `ExecutorResultDTO`. **A16**
- `EvidenceDTO` (265): position start/contiguity support. **E21**
- `SubmitQueryRequest` (426): reject path-sid/body-`session_id` mismatch. **E48**
- `GetAuditPageResponse` (518-521): add `total`/`has_more`. **E36**

### `planning/detailed-design/schemas/001_module12_copilot_schema.sql`

- `sessions` (26-39): tighter `operator_role` GLOB; expiry persistence; `last_turn_at` NULL handling. **E19, A12, E7**
- `answers` (44-64) + C2 (290-298): compound context append. **A19**
- `claims` (89-96): non-empty `text` CHECK. **E20**
- `evidence` (71-84): position start/contiguity guard. **E21**
- `proposals` (133-167): `UNIQUE(gate_token)`. **E22**
- `audit_records` (173-193): reconcile CASCADE/RESTRICT (note). **A29**
- `audit_events` (207-221): `session_id` requirement for session-scoped event types. **A28**
- `audit_rotation_gate` (197-201): document/guard single rotation writer. **E26**
- `sessions.context_*` (36-38): validate element types. **E38**
- `proposals.selector` (143): allowlist `method`. **E39**
- `proposals.affected_items` (144): enforce array/item shape. **E40**
- `ix_audit_session_ts` (193): add `audit_id` tiebreak for chronology. **E47**

### `planning/detailed-design/schemas/events.schema.json` / `events.md`

- `answerProduced` (176-179): `answer_chain` `minItems: 1`. **E23**
- `answerProduced` (196-197): counts cross-field rule. **E24**
- `events.md` (11): event-id kind/origin aligned with `IdKind`. **A20**
- `proposalLifecycle` (152-153): constrain `from_state`/`to_state` to legal transitions. **E37**
- `answerProduced` (176): validate contiguous-prefix chain order. **E50**

### `planning/detailed-design/schemas/openapi.yaml`

- `SessionWithTurns` (598-604): fix `allOf` composition. **A27**
- `submit_query` / `post_dry_run` 200 (59-68, 230-240): canonical response shape. **A14**
- `ExecutorResult` (650-659): `source` requirement. **A16**
- `Instant` (392): confirm the ms-or-none pattern is intentional (Reject note). **E29**
- `GetAuditPageResponse` (755-762): add `total`/`has_more`. **E36**

### `planning/detailed-design/schemas/phase-2.3-cross-check.md`

- X-02 and X-16 (17,31): resolve the open decisions before Phase 2.3. **A30**

---

## Triage summary

- **Accept:** 74
- **Defer:** 5 (A13 `refused` reserved; A29 FK path unexercised; E27 `executor_result` shape already covered by SQL; E28 claim-citation existence covered by runtime tests; E49 `browse` `total` semantics cosmetic)
- **Reject:** 1 (E29 — the contract `Instant` pattern intentionally requires milliseconds-or-none)

All 74 Accepted rows have landed in `contracts.md`, `ports-and-adapters.md`, and the `schemas/*`
artifacts via new decisions D52–D68 (recorded in `ai-log/decision-log-solu2.md`) and amendments to
AD-2/3/5/7/10/11/13/15 and D31/D33/D46/D47/D51; their "Corrected?" cells are ☑. The 5 Deferred rows
(A13 `refused` reserved, A29 FK path unexercised, E27 `executor_result` shape covered by the SQL
CHECK, E28 claim-citation existence covered by runtime tests, E49 `browse` `total` semantics
cosmetic) and the 1 Rejected row (E29 — the `Instant` ms-or-none pattern is intentional) remain ☐ by
design and are carried as runtime-test obligations or explicit non-changes.

**Gate status: Phase 1–2 CLEARED (2026-10-16).** No unresolved decisions remain in the frozen
detailed-design contract.

---

*Companion to `planning/detailed-design/contracts.md`. Dual-lens review and triage performed 2026-10-16.*
