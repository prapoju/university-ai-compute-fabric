---
type: review
reviewer: adversarial-general (cynical), implementability-limited
target: planning/ARCHITECTURE.md (Module 12 — AI Operations Copilot, feature altitude, final)
focus: implementability gaps only — every finding is a detail that does not exist and that a developer would have to invent
scope: core operations OP-A answerQuery, OP-B confirmAndDispatchProposal, OP-C resolveEntities, plus shared persistence/contract gaps
sources-read:
  - ARCHITECTURE.md (final, full)
date: 2026-10-16
verdict: disciplined spine, but many undecided details a builder must invent, concentrated in the three core operations
---

# Adversarial Review (Implementability-Limited) — Module 12 Architecture

Descriptions only, no severity, priority, or ranking. Every item is a detail that does not exist and that a developer would have to invent.

## OP-A — `answerQuery`

- No request or response schema for `POST /sessions/{sid}/queries` or the `Answer` resource: field names, nullability, and the "error/answer envelope" (`ARCHITECTURE.md:602`) are asserted but never defined.
- No HTTP status codes for any §3 route: clarification, `Entity Not Found`, `Cannot confirm (insufficient evidence)`, `Provider unavailable`, empty-set refusal, and stale-snapshot delta have no status binding, so the client cannot branch on a contract.
- No idempotency key or turn id on the query POST; a double-submit yields duplicate Answers, audit rows, and LLM calls.
- Clock/time source unbound: no `read_id` format for `clock#<read_id>` (`:222`, `:581`), no rule for how many clock reads per answer, no granularity, no freeze hook for the FR-14 test, no P9 interface.
- LLM call parameters unbound: no timeout value, retry count, or behavior when a retry contradicts "invoked exactly once" (`:437`); AD-2 ("not on the critical path", `:170`) and AD-12 (abort on LLM timeout, `:557`) tell the dev to build two different failure behaviors.
- Prose token-scan (`:509`) gives no tokenization rule and no decision between "strips" and "rejects" — behavior and failure mode are the dev's to invent.
- `answer_chain` construction unbound: no rule for which of the six enum stages are present, no stage→node mapping.
- Evidence `position` (`:137`, `:581`) has no start value, type, or uniqueness constraint.
- Intent classifier internals unbound: ambiguity threshold for the LLM-assist, destructive-verb list, decomposition algorithm, and the decomposed-answer output shape (one Answer vs N).
- Server-side request validation (char cap, UTF-8, non-empty, malformed input, FR-01/NFR-7) is allocated to no component or middleware.

## OP-B — `confirmAndDispatchProposal`

- Dry-run → proposal lifecycle undefined: whether `POST /destructive/dry-runs` creates a `Proposal` row, what id it returns, and whether the gate token is issued there or at confirm (`:270`, `:593`) are all unstated.
- Whether confirm and dispatch are one request or two is unresolved (`:270` vs AD-4's "no single-request confirm and execute", `:463`); the dev must pick, and the choice changes the materialized states.
- Confirm idempotency and gate-token single-use undefined: a retried confirm either re-confirms, re-dispatches, or errors — no rule.
- Second-dispatch rejection has no error code, status, or recorded transition; "audit writer rejects … surfacing as executor failure" (`:593`) leaves the check's owner and result shape to the dev.
- `gate_token` is a placeholder: no generation, entropy, TTL/expiry, single-use rule, re-render rotation, or storage nullability; executor validation has no shared secret or read handle to implement against.
- The "actionable field" per entity type for snapshot comparison (`:485`) is unnamed, and the selector predicate's persisted serialization is unspecified.
- Safe-failure text for re-validation (`:485`) is not in `canonical_strings` (`:602`); empty-set and scope-delta are UI states with no payload flag or status to carry them.
- Executor timeout, partial application, retry, and the `failed` transition are unbound; `GET /executor/v1/proposals/{pid}` has no caller.
- The "closed-verb action" (`:593`) has no enumerated verb set or proposal→executor verb mapping.
- `superseded` transition rules (which states may supersede) are unbound.

## OP-C — `resolveEntities`

- The case-fold rule is undefined (Python `str.casefold()` vs ASCII lower vs NFKC); whitespace, `#` escaping, punctuation, and leading-zero handling are unstated.
- The citation-type ↔ entity-type mapping is missing: singular citation prefixes (`user#`, `job#`, `policy#catalog.4.2`, `:175`) vs the plural `{entity_type}` enum (`users, catalog, windows …`, `:228`) have no defined mapping.
- "Type-scoped by intent requirements" (`:497`) names no source for the admissible type set, and gives no rule for a bare name matching multiple types or an id containing `#`.
- Whether a context-first hit must be re-validated against the provider index is unstated, so the dev chooses whether a stale reference can resolve.
- No canonical response exists for a reference matching multiple records (ambiguity falls between the two defined strings).
- Nested `OperationalEvent.entity_ref` resolution and malformed-reference handling have no defined behavior.
- Unresolved-reference reporting ("naming each unresolved reference", `:497`) has no format, order, or dedup rule.
- Browse `?q=` no-match behavior, matched fields, and pagination are unspecified.

## Shared persistence / contract gaps

- The data model (`:214`–`:224`) specifies no `NOT NULL`/`CHECK`/enum constraints for state, actor, status, nullability of optional FKs, `Evidence.position`, or the stage-gated Proposal columns — the dev invents every constraint.
- AD-10 declares the Audit Writer the "single writer for all Module-12 persistence" (`:533`) but no component is granted the write path for `Proposal.state` or session context.
- AD-14's `clock` citation has no enum entry or `/state/clock/{id}` route to make it resolvable.
- AD-5's confirmation caption (`:473`) has no owner in `canonical_strings` (`:603`).
- `operator_role` has no id format or assignment source.
- No SQLite schema-versioning/migration mechanism is defined.
- UX-26's "confirm disabled while re-validation pending" (`:461`) has no async or polling contract.

---

## Gap Table

One row per gap; each is a detail decided by "nothing" that a developer would have to invent. Owner A = Architect-lead, B = Test-lead.

| # | Gap in ARCHITECTURE.md (decided by "nothing") | How an AI/dev agent would invent a decision | Resolved in Phase | Owner (A/B) |
|---|---|---|---|---|
| 1 | No request/response schema for `POST /sessions/{sid}/queries` or the `Answer` resource (`:602`) | Invents field names, nullability, and envelope shape | 2 | A |
| 2 | No HTTP status codes bound to any §3 route | Invents statuses; client cannot branch on a contract | 1 | A |
| 3 | No idempotency key or turn id on the query POST | Double-submit yields duplicate Answers, audit rows, LLM calls | 1 | A |
| 4 | Clock source unbound: no `read_id` format, granularity, freeze hook, or P9 interface | Invents a time source; FR-14 becomes unverifiable | 1 | B |
| 5 | AD-2 "not on the critical path" (`:170`) contradicts AD-12 "abort on LLM timeout" (`:557`) | Builds two contradictory LLM failure behaviors | 1 | B |
| 6 | Prose token-scan gives no tokenization rule and no strip-vs-reject decision (`:509`) | Invents the guard behavior and its failure mode | 1 | B |
| 7 | `answer_chain` stage-presence rule and stage→node mapping unbound (`:602`) | Invents the chain spine | 2 | A |
| 8 | `Evidence.position` start value, type, and uniqueness unbound (`:137`, `:581`) | Invents ordering semantics | 2 | A |
| 9 | Intent classifier internals and decomposed-answer shape (one Answer vs N) unbound (`:128`) | Invents threshold, verb list, output shape | 1 | A |
| 10 | No component owns server-side request validation (char cap, UTF-8, non-empty) | Trusts the client; NFR-7 crash on malformed input | 2 | B |
| 11 | Dry-run→proposal lifecycle and confirm/dispatch split unresolved (`:270` vs AD-4 `:463`) | Invents whether `confirmed` is materialized | 1 | A |
| 12 | `gate_token` has no generation, entropy, TTL, single-use, rotation, or executor shared secret (`:593`) | Invents token semantics; gate proof is untestable | 1 | A |
| 13 | Second-dispatch rejection and `superseded` transition rules have no code/status/transition table | Invents the error code and transition rules | 1 | A |
| 14 | Snapshot "actionable field" per entity and selector serialization unnamed (`:485`) | Invents the comparison key and predicate format | 1 | A |
| 15 | Executor timeout, partial application, retry, `failed` transition unbound; `GET /executor/v1/proposals/{pid}` has no caller | Invents failure handling; leaves a dead route | 1 | B |
| 16 | Empty-set / scope-delta / re-validation safe-failure are UI states with no payload flag or status (`:485`) | Invents the response envelope | 2 | B |
| 17 | Case-fold rule undefined; citation-type ↔ entity-type mapping missing (`:497`, `:175` vs `:228`) | Invents normalization and prefix mapping | 1 | B |
| 18 | Type-scoping source, bare-name multi-type, `#` in id, unresolved-reference report format unbound (`:497`) | Invents resolution and reporting rules | 1 | A |
| 19 | Data model specifies no `NOT NULL`/`CHECK`/enum constraints (`:214`–`:224`) | Invents every constraint | 2 | B |
| 20 | AD-10 "single writer" (`:533`) but no write path granted for `Proposal.state` or session context | Invents writer ownership | 2 | A |
| 21 | `clock` citation not addressable; AD-5 caption not in `canonical_strings`; `operator_role` id format; SQLite schema-versioning; UX-26 polling contract (`:222`, `:473`, `:602`, `:461`) | Invents each | 2 | A/B |

## Triage

Every finding is triaged Accept / Defer / Reject. **Resolution** names the artifact the fix landed in
and `Fixed?` flips to ☑ only when the change is present in that artifact.

**Resolution record (completed 2026-10-16).** No separate `AD-16`/`AD-17` batch was created; the
accepted findings were folded into `planning/detailed-design/contracts.md` (§0–§6), `dto.py`,
`openapi.yaml`, and `001_module12_copilot_schema.sql` via decisions **D52–D68**, plus amendments to
AD-2/AD-3/AD-4/AD-5/AD-6/AD-7/AD-8/AD-10/AD-12/AD-13/AD-14/AD-15 in `planning/ARCHITECTURE.md`.

| Gap # | Triage | Reason | Resolution (owner · artifact) | Fixed? |
|---|---|---|---|---|
| 1 | Accept | The client cannot build against an undefined resource | D64 · `dto.py` + `openapi.yaml` request/response schemas | ☑ |
| 2 | Accept | Status codes are the machine-enforceable part of the contract | D58 · `contracts.md` §2 preamble + §4; `openapi.yaml` `x-error-catalog` | ☑ |
| 3 | Accept | Needed for idempotency/concurrency on the query path | `contracts.md` §1 concurrency clause (query POST intentionally non-idempotent; repeat = new turn) | ☑ |
| 4 | Accept | FR-14 is untestable without a frozen Clock port | OP-10 `clock_port` + DP-5; `ClockReadDTO`; AD-14 clock citation | ☑ |
| 5 | Accept | Contradictory LLM failure behavior must be reconciled | D56 · one LLM-prose budget; `contracts.md` §1 `answer_query`, §3.1 OP-14 | ☑ |
| 6 | Accept | Determines FR-15/AD-8 enforcement | D48 · `contracts.md` §3 OP-14 token-scan (reject-and-retry-once, never strip) | ☑ |
| 7 | Accept | `answer_chain` is a rendered, asserted artifact | D60 · `contracts.md` §0.4 `answer_chain` contiguity + stage enum | ☑ |
| 8 | Accept | Required by AD-14 and the FR-14 position assertion | D60/D66 · `Evidence.position` starts at 0, contiguous; schema UNIQUE backstop | ☑ |
| 9 | Accept | Routing and decomposition shape are contract-bearing | D54 · `contracts.md` §0.4 `AnswerEnvelope` (compound ⇒ `len(answers) ≥ 2`); §1 `answer_query` Q1 | ☑ |
| 10 | Accept | NFR-7 "0 hard crashes" needs an enforcement home | D52/D64 · `contracts.md` §2 route-level validation (400 family) | ☑ |
| 11 | Accept | AD-4 requires a materialized `confirmed` stage | D32/D47/D55 · `contracts.md` §1 propose/confirm; `ProposalState` enum | ☑ |
| 12 | Accept | Gate proof is otherwise circular and untestable | D47/D66 · `GateToken` (`^gt-[0-9a-f]{32}$`), TTL, `proposals.gate_token` UNIQUE | ☑ |
| 13 | Accept | Single-winner semantics must be a stored transition | D32/D55 · `contracts.md` §1 `confirm_and_dispatch`, §2 `post_re_dispatch`; `PROPOSAL_STATE_INVALID` | ☑ |
| 14 | Accept | Snapshot re-validation depends on a fixed key | D55 · AD-6; `AffectedItemDTO` (`(id, actionable)`), `SelectorDTO` | ☑ |
| 15 | Accept | Executor failure classes must be typed | D59/D63 · AD-12/AD-15; §3.1 OP-15; `ExecutorStatus` + `EXECUTOR_*`/`CONFIRMATION_*` codes | ☑ |
| 16 | Accept | UI states need a backing contract (rubric: every UX state) | D58 · `contracts.md` §2 destructive + §4; `test/traceability-matrix.md` §4b UX-state coverage | ☑ |
| 17 | Accept | Determinism and citation integrity depend on it | D60/D61 · AD-7 case-fold; `citation_id`→`EntityKey` prefix mapping (`contracts.md` §0.1) | ☑ |
| 18 | Accept | Anti-fabrication behavior must be fully specified | D61 · `RawRef` `#`-escaping; `S_ENF` names refs in input order (AD-7) | ☑ |
| 19 | Accept | Schema is where invariants become physical | D66 · `001_module12_copilot_schema.sql` NOT NULL/CHECK/UNIQUE/enum constraints | ☑ |
| 20 | Accept | AD-10 single-writer must name the proposal/session writer | D66 · AD-10 amendment — Audit Writer writes `Proposal.executor_result` + executor row | ☑ |
| 21a | Accept | `clock` citation must be addressable (AD-14) | **OPEN** — no `GET /api/v1/state/clock/{id}` route (nor a UX non-clickable decision); tracked as `test/test-design.md` **T-11 / P0-G9** | ☐ |
| 21b | Accept | Caption must live in `canonical_strings` | D57 · `contracts.md` §0.1 canonical table `S_CAP`; carried in `Proposal.confirmation.caption` | ☑ |
| 21c | Accept | NFR-11 requires an operator id, not a role | D66 · AD-10 amendment; `OperatorRole` `^role-[a-z0-9_-]{1,32}$` | ☑ |
| 21d | Defer | Prototype re-creates the DB from `001_*.sql`; versioning is an implementation detail | Phase 2 note (no AD) | n/a |
| 21e | Reject | AD-7 already requires exactly-one resolution; a multi-match falls under `Entity Not Found in State` | — (already covered) | n/a |

### Triage summary

- **Accept:** 24 · **folded in:** 23 · **still open:** 1 (21a — clock-citation addressability).
- **Defer:** 1 (21d — SQLite schema-versioning).
- **Reject:** 1 (21e — multi-match canonical response, covered by AD-7).

The single open Accepted finding (21a) is not an oversight: AD-14 requires `clock#<read_id>` to be
citable while §2 defines no `GET /api/v1/state/clock/{id}` route. Resolving it is an Architect/UX
decision — either add the route or mark the clock citation non-clickable — and is owned by the
Phase-0 gap **P0-G9** (`test/test-design.md` §4.1). No accepted finding was silently dropped.

---

*Companion to `planning/ARCHITECTURE.md`. Triage performed by the pair on 2026-10-16.*
