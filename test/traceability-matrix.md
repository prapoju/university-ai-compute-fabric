---
title: Module 12 — AI Operations Copilot — Traceability Matrix
workflow: bmad-testarch-trace
status: complete
collection_mode: contract_static
coverage_basis: acceptance_criteria
oracle_resolution_mode: formal_requirements
oracle_confidence: high
gate_type: story
decision_mode: deterministic
gate_status: NOT_EVALUATED
p0_requirements: 8
p0_linked_story_and_red_test: 8
stepsCompleted: ['step-01-load-context', 'step-02-discover-tests', 'step-03-map-criteria', 'step-04-analyze-gaps', 'step-05-gate-decision']
lastStep: 'step-05-gate-decision'
lastSaved: '2026-10-16'
created: 2026-10-16
updated: 2026-10-16
sources:
  - planning/prd.md (§7 FR-01..FR-16, §8 NFR-1..NFR-11, §15 S1..S4/EC/PT)
  - planning/ux/C-UX-Scenarios/00-ux-scenarios.md (Scenario 01..04)
  - planning/ARCHITECTURE.md (AD-1..AD-15)
  - planning/detailed-design/contracts.md (§1 core, §2 inbound, §4 errors, §5 invariants, §6 op→FR/AD)
  - planning/epics.md (Epic 1..4, Story 1.1..4.3) — Phase 4, story binding (canonical)
  - test/atdd/module12_contracts.test.py (red phase)
  - test/atdd/module12_interface.py (inbound-port contract stub)
review_set: test/atdd/
---

# Traceability Matrix — Module 12

## What this file is (simple words)

This file shows the chain from a requirement to a test to a story:

**PRD requirement → UX scenario → AD rule → contract clause → test → story → status.**

**P0 traceability: 8/8 P0 requirements (100%) are linked to a story and a red test** —
FR-03, FR-06, FR-09, FR-10, FR-13, FR-14, NFR-2, NFR-8 (the release-blocker set derived from
`test/test-design.md` §1.3: R-01, R-02, R-03, R-05). Each carries a Story ID in
`planning/epics.md` **and** ≥ 1 `RED` ATDD test in `test/atdd/module12_contracts.test.py`. No P0
requirement is a `GAP`.

If a line breaks, the gate fails. Right now every link exists, except that nothing is
**green** yet, because there is no `service/` code — only the interface stub. So every test
"fails on purpose" (`RED`). That is the correct red-phase state: P0 *traceability* is complete;
P0 *pass-rate* is deferred until the code exists (gate stays `NOT_EVALUATED`).

- **Test basis:** `test/atdd/module12_contracts.test.py` — 123 tests, `@pytest.mark.atdd`.
- **Story source:** `planning/epics.md` (Epic 1–4, 16 stories) — the canonical epics for this unit.
- **Story ID** is now filled in (Phase 4 is done) and bound to `planning/epics.md`.

**Status legend**
- `RED` — the test exists and fails on purpose (`NotImplementedError`) because the code is not written yet.
- `PARTIAL` — some parts have a test, some do not (see **Gap**).
- `GAP` — no test yet.
- Green/passing proof is tracked in `test/nfr-evidence.md`.

**Test ID.** This is the test function name inside `test/atdd/module12_contracts.test.py`.
A `*` means "all functions with this start".

---

## 1. Functional requirements

| PRD FR/NFR | Scenario (UX) | AD-n | Contract clause | Test ID | Story ID | Status |
|---|---|---|---|---|---|---|
| **FR-01** Conversational intake & intent routing | S1–S4 | AD-7, AD-11 | §1 `answer_query`; §2 `POST /api/v1/sessions/{sid}/queries`; §4 `VALIDATION_EMPTY_QUERY`, `VALIDATION_QUERY_TOO_LONG`, `CLARIFICATION`, `INTENT_NOT_SUPPORTED` | `test_answer_query_happy_returns_cited_envelope_no_operational_writes`, `test_answer_query_precondition_rejects_empty_query`, `test_answer_query_precondition_rejects_overlong_query`, `test_submit_query_happy_returns_envelope`, `test_submit_query_precondition_rejects_empty_query`, `test_submit_query_q_canonical_codes_return_200_errorbody_not_a_status_error`, `test_assemble_evidence_precondition_rejects_unregistered_intent`, `test_propose_destructive_action_precondition_compound_intent_needs_clarification` | 1.2 · 3.4 | RED |
| **FR-02** Minimal session & conversation context | S1–S4 | AD-5 | §2 `create_session`/`submit_query`/`get_session`/`reset_session`; §4 `SESSION_NOT_FOUND`, `SESSION_EXPIRED` | `test_create_session_*`, `test_get_session_*`, `test_reset_session_*`, `test_submit_query_precondition_absent_session_is_404`, `test_answer_query_precondition_rejects_absent_session`, `test_answer_query_precondition_expired_session_is_410`, `test_submit_query_invariant_repeat_is_a_new_turn_not_idempotent` | 1.2 · 3.4 | RED |
| **FR-03** Entity resolution (Entity-Not-Found guardrail) | S1–S4, EC | AD-7 | §1 `resolve_entities`; §4 `ENTITY_NOT_FOUND` (`S_ENF`); §5 I4 | `test_resolve_entities_*`, `test_edge_ec_resolve_entities_never_fabricates_an_imaginary_entity`, `test_edge_ec_resolve_entities_names_only_the_unresolved_refs`, `test_propose_destructive_action_precondition_unresolved_target_is_entity_not_found`, `test_get_state_record_precondition_absent_is_404_with_s_enf_body`, `test_get_citation_precondition_absent_is_404_with_s_enf_body`, `test_edge_ec_answer_query_imaginary_entity_is_canonical_not_fabricated` | 1.3 · 4.1 | RED |
| **FR-04** Access denial diagnosis | S1 (UJ-1) | AD-2, AD-8 | §1 `diagnose_access_denial`; §4 `CANNOT_CONFIRM` | `test_diagnose_access_denial_happy_class_from_evidence`, `test_diagnose_access_denial_precondition_rejects_wrong_entity_type`, `test_diagnose_access_denial_precondition_no_clause_is_cannot_confirm`, `test_diagnose_access_denial_invariant_clause_precedence_is_deterministic`, `test_edge_ec_answer_query_nonexistent_policy_clause_is_cannot_confirm` | 1.3 | RED |
| **FR-05** Schedule & window inquiry | S2 (UJ-2) | AD-2 (D38) | §1 `diagnose_schedule_window`; §5 I6 | `test_diagnose_schedule_window_happy_computes_next_open_window`, `test_diagnose_schedule_window_precondition_rejects_non_pending_job`, `test_diagnose_schedule_window_invariant_boundary_is_half_open`, `test_diagnose_schedule_window_q4_null_constraint_renders_no_window` | 3.1 | RED |
| **FR-06** Event-log retrospective diagnosis | S1, S2 (UJ-1/2) | AD-2 (D40) | §1 `diagnose_retrospective`; §4 `CANNOT_CONFIRM`; §5 I7 | `test_diagnose_retrospective_happy_one_claim_per_matched_event`, `test_diagnose_retrospective_precondition_rejects_inverted_window`, `test_diagnose_retrospective_precondition_rejects_bad_event_type`, `test_diagnose_retrospective_invariant_boundary_matched_once`, `test_diagnose_retrospective_invariant_type_precedence_is_deterministic`, `test_edge_ec_retrospective_zero_events_is_cannot_confirm` | 3.2 · 4.1 | RED |
| **FR-07** Node triage runbook | S3 (UJ-3) | AD-9 | §1 `diagnose_node_triage`; §4 `RUNBOOK_NOT_FOUND` (`S_RBX`) | `test_diagnose_node_triage_happy_returns_verbatim_template`, `test_diagnose_node_triage_precondition_rejects_uncordoned_node`, `test_diagnose_node_triage_precondition_code_mismatch_or_null_is_no_runbook`, `test_diagnose_node_triage_precondition_rejects_unsafe_code_format`, `test_diagnose_node_triage_invariant_unsourced_physical_template_renders_unavailability`, `test_explainability_node_triage_decision_cites_rule_and_observed_code` | 3.3 | RED |
| **FR-08** Runbook source rule | S3 (UJ-3) | AD-9 (D43/D44) | §1 `lookup_runbook`; §2 `GET /api/v1/runbooks/{error_code}`; §4 `RUNBOOK_TEMPLATE_EMPTY`, `RUNBOOK_TEMPLATE_UNSOURCED`; §5 I8 | `test_lookup_runbook_*`, `test_get_runbook_happy_returns_steps_and_provenance_separately`, `test_get_runbook_precondition_malformed_code_is_400`, `test_get_runbook_precondition_unknown_code_is_404_with_s_rbx_body`, `test_get_runbook_invariant_unsourced_physical_template_renders_unavailability` | 3.3 | RED |
| **FR-09** Destructive refusal, dry-run & confirmation | S4 (UJ-4) | AD-3, AD-4, AD-5, AD-6 | §1 `propose_destructive_action`; §2 `post_dry_run`; §4 `ACTION_REFUSED` (`S_ARF`), `DRY_RUN_EMPTY_SET`; §5 I9, I12 | `test_propose_destructive_action_*`, `test_post_dry_run_*`, `test_explainability_destructive_refusal_cites_rule_and_scope`, `test_post_re_dispatch_precondition_dispatched_parent_is_409` | 2.1 · 2.2 · 2.3 | RED |
| **FR-10** Propose-only executor handoff | S4 (UJ-4) | AD-1, AD-3, AD-6, AD-15 | §1 `confirm_and_dispatch`; §2 `post_confirm`/`get_proposal`/`post_re_dispatch`; executor `POST /executor/v1/proposals`; §4 `GATE_TOKEN_INVALID`, `CONFIRMATION_STALE`, `CONFIRMATION_CONFLICT`, `EXECUTOR_DUPLICATE_APPLY`; §5 I10, I21 | `test_confirm_and_dispatch_*`, `test_post_confirm_*`, `test_get_proposal_*`, `test_post_re_dispatch_*`, `test_executor_post_proposal_*`, `test_executor_get_proposal_*` | 2.4 | RED |
| **FR-11** Tool-call audit log | S1–S4 | AD-10 | §2 `GET /api/v1/sessions/{sid}/audit`; §5 I14, I15, I20 | `test_get_audit_page_happy_chronological`, `test_get_audit_page_precondition_bad_pagination_is_400`, `test_get_audit_page_precondition_absent_session_is_404`, `test_get_audit_page_invariant_read_of_audit_is_not_itself_audited`; `s.audit.events` assertions across the suite | 1.5 | PARTIAL |
| **FR-12** State inspection viewer | S1–S3 | AD-1, AD-13 | §2 `get_state_record`, `browse_state`; §4 `VALIDATION_BAD_ENTITY_TYPE`, `PAGINATION_INVALID`; §5 I18, I22 | `test_get_state_record_*`, `test_browse_state_*` | 1.5 | RED |
| **FR-13** Citation & evidence integrity | S1–S3 | AD-8, AD-14 | §1 `assemble_evidence`; §2 `get_answer_evidence`, `get_citation`; §5 I3, I5 | `test_assemble_evidence_*`, `test_get_answer_evidence_*`, `test_get_citation_*`, `test_explainability_answer_query_carries_cited_rule_ids`, `test_explainability_node_triage_decision_cites_rule_and_observed_code`, `test_explainability_destructive_refusal_cites_rule_and_scope`, `test_explainability_guard_rejects_a_decision_without_a_rule_id` | 1.4 | RED |
| **FR-14** Deterministic reproducibility | S1–S4 | AD-2, AD-14 | §1 `assemble_evidence`; §5 I2, I5, I19 | `test_answer_query_invariant_determinism_across_three_runs`, `test_assemble_evidence_invariant_identical_inputs_identical_positions`, `test_resolve_entities_invariant_is_idempotent_over_a_snapshot`, `test_diagnose_access_denial_invariant_clause_precedence_is_deterministic`, `test_diagnose_retrospective_invariant_type_precedence_is_deterministic`, `test_get_session_invariant_idempotent_read_no_writes`, `test_get_state_record_invariant_renders_provider_fields_verbatim_no_writes`, `test_get_answer_evidence_invariant_is_ordered_subset_of_stored_set`, `test_get_proposal_invariant_idempotent_read_no_writes`, `test_executor_get_proposal_invariant_idempotent_read` | 1.4 | RED |
| **FR-15** Untrusted input & retrieved-content handling | PT / all UJs | AD-11 | §5 I16 | `test_injection_corpus_query_text_is_data_not_control`, `test_injection_corpus_retrieved_content_is_data_not_control` | 4.1 | RED |
| **FR-16** Safe failure on degraded dependencies | all UJs | AD-12 | §4 `PROVIDER_UNAVAILABLE` (`S_PUA`), `CLOCK_UNAVAILABLE`, `LLM_UNAVAILABLE`, `EXECUTOR_UNAVAILABLE`, `AUDIT_WRITE_FAILED`; §5 I17 | `test_assemble_evidence_fault_provider_down_returns_s_pua_no_partial_evidence`, `test_diagnose_schedule_window_fault_clock_unavailable` | 2.4 · 4.2 · 4.3 | PARTIAL |

---

## 2. Non-functional requirements

| PRD FR/NFR | Scenario (UX) | AD-n | Contract clause | Test ID | Story ID | Status |
|---|---|---|---|---|---|---|
| **NFR-1** Diagnosis accuracy | S1–S4 | AD-2, AD-8, AD-9 | §1 `diagnose_*`; §6 op→FR | `test_diagnose_access_denial_happy_class_from_evidence`, `test_diagnose_schedule_window_happy_computes_next_open_window`, `test_diagnose_retrospective_happy_one_claim_per_matched_event`, `test_diagnose_node_triage_happy_returns_verbatim_template` (fixture accuracy only; extension corpus absent) | 1.3 · 3.1 · 3.3 | PARTIAL |
| **NFR-2** Anti-fabrication | EC | AD-7 (NFR-2) | §4 `ENTITY_NOT_FOUND` (`S_ENF`); §5 I4 | `test_edge_ec_*` (5 tests), `test_resolve_entities_*`, `test_lookup_runbook_invariant_miss_returns_s_rbx_byte_exact` | 1.3 · 4.1 | RED |
| **NFR-3** Citation integrity | S1–S3 | AD-8, AD-14 | §5 I3; §2 `get_citation`, `get_answer_evidence` | `test_get_citation_*`, `test_get_answer_evidence_*`, `test_explainability_*` | 1.4 | RED |
| **NFR-4** Determinism | S1–S4 | AD-2, AD-14 | §5 I2, I5, I19 | `test_answer_query_invariant_determinism_across_three_runs`, idempotence invariants (see FR-14) | 1.4 | RED |
| **NFR-5** Latency (p95 ≤ 3 s / 5 s; p99 ≤ 8 s) | S1–S4 | AD-2 | §1 latency clause | *(none — no timing/perf harness)* | 1.3 · 3.1 · 3.2 · 3.3 | GAP |
| **NFR-6** Concurrency (≥ 5 sessions, ≥ 50 q/h) | all UJs | AD-10 (WAL) | §1 concurrency clause | `test_create_session_invariant_session_ids_are_unique`, `test_submit_query_invariant_repeat_is_a_new_turn_not_idempotent` (carriers only; no concurrent harness) | 1.2 | GAP |
| **NFR-7** Availability & robustness (≥ 99% / 8 h; cold-start ≤ 60 s; 0 crashes) | all UJs | AD-12 | §4 fault codes; §5 I17 | `test_assemble_evidence_fault_provider_down_returns_s_pua_no_partial_evidence`, `test_diagnose_schedule_window_fault_clock_unavailable` (2 of 5 failure classes) | 4.2 · 4.3 | PARTIAL |
| **NFR-8** Safety (0 mutations; 100% refusal+dry-run+confirm; 100% audited) | S4, all UJs | AD-1, AD-3, AD-4 | §5 I1, I9, I10, I12 | `s.store.mutations == []` assertions across the suite; `test_propose_destructive_action_happy_builds_dry_run_snapshot`, `test_propose_destructive_action_qfail_empty_affected_set_disables_confirm`, `test_confirm_and_dispatch_*`, `test_post_confirm_*` | 2.1 · 2.2 · 2.3 · 2.4 | RED |
| **NFR-9** Usability (≥ 90% < 5 min) | S1–S4 | — | — | *(none — moderated study)* | 1.3 | GAP |
| **NFR-10** Extensibility (≤ 1 dev-day; config-only runbook) | PT | AD-9, AD-13 | §3 `runbook_registry_port` | `test_lookup_runbook_invariant_empty_steps_template_rejected_at_registration` (anchor only) | 1.1 · 3.3 | GAP |
| **NFR-11** Security / privacy (logging, retention, redaction) | all UJs | AD-10 (D42, D45) | §2 `get_audit_page`; §5 I15, I20 | `test_get_audit_page_happy_chronological` (+ read-only invariant); redaction/retention **not tested in ATDD** | 1.5 | PARTIAL |

---

## 3. Scenario (UX) roll-up

| Scenario | UJ | Covered FRs | ATDD coverage | Notes |
|---|---|---|---|---|
| 01 Access Denial Diagnosis | UJ-1 | FR-01, FR-03, FR-04, FR-13 | RED | S1 fixture; `diagnose_access_denial` + citation/explainability tests |
| 02 Night Schedule Inquiry | UJ-2 | FR-01, FR-03, FR-05, FR-13 | RED | S2 fixture; window boundary + null-constraint tests |
| 03 Node Triage Runbook | UJ-3 | FR-01, FR-03, FR-07, FR-08 | RED | S3 fixture; template verbatim + unsourced-physical guard |
| 04 Destructive-Action Safety Guardrail | UJ-4 | FR-01, FR-03, FR-09, FR-10, FR-11 | RED | S4; refusal → dry-run → confirm → executor; zero-mutation checks |
| EC Hallucination prevention (**P0** — R-01) | edge | FR-03, FR-06 | RED | `test_edge_ec_*` (5 tests) + `diagnose_retrospective` zero-event case; the P0 EC is anti-fabrication (FR-03/FR-06) |
| Content data-hygiene (P1 — R-06) | edge | FR-15 | RED | `test_injection_corpus_*` (2 tests); **not P0** per `test-design.md` §1.3 |
| PT Standalone prototype console | all | FR-02, FR-11, FR-12 | PARTIAL | audit/state read covered; retention, redaction, viewer E2E absent |

---

## 4. Architecture-decision (AD-n) roll-up

| AD-n | ATDD tests that go red if you remove the rule | Status |
|---|---|---|
| AD-1 read-only state boundary | `s.store.mutations == []` in `test_answer_query_happy_*`, `test_propose_destructive_action_happy_*`, read-route invariants | RED |
| AD-2 evidence determinism | `*_determinism_across_three_runs`, `*_identical_inputs_identical_positions`, precedence invariants | RED |
| AD-3 propose-only / no execution path | `test_post_re_dispatch_invariant_never_dispatches_directly`, `test_confirm_and_dispatch_happy_exactly_one_executor_call` | RED |
| AD-4 server-side safety state machine | `test_confirm_and_dispatch_precondition_stale_token_is_409`, `test_confirm_and_dispatch_precondition_empty_affected_set_is_409` | RED |
| AD-5 confirmation is procedural | `test_reset_session_invariant_idempotent_and_never_authorizes_destructive`, confirm/dispatch precondition tests | RED |
| AD-6 snapshot re-validation | `test_confirm_and_dispatch_precondition_changed_scope_refuses_with_delta`, `test_confirm_and_dispatch_precondition_stale_token_is_409` | RED |
| AD-7 exact-match resolution | `test_resolve_entities_*`, `test_edge_ec_*` | RED |
| AD-8 structured claims + citation binding | `test_diagnose_access_denial_happy_class_from_evidence`, `test_explainability_*` | RED |
| AD-9 runbook source rule | `test_diagnose_node_triage_invariant_unsourced_physical_template_renders_unavailability`, `test_get_runbook_invariant_*` | RED |
| AD-10 append-only audit + redaction/retention | `test_get_audit_page_*` (append-only/read-only only) | PARTIAL |
| AD-11 content hygiene (data not control) | `test_injection_corpus_query_text_is_data_not_control`, `test_injection_corpus_retrieved_content_is_data_not_control` | RED |
| AD-12 safe failure | `test_assemble_evidence_fault_*`, `test_diagnose_schedule_window_fault_clock_unavailable` | PARTIAL |
| AD-13 no control-plane expansion | `test_browse_state_*`, read-only invariants | PARTIAL |
| AD-14 citation identity & ordering | `test_assemble_evidence_happy_positions_unique_and_monotonic`, `test_get_answer_evidence_invariant_is_ordered_subset_of_stored_set` | RED |
| AD-15 frozen executor contract | `test_executor_post_proposal_*`, `test_executor_get_proposal_*`, `test_confirm_and_dispatch_invariant_applied_count_mismatch_is_never_success` | RED |

---

## 4b. UX-state coverage (state → contract → DTO)

Every state in `planning/ux/EXPERIENCE.md` §State Patterns maps to a wire contract and a DTO in
`planning/detailed-design/schemas/dto.py` / `openapi.yaml`, or is explicitly client-only.

| UX state (`EXPERIENCE.md`) | Wire contract / status | Canonical string | DTO / schema | Story |
|---|---|---|---|---|
| Loading | client-only (no wire payload) | — | — (answer-anatomy skeleton) | 1.2 |
| Empty (first session / empty list) | client-only (no wire payload) | — | — (guided empty state) | 1.2 |
| Valid diagnosis | `POST /api/v1/sessions/{sid}/queries` → 200 | — | `AnswerEnvelopeDTO` · `AnswerDTO` · `DiagnosisClass` | 1.3 |
| Entity Not Found in State | 200 canonical `ENTITY_NOT_FOUND` (query) / 404 `ENTITY_NOT_FOUND` (lookup) | `S_ENF` | `ErrorBody` · `AnswerDTO` | 1.3 · 4.1 |
| Insufficient evidence / Cannot confirm | 200 canonical `CANNOT_CONFIRM` | `S_CNC` | `AnswerDTO` | 1.4 · 3.2 |
| Provider unavailable | 503 `PROVIDER_UNAVAILABLE` | `S_PUA` | `ErrorBody` | 4.2 |
| Malformed / invalid input | 400 `VALIDATION_MALFORMED_BODY` · `VALIDATION_EMPTY_QUERY` · `VALIDATION_QUERY_TOO_LONG`; 200 canonical `CLARIFICATION` · `INTENT_NOT_SUPPORTED` | — | `ErrorBody` · `AnswerDTO` | 1.2 · 4.3 |
| Delegated service / executor failure | 503 `EXECUTOR_UNAVAILABLE` / 502 `EXECUTOR_PARTIAL_APPLY` | — | `ProposalDTO.executor_result` (`ExecutorResultDTO`) | 2.4 |
| Rejected / destructive action | 200 canonical `ACTION_REFUSED` | `S_ARF` | `ProposalDTO` (`state=refused`) | 2.1 |
| Confirmation required | `POST /api/v1/destructive/proposals` → 200 | `S_CAP` | `ConfirmationDTO` (`ProposalDTO.confirmation`) | 2.3 |
| Proposed action | 200 (`dry_run`→`confirmed`→`dispatched`) | — | `ProposalDTO` · `DryRunSnapshotDTO` | 2.2 · 2.4 |
| Successful delegated execution | 200 (`executed`) | — | `ProposalDTO.executor_result` (`source="executor"`) | 2.4 |
| Audit result | `GET /api/v1/sessions/{sid}/audit` → 200 | — | `GetAuditPageResponse` · `AuditRecordDTO` | 1.5 |
| Clock / time source failure | 503 `CLOCK_UNAVAILABLE` | `S_PUA` | `ErrorBody` | 3.1 · 4.2 |
| Empty audit | 200 (`items: []`, `total: 0`) | — | `GetAuditPageResponse` | 1.5 |

**Rule:** every state that is a *response to a request* carries a status + error/canonical code + DTO.
`Loading` and `Empty` are pure client-render states with no wire payload by design.

---

## 5. Gap register

| ID | Requirement | Gap | Recommended action |
|---|---|---|---|
| G-1 | FR-15 / AD-11 / I16 | ~~No injection-corpus test~~ — **closed**: injection corpus added (instruction-like payloads in query text + retrieved records) asserting parity with the clean fixture and 0 destructive triggers. | — |
| G-2 | FR-16 / NFR-7 / AD-12 / I17 | Only 2 of 5 failure classes tested (`PROVIDER_UNAVAILABLE`, `CLOCK_UNAVAILABLE`). Missing: `LLM_UNAVAILABLE`, `EXECUTOR_UNAVAILABLE`, malformed-input no-crash, cold-start recovery. | Write `tests/fault_injection` for the rest. |
| G-3 | FR-11 / NFR-11 / AD-10 / I15, I20 | Append-only is tested, but audit **retention cap / oldest-first rotation** and **secret redaction** have no ATDD test. | Write `tests/retention` and `tests/audit_redaction`. |
| G-4 | NFR-5 / NFR-6 | No latency or concurrency harness (p95/p99, ≥ 5 sessions, ≥ 50 q/h). | Write `tests/latency` + `tests/concurrency`. |
| G-5 | NFR-1 (extension) | Fixture accuracy is tested; the ≥ 90% / 20-query extension corpus is not. | Write `tests/diagnosis_accuracy` extension corpus. |
| G-6 | NFR-10 | Extensibility spike not measurable in ATDD; only the empty-template anchor exists. | Produce `nfr-extensibility-spike.md`. |
| G-7 | AD-13 / I18 | No static route/import audit proving no mutating route outside destructive/executor. | Write `tests/route_audit` + static import check. |
| G-8 | All | ~~Story IDs unbound~~ — **closed**: stories exist in `planning/epics.md` and every FR/NFR row now has a Story ID. | — |

---

## 6. Gate decision

**`gate_status: NOT_EVALUATED`.**

The requirements, AD rules, contract clauses, tests, and stories are all linked. But there is **no
implementation** (`service/` does not exist) and **all 123 tests are red on purpose**, so a
story/release gate has no passing runtime proof. Red tests count as "test present", not "coverage
passed".

| Check | Threshold | Actual | Status |
|---|---|---|---|
| **P0 requirements linked to a story AND a red test** | **100%** | **8/8** — FR-03, FR-06, FR-09, FR-10, FR-13, FR-14, NFR-2, NFR-8 | **MET** |
| P0 test pass rate (story/release gate) | 100% | 0/8 green — all `RED` (no `service/` code yet) | NOT_MET (deferred) |
| Overall FR coverage | — | 16/16 FRs have ATDD tests (`RED`/`PARTIAL`); FR-15 closed (was `GAP`) | — |
| NFR coverage | — | 4/11 `RED`, 3 `PARTIAL`, 4 `GAP` | — |
| Story binding | every FR/NFR → a story | done (G-8 closed) | MET |

P0 *traceability* is satisfied — the gate stays `NOT_EVALUATED` only because P0 *pass-rate* has no
green runtime proof (red ≠ pass).

**Next actions**
1. Close `G-3` (audit retention/redaction, P1) — the only remaining safety/security gap with no test at all.
2. Write `service/` against `test/atdd/module12_interface.py` to turn the red suite green, then re-run `bmad-testarch-trace` for a real gate.
3. Keep `Story ID` in sync if `planning/epics.md` changes (canonical epics for this unit).
