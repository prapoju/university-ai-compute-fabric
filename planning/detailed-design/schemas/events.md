# Module 12 — Event & Telemetry Payloads (Phase 2.2)

**Purpose.** Define every event Module 12 **emits** or **ingests**, with a common envelope, so producers and consumers cannot diverge. The machine contract is `events.schema.json` (JSON Schema 2020-12). Stored append-only in the `audit_events` table (`001_module12_copilot_schema.sql`); `event_type` mirrors the envelope `eventType`.

**Names** follow `contracts.md` (§0.3 `OperationalEvent`, §0.4/§0.5 answer + proposal types, §4 error catalog, §5 invariants) and `ARCHITECTURE.md` (§2.2 records, AD-2, AD-10, AD-12, AD-15).

## Envelope (every event)

| Field | Type | Rule |
|---|---|---|
| `eventId` | string | Unique, stable. Minted via `idgen_port` (OP-13, `IdKind` `event`) as `evt-[0-9a-f]{16}`, or an injected estate key `{type}#{id}`; never a random/ULID value and never regenerated (D59, A20). |
| `occurredAt` | string | ISO-8601 UTC, `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z$`. From the Clock port only (R2/OP-10). |
| `schemaVersion` | string | Semver of the payload schema, e.g. `"1.0.0"`. |
| `eventType` | enum | One of the five types below. |
| `sessionId` | string \| null | Present when the event belongs to a session. |
| `payload` | object | Type-specific body (below). |

## Event catalog

| `eventType` | Direction | Source / sink | Payload | Governed by |
|---|---|---|---|---|
| `operational_event_ingested` | ingest | `event_store_port` (OP-9) reads `OperationalEvent` from the estate | `event_id, type, entity_ref, timestamp, outcome, recorded_reason` | §0.3; AD-1, AD-13 (read-only) |
| `tool_call` | emit | `tool_calls` / Audit Writer interception | `tool_call_id, session_id, tool_name, params_summary, timestamp, status` | §4 `toolcall.*`; AD-10, I14 |
| `audit` | emit | Audit Writer (single writer) | `audit_id, tool_call_id?, session_id?, operator_role?, timestamp, result_summary, actor, proposal_id?` | ARCH §2.2 `AuditRecord`; AD-10, AD-15 |
| `proposal_lifecycle` | emit | Safety workflow (Proposal Dispatcher) | `proposal_id, session_id, action, from_state, to_state, at, applied_count?` | §0.5; AD-3, AD-4, AD-6, AD-15 |
| `answer_produced` | emit | Application ring after `answer_query` | `answer_id, session_id, intent, answer_chain, diagnosis_class?, canonical?, claim_count, evidence_count, prose_present, at` | §0.4; AD-2, AD-8, AD-14 |

## Payload field notes

- **`operational_event_ingested`** — `type ∈ {access_denied, job_cancelled, node_cordoned}`; `entity_ref` is `{type}#{id}`; `timestamp` is the event's own instant (not the ingest instant) and is matched half-open `[start, end)` by `event_store_port.query` (AD-2, D40). `recorded_reason` is read directly, never replayed (D25).
- **`tool_call`** — exactly one `tool_call_id`; `tool_name` is `toolcall.<op>` (e.g. `toolcall.answer_query`, `toolcall.resolve_entities`); `params_summary` is redacted at write (NFR-11, D45); `status ∈ {ok, failure}`.
- **`audit`** — `actor ∈ {copilot, executor}`; when `actor = executor`, `tool_call_id` is `null` and `proposal_id` is set (AD-10, AD-15). Append-only; never updated or deleted (D42 rotation exempts only retention).
- **`proposal_lifecycle`** — one event per transition of the ordered state machine `refused → dry_run → confirmed → dispatched → executed|failed|superseded` (AD-4). `from_state`/`to_state` carry the transition; only the legal transition set is admitted — `refused→dry_run`, `dry_run→confirmed`, `confirmed→dispatched`, `dispatched→{executed|failed}`, `failed→superseded`; any other pair is rejected (D59, E37). `applied_count` is present only on terminal `executed`/`failed` (D33).
- **`answer_produced`** — `answer_chain` is the ordered, contiguous stage prefix from `[observation, evidence, diagnosis, recommendation, proposal, execution]` (§0.4); the schema admits exactly the six legal prefixes, so a reordered or skipped chain fails validation (E50). `answer_chain` has `minItems: 1` (E23). When `claim_count >= 1`, `evidence_count >= 1` is required — an answer advertising an uncited claim is rejected (E24). `diagnosis_class`/`canonical` are emitted by deterministic code, never from LLM output (AD-2). `prose_present` is a boolean only — prose is not carried on the event bus.

## Notes for Phase 2.3

- `answer_produced` carries counts and the chain, not the full `Answer` graph; the `Answer`/`Evidence`/`Claim` rows are the authority (fetch via §2 routes).
- `proposal_lifecycle` is derived from `proposals.state` transitions; if an authoritative transition log is required, the `audit_events` row is the append-only record.
- The envelope has no ingest schema for provider **reads** (only the ingested `OperationalEvent`). Reads are audited as `tool_call` rows, not emitted as their own event type (finding X-06 in `phase-2.3-cross-check.md`).
