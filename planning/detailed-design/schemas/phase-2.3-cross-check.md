# Module 12 — Phase 2.2 → Phase 2.3 Cross-Check

**Purpose.** Every place where the Phase 2.2 artifacts (`001_module12_copilot_schema.sql`, `dto.py`,
`events.schema.json` + `events.md`, `openapi.yaml`) **cannot** express a `contracts.md` invariant
(precondition/postcondition, §5 invariant, or AD rule) — so Phase 2.3 can carry it as an explicit
runtime/CI guard. Each row names the artifact, the contract reference, why it is inexpressible, the
mitigation already present, and the action for 2.3.

Baseline: `contracts.md` (§0.1–§0.6, §1 core ops, §2 inbound ops, §3 OP-1..OP-15, §4
error catalog, §5 I1..I22, §6 coverage), `ARCHITECTURE.md` (AD-1..AD-15, D42/D46/D50).

## Findings

| ID | Artifact | Contract ref | Why it can't be expressed | Mitigation already in Phase 2.2 | Action for Phase 2.3 |
|---|---|---|---|---|---|
| X-01 | SQL | §0.4 `Claim.claim_citations` `len>=1`, §5 I3 | SQLite has no deferred `CHECK` / `DEFERRABLE` for "≥1 child row" at INSERT time; a claim and its first citation are separate rows. | `trg_claim_citations_guard_delete` blocks deleting a claim's last citation; composer inserts claim+citations in one transaction. | Add an explicit answer-composition "finalize" step + `tests/citation_coverage` assertion that no claim has zero rows; consider a trigger on an `answers.composed` flag. |
| X-02 | SQL | §0.1 `IdString` | SQLite `GLOB` has no quantifier `{16}`, so the per-kind regex is approximated by prefix + fixed length. | `CHECK (id GLOB '<prefix>-*' AND length(id) = N)` on answer/claim/tool_call/audit/proposal. | **RESOLVED (D67).** `evidence` is removed from `IdKind`: an `Evidence` row is keyed by `(answer_id, citation_id)` and `citation_id` is a provider key, never minted by `idgen_port`. `IdString`/DTO/SQL header updated (`ev` prefix dropped). Prefix+length checks are sufficient; exact regex lives in DTOs. |
| X-03 | SQL | §0.1 `Instant` | Exact ISO-8601 `^\d{4}-…(\.\d{3})?Z$` is a regex; SQLite `GLOB` only approximates the shape. | `GLOB` shape check on every timestamp column; exact regex enforced by the `Instant` DTO. | Keep exact validation at the DTO/ingress boundary; document that the DDL check is a shape guard, not the normative regex. |
| X-04 | SQL | §0.4 `AnswerChain` "contiguous prefix, never reordered/skipped"; `AnswerEnvelope` len≥2 for decomposed compound (D37) | Column `CHECK(json_valid(...))` cannot assert array order/contiguity or element membership. | `answer_chain` stored as JSON; emitted by deterministic code. | Add a trigger using `json_each` (enforce the closed enum + prefix rule) or an application guard + `tests/determinism`. |
| X-05 | SQL | AD-3/AD-4/AD-6/I9/I13 | The DB enforces legal state transitions (`trg_proposals_state_machine` + conditional UPDATEs) but cannot verify that a **refusal** preceded `dry_run`, nor perform AD-6 snapshot re-validation against live provider state. | State-machine trigger + conditional-UPDATE guards (C5–C7 in the SQL). | Re-validation and refusal-precedence are runtime (Confirmation Gate); assert via `tests/dryrun_revalidation` and `tests/safety_instrumentation`. |
| X-06 | events | AD-10/I14, §3 OP-1..OP-14 | Provider **reads** are audited as `tool_call` rows, not emitted as first-class events; there is no `port_read` eventType. | `tool_call` events carry `tool_name = toolcall.<op>`. | If 2.3 wants per-read telemetry, add a `port_read` eventType with `port` + `method` to `events.schema.json`. |
| X-07 | SQL | §5 I2/I5 (`position` monotonic, assigned at assembly) | SQLite cannot assert a contiguous `0..n-1` strictly-increasing sequence; `UNIQUE(answer_id, position)` allows gaps. | `UNIQUE(answer_id, position)` + `position NOT NULL`. | Assert contiguity/monotonicity in `tests/determinism` (position-sequence assertion). |
| X-08 | SQL | §5 I15, D45, NFR-11 (audit secret-free) | `CHECK(json_valid(result_summary))` cannot assert absence of credential-named keys. | Write-time redaction filter (application) + append-only trigger. | Keep `tests/audit_redaction` (0 secrets in sampled entries); no DDL change. |
| X-09 | SQL/DTO | OP-13 Q2, FR-14 | "Seeded simulated idgen returns a fixed sequence so runs reproduce ids" is an adapter property, not a store constraint. | `IdKind`/`IdString` DTOs; ids are PKs. | Assert in `tests/determinism` with the seeded `idgen_port` adapter. |
| X-10 | DTO/SQL | §5 I3, D48, OP-14 | "Prose scanned against EvidenceSet vocabulary; whole output rejected and retried once, never stripped" cannot be a storage constraint. | `LLM_PROSE_REJECTED` error code; `prose` stores only accepted prose; OP-14 DTOs added. | Enforce in the `llm_prose_port` adapter; `tests/citation_coverage` scans rendered answer text. |
| X-11 | SQL | AD-15, I21 | "Executor applies exactly the referenced snapshot without re-enumeration" is a behavioral contract, not schema-expressible. | `ExecutorRequest` frozen schema (DTO + OpenAPI + `allOf` CHECK on `executor_result`). | `tests/executor_contract`: schema conformance; double-apply surfaces failure. |
| X-12 | OpenAPI/DTO | AD-6, `CONFIRMATION_STALE` | Comparing live provider state to the stored snapshot is external to the schema/HTTP contract. | 409 `Response409` documents the code. | Runtime (Confirmation Gate); `tests/dryrun_revalidation`. |
| X-13 | SQL | D35, AD-7 | Session-context-first follow-up resolution that re-resolves against providers before use is runtime. | `session.context_*` JSON columns. | Runtime; `tests/anti_fabrication`. |
| X-14 | SQL | §5 I20, D50 | The 10,000-row retention cap + oldest-first rotation is a job + config value; only append-only + the D42 gate are physical. | `audit_rotation_gate` + `trg_audit_records_no_delete`; rotation statement C9. | `tests/retention`: cap honored, oldest evicted first, rotation logged. |
| X-15 | OpenAPI | §4 `ENTITY_NOT_FOUND` (404 **and** 200 canonical) | One status code cannot carry both shapes from a single reusable response component. | 200 body modeled `oneOf(AnswerEnvelope|Proposal, ErrorBody)`; `x-error-catalog` records the 404/200 duality. | Keep the duality documented; downstream codegen must treat `ErrorBody` as a valid 200 body on query/dry-run routes. |
| X-16 | OpenAPI | §4 `VALIDATION_BAD_ID_KIND` (HTTP 400) | The code is raised by OP-13 `idgen_port`, which is **outbound** and has no ingress route; no OpenAPI operation can return it directly. | Code added to `ErrorCode` enum + `x-error-catalog` (http 400). | **RESOLVED (D67): internal-only.** `VALIDATION_BAD_ID_KIND` signals a programming error (an internal caller passed an out-of-enum `kind` to `idgen_port`); it is not reachable from any client request, so no ingress route returns it. It remains in the `ErrorCode` enum for the port boundary and is annotated `internal-only` in `x-error-catalog`; it is never mapped to a client 4xx. |
| X-17 | SQL | AD-5/I12 | "Confirmation records no identity; session context never consulted" is a code-path property; the schema can only omit identity columns on `proposals`. | `proposals`/`confirm` carry no identity/role column. | `tests/confirmation_semantics`: no role/identity field stored or read. |

## Positive (physically enforced — no Phase 2.3 action)

The following §5 invariants **are** enforced by the DDL/OpenAPI and need no runtime guard:
AD-14 evidence `UNIQUE(answer_id, citation_id)` + `position NOT NULL` (I2/I5);
I14 exactly one audit row per tool call (`ux_audit_tool_call`);
AD-15 one executor-applied record per proposal (`ux_audit_executor_apply`);
AD-4 `Proposal.state` CHECK + `trg_proposals_state_machine` (I9);
AD-10 append-only audit triggers with the D42 rotation exemption (I14/I20);
claim_citations join shape (I3, delete side — see X-01 for the insert side);
`AnswerChain`/`CanonicalCode`/`DiagnosisClass`/`ExecutorStatus` closed enums;
D46 pagination cap (`page_size <= 100`) at DTO + OpenAPI.
