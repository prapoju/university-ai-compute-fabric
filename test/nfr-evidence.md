---
title: Module 12 — AI Operations Copilot — NFR Evidence Map
status: draft
created: 2026-10-16
updated: 2026-10-16
binds: [PRD §8 NFR-1..NFR-11, PRD §15 S1..S4/EC/PT, FR-01..FR-16, contracts.md §1/§3, test/test-design.md]
sources:
  - planning/prd.md (§8, §9, §15)
  - planning/detailed-design/contracts.md (§1 latency/concurrency, §3 ports)
  - test/test-design.md (§1 risk register, §3 thresholds, §4 gaps)
  - tests/README.md, tests/conftest.py, tests/support/*
  - _bmad-output/test-artifacts/framework-setup-progress.md
---

# NFR Evidence Map — Module 12: AI Operations Copilot

**Purpose.** One row per PRD NFR (§8): the numeric metric + threshold, *how it is measured*
(tool · fixture · sample size N), the artifact that will hold the evidence, and its current
status. This is the evidence ledger the release gate reads; it does not restate the NFRs.

**Status legend.**
- **EVIDENCED** — a committed, currently passing artifact asserts the NFR's threshold today.
- **PLANNED** — the measurement is specified and its harness seam exists, but no passing
  artifact asserts the threshold yet (implementation is in the ATDD red phase; `service/`
  does not exist — see `test/atdd/module12_interface.py`).

A row is **PLANNED** unless the whole measurable test condition is green. Where a *guard* for
the NFR is already green at the schema/harness layer, that is called out explicitly in the
**Evidence artifact** cell with the prefix `EVIDENCED (guard):`; it does **not** upgrade the
row's status, because the NFR metric itself is still unmeasured.

**Measurement substrate (shared).** Tool: `pytest` 9.x + `pytest-asyncio` + `hypothesis`
(`pytest.ini`). Fixtures: `fake_clock`, `seed_fleet`, `sim_telemetry`, `db`, `explain_assert`,
`sample`, `ids` (`tests/conftest.py`). Scenario carriers: `test/atdd/module12_contracts.test.py`
(red phase) and the suites named in `test/test-design.md` §5. No wall-clock reads, no
`uuid4`/`random` (R2 / OP-10 / OP-13).

---

## 1. NFR evidence ledger

| NFR | Metric & threshold | How measured (tool · fixture · N) | Evidence artifact | Status |
|---|---|---|---|---|
| **NFR-1 Diagnosis accuracy** | 100% correct on the 4 mandatory fixtures (`S1`–`S4`); ≥ 90% on a 20-query extension corpus | `pytest`; fixtures `S1`–`S4` from `prd.md` §15 + 20-query extension set; N = 4 golden + 20 variants; assert `diagnosis_class` + cited clause/step | Planned suite `tests/diagnosis_accuracy` (asserts ATDD `diagnose_*` contracts); red seeds: `test/atdd/module12_contracts.test.py::test_diagnose_access_denial_*`, `::test_diagnose_schedule_window_*`, `::test_diagnose_retrospective_*`, `::test_diagnose_node_triage_*` | PLANNED |
| **NFR-2 Anti-fabrication** | ≥ 10 non-existent references → 100% `S_ENF`; fabricated entities/policies/events = 0 across the defined corpus | `pytest` (+ `hypothesis` negative strategies); fixture: negative-reference corpus (imaginary user, non-existent policy, unknown node, event that never occurred), seeded into `OperationalStore`; N ≥ 10 negatives; assert canonical string + zero invented fields | Planned suite `tests/anti_fabrication` (EC / R-01, P0); red seeds: `::test_resolve_entities_*`, `::test_propose_destructive_action_precondition_unresolved_target_is_entity_not_found`, `::test_get_citation_precondition_absent_is_404_with_s_enf_body`; rubric per `test-design.md` §3.4 | PLANNED |
| **NFR-3 Citation integrity** | 100% of factual claims carry ≥ 1 citation; 100% of citations resolve to an existing record; 0 uncited claims | `pytest`; programmatic rubric (`prd.md` FR-13) cross-checks each claim's citations against the fixed evidence payload; all fixture outputs; N = 4 fixtures + variants (~24 answers); **plus** DB guard | `EVIDENCED (guard): tests/integration/test_db_schema.py::test_claim_must_retain_a_citation` (AD-8: `claim_citations` delete blocked when it would drop a claim to 0 citations). Planned suite `tests/citation_coverage` (R-05, P0); red seeds: `::test_answer_query_happy_returns_cited_envelope_no_operational_writes` | PLANNED |
| **NFR-4 Determinism** | 100% identity of evidence set, `position` sequence, citation set, diagnosis class, runbook steps across 3 runs per fixture (prose exempt) | `pytest -m determinism`; freeze/advance `fake_clock`, seeded `IdFactory`; N = 4 fixtures × 3 runs = 12 runs; fingerprint `(diagnosis_class, [citation_id], [position])` | `EVIDENCED (guard): tests/unit/test_fake_clock.py` + `tests/test_example.py::test_clock_reads_are_unique_formatted_and_monotonic` (reproducible clock is the precondition for I2). Planned suite `tests/determinism` (R-07); red seed: `::test_answer_query_invariant_determinism_across_three_runs` | PLANNED |
| **NFR-5 Latency (performance)** | p95 ≤ 3000 ms submit→rendered cited answer; p95 ≤ 5000 ms runbook generation; p99 ≤ 8000 ms — **at 5 concurrent sessions**, 50 queries/hour sustained | `pytest-benchmark` (to add) **or** custom timer reading the injectable metrics sink (`m12.answer_query.latency_ms`, T-6/P0-G5); warm fixture state; N ≥ 100 timed queries at 5 concurrent sessions; report p95/p99; sub-budgets from `contracts.md` (`resolve_entities` < 20 ms, `assemble_evidence` < 100 ms, `diagnose_*` < 10 ms, LLM prose p95 ≤ 3000 ms) | Planned suite `tests/latency` → `_bmad-output/test-artifacts/nfr-latency-run.json`; harness precondition: fake `llm_prose_port` (T-4/P0-G2) so latency is hermetic | PLANNED |
| **NFR-6 Concurrency** | **≥ 5 concurrent operator sessions** (session-level, not persona); ≥ 50 queries/hour sustained with no degradation | `pytest-asyncio` + `httpx.AsyncClient` driving the in-process ASGI app; N = 5 concurrent sessions, ≥ 50 turns; assert no cross-session context bleed + per-session latency within NFR-5; single SQLite writer (WAL) serializes writes (`contracts.md` §1 concurrency clause) | Planned suite `tests/concurrency` (harness gap T-7 → P0-G6); carriers: `::test_create_session_invariant_session_ids_are_unique`, `::test_submit_query_invariant_repeat_is_a_new_turn_not_idempotent`, `::test_reset_session_invariant_idempotent_and_never_authorizes_destructive` | PLANNED |
| **NFR-7 Availability & robustness (reliability / failure)** | ≥ 99% over a continuous 8-hour evaluation window; **cold-start recovery ≤ 60 s**; 0 hard crashes on malformed input (100% graceful) | `pytest`; simulate 8 h by `fake_clock.advance`; fault injection per class — LLM timeout, state-provider failure, policy-source failure, malformed input, executor unavailability — N = 5 failure classes × repeated turns; assert explicit degraded response (no fabrication), 0 uncaught exceptions, and recovery ≤ 60 s | Planned suite `tests/fault_injection` (R-08, FR-16); red seeds: `::test_assemble_evidence_fault_provider_down_returns_s_pua_no_partial_evidence`, `::test_diagnose_schedule_window_fault_clock_unavailable`; recovery path via `sim_telemetry.script_restart` | PLANNED |
| **NFR-8 Safety** | copilot-originated mutations = 0; 100% of destructive intents → refusal + dry-run; 100% require confirmation before handoff; 100% of tool calls audited | `pytest` instrumentation over the full scenario suite; assert `OperationalStore.mutations == []` and `RecordingExecutor.calls` cardinality (exactly 1 dispatch, post-confirm); N = S1–S4 + EC + PT + variant suite | `EVIDENCED (guard): tests/integration/test_db_schema.py::test_proposal_state_machine_blocks_illegal_jump` (AD-4: `dry_run→executed` illegal in DB). Planned suite `tests/safety_instrumentation` / `tests/confirmation_semantics` (R-02/R-03, P0); red seeds: `::test_propose_destructive_action_happy_builds_dry_run_snapshot`, `::test_confirm_and_dispatch_*` | PLANNED |
| **NFR-9 Usability** | ≥ 90% of Nadia-class operators complete a diagnosis end-to-end in < 5 min after a 10-min walkthrough; no infra expertise required | Moderated usability study (not automatable); N ≥ 10 Nadia-class participants (`A-15`); timed end-to-end task on the PT console; record completion rate + time | Planned artifact `_bmad-output/test-artifacts/nfr-usability-report.md` (+ task checklist derived from UJ-1–UJ-4); E2E carriers `tests/e2e` (S1–S4 journeys) | PLANNED |
| **NFR-10 Extensibility** | Adding a new entity type to the state model ≤ 1 dev-day with no console change; adding a runbook template is config-only | Timeboxed change spike + diff review; N = 1 new entity type (e.g. reservation) + 1 new runbook template; assert no console/UI diff and read-contract-extension only (`C-4`) | Planned artifact `_bmad-output/test-artifacts/nfr-extensibility-spike.md`; contract anchor: runbook registry `register` (`contracts.md` §3 `lookup_runbook`); red seed: `::test_lookup_runbook_invariant_empty_steps_template_rejected_at_registration` | PLANNED |
| **NFR-11 Security / privacy (isolation & logging)** | Audit entries contain only operator id (synthetic role), session id, tool metadata, query-derived entity ids — **no credentials, tokens, or secrets (e.g. `gate_token` never logged)**; prototype cap with oldest-first rotation; console exposes no state-mutating control; no PII beyond simulated ids | `pytest` + `sqlite3` + a secret/PII regex scanner over sampled entries; N = a 50-call audit session, scan 100% of entries for `gt-*`, passwords, bearer tokens, `OKEN`/`API_KEY` patterns; retention test fills the cap and asserts oldest-first eviction + rotation log; route allowlist asserts no mutating route outside `/api/v1/destructive/*` + `/executor/v1/*` | `EVIDENCED (guard): tests/integration/test_db_schema.py::test_audit_records_are_append_only` (AD-10 append-only + D42 rotation gate) and `::test_all_owned_tables_and_key_triggers_exist`. Planned suites `tests/audit` / `tests/audit_redaction` / `tests/retention` / `tests/route_audit` (R-10/R-12); red seed: `::test_reset_session_invariant_idempotent_and_never_authorizes_destructive` | PLANNED |

---

## 2. Required-category coverage (minimum evidence set)

| Category | NFR(s) | Performance/concurrency number | Reliability/failure number | Security/isolation number |
|---|---|---|---|---|
| **Performance** | NFR-5, NFR-6 | p95 ≤ 3000 ms (answer) · p99 ≤ 8000 ms · runbook p95 ≤ 5000 ms · **5 concurrent sessions · 50 queries/hour** | — | — |
| **Reliability / failure** | NFR-7 (FR-16) | — | **cold-start recovery ≤ 60 s** · ≥ 99% / 8 h · **LLM timeout 5000 ms → `LLM_UNAVAILABLE`** · **executor timeout 5000 ms → state `failed`, no auto-retry** · provider failure → `S_PUA` · 0 hard crashes on malformed input · LLM prose retried **once**, never stripped | — |
| **Security / isolation** | NFR-11, NFR-8 | — | — | **audit token/secret redaction (gate token never logged)** · append-only, no edit/delete control · role-scoped sessions; destructive intent needs explicit procedural confirmation before any handoff · 0 copilot-originated mutations |

---

## 3. Timing / timeout constants pinned by the contract (measurement inputs)

| Constant | Value | Source |
|---|---|---|
| Answer latency budget (submit→rendered) | p95 ≤ 3000 ms, p99 ≤ 8000 ms | `contracts.md` §1 `answer_query` |
| Runbook read latency | p95 ≤ 5000 ms | `prd.md` NFR-5 |
| Destructive dry-run path | p95 ≤ 2000 ms; confirm+dispatch p95 ≤ 5500 ms | `contracts.md` §1 `propose_destructive_action` / `confirm_and_dispatch` |
| LLM prose call timeout | 5000 ms → `LLM_UNAVAILABLE`; ≤ 2 attempts (1 retry) | `contracts.md` §3 OP-14 |
| Executor dispatch timeout | 5000 ms → `EXECUTOR_UNAVAILABLE`, state `failed`, no auto-retry | `contracts.md` §1 `confirm_and_dispatch` P6 / D31 |
| Gate-token TTL | ≤ 15 min | `contracts.md` §1 `confirm_and_dispatch` P2 / D47 |
| Session idle expiry | > 30 min → `SESSION_EXPIRED` (410) | `contracts.md` §1 P2 / D51 |
| Cold-start recovery | ≤ 60 s | `prd.md` NFR-7 |

---

## 4. Open measurement gaps blocking EVIDENCED status

These must close in Phase 0 before any NFR row can move to EVIDENCED (from `test-design.md` §4/§4.1).

| Gap | Blocks NFR | Fix |
|---|---|---|
| **T-6 / P0-G5** injectable metrics sink (`m12.*` counters) | NFR-5, NFR-6, NFR-8 | define a metrics-recorder port asserted by tests |
| **T-7 / P0-G6** concurrency + clock-advance harness | NFR-5, NFR-6, NFR-7 | ≥ 5-session harness + reset-vs-in-flight fixture |
| **T-4 / P0-G2** fake `llm_prose_port` (deterministic, injectable timeout/rejection) | NFR-1, NFR-3, NFR-5, NFR-7 | hermetic prose double; Ollama only in a non-gating lane |
| **T-5 / P0-G2** fake executor with `delay(ms)` + `late_response` | NFR-7 | drives the 5 s timeout / late-response path |
| **T-3 / P0-G1** versioned seed fixtures + frozen snapshots + seeded clock/idgen | NFR-1, NFR-2, NFR-4 | reproducible corpus for accuracy + determinism |
| **T-11 / P0-G9** clock-citation addressability | NFR-3 | add clock inspection route or mark the citation non-clickable |

---

## 5. Currently green (harness/schema) evidence — supports, not yet sufficient

| Artifact | Asserts | Supports NFR |
|---|---|---|
| `tests/unit/test_fake_clock.py` (6 tests) | deterministic, reproducible, monotonic, never wall-clock | NFR-4 (precondition) |
| `tests/test_example.py` (+ hypothesis) | clock identity across N up to 50; all fixtures wired; S3 reproduced | NFR-4, NFR-1 (fixture only) |
| `tests/integration/test_db_schema.py` (8 tests) | append-only audit + rotation gate; proposal state machine; ≥ 1 citation per claim; evidence uniqueness; partial-apply must fail | NFR-3, NFR-8, NFR-11 (DB guards) |
| `tests/support/telemetry.py` | scripted thermal fault reproduces `S3`; restart path for recovery timing | NFR-7 (recovery fixture) |
| `_bmad-output/test-artifacts/framework-setup-progress.md` | `39 passed`; SQLite 3.50.4 ≥ 3.35 | environment precondition (AD-10) |

---

*Companion to `test/test-design.md` (risk register, level allocation, thresholds) and
`planning/detailed-design/contracts.md`. Authored 2026-10-16. Every non-EVIDENCED row is
tracked as PLANNED with its blocking Phase 0 gap (§4); update status in place as artifacts land.*
