---
stepsCompleted: ['step-01-preflight-and-context', 'step-02-generation-mode', 'step-03-test-strategy', 'step-04-generate-tests', 'step-05-validate-and-complete']
lastStep: 'step-05-validate-and-complete'
lastSaved: '2026-11-08'
storyId: '2.4'
storyKey: '2-4-propose-only-handoff-simulated-executor-and-executor-failure-safety'
storyFile: '_bmad-output/implementation-artifacts/2-4-propose-only-handoff-simulated-executor-and-executor-failure-safety.md'
generatedTestFiles: ['tests/atdd/test_story_2_4.py']
inputDocuments: ['_bmad-output/implementation-artifacts/2-4-propose-only-handoff-simulated-executor-and-executor-failure-safety.md', 'planning/epics.md', 'test/test-design.md', 'planning/detailed-design/contracts.md', 'docs/impl2-rules.md']
---

# ATDD checklist - story 2.4 (executor, dispatch and executor-failure safety)

Murat (`bmad-testarch-atdd`), Flow A. Red phase, written before any production code, port, adapter or contract change. D1, D2, D5, D7 and D9 were confirmed by the user on 2026-11-08.

## Stack and mode

- Python backend (FastAPI, pytest), API level only; no `skip`, no `xfail`. The simulated executor is reached lazily through `ExecutorPort` (a missing port is a failed case, not a collection error); its controls are `down`, `delay_seconds`, `apply_only`, `extra_applied`, `calls` and `requests`. Other doubles at outbound ports: a switch on `SimJobs.select` and a `SqliteAuditStore.append` that fails on its Nth call. Time is the real `SimClock`; nothing sleeps.

## Acceptance criteria to cases

| AC | Case | Priority |
|---|---|---|
| 1, 4 | `test_the_annex_runs_to_executed_and_only_the_three_jobs_change`, `test_the_session_audit_tells_the_copilots_rows_from_the_executors`, `test_the_executor_takes_its_own_clock_read_for_its_timestamp` | P0 |
| 2 | `test_a_provider_port_cannot_write`, guard `test_regression_guard_a_dry_run_and_a_stale_confirm_change_nothing` | P0 |
| 3 | `test_simultaneous_confirms_call_the_executor_once` (2, 50), `test_a_sequential_replay_answers_the_persisted_proposal_and_adds_no_call` | P0 |
| 5 | `test_the_dispatcher_forwards_exactly_the_frozen_request`, `test_a_malformed_executor_request_is_400_and_applies_nothing` (3) | P0 |
| 6 | `test_an_item_that_is_no_longer_running_is_skipped_and_the_result_is_partial` | P0 |
| 7 | `test_an_executor_that_is_down_fails_the_proposal_safely_and_is_never_retried` | P0 |
| 8 | `test_the_executor_has_five_seconds_on_the_clock` (4.999, 5.000, 5.001 s), `test_a_late_result_is_kept_by_the_executor_and_never_applied_twice` | P0 |
| 9 | `test_a_partial_apply_is_failed_and_the_502_body_is_the_proposal`, `test_a_result_larger_than_the_scope_is_never_executed` | P0 |
| 10, 11 | `test_the_executor_refuses_a_proposal_that_was_not_confirmed`, `test_the_executor_checks_the_token_and_the_proposal`, `test_an_identical_executor_request_returns_the_stored_result_and_a_differing_one_conflicts` | P0 |
| 12 | `test_get_proposal_answers_the_persisted_proposal_in_every_state`, `test_the_read_routes_answer_404_for_an_unknown_proposal` | P0 |
| 13 | `test_a_failed_proposal_is_re_dispatched_as_a_new_proposal_through_the_gate`, `test_a_partly_applied_parent_is_not_superseded`, `test_only_a_failed_parent_can_be_re_dispatched` (3), `test_re_dispatch_of_an_unknown_or_empty_parent_is_refused` | P0 |
| 14 | `test_a_failing_audit_write_while_recording_the_result_leaves_the_proposal_dispatched` | P0 |
| 15 | `test_every_contract_operation_but_the_runbook_is_served`, guard `test_regression_guard_no_mutating_route_outside_the_two_prefixes` | P0 |
| 16 | guards `test_regression_guard_the_chat_reply_and_the_query_route_keep_their_shape`, `test_regression_guard_a_wrong_token_is_still_403` | P1 |

The 2.3 cases that now read `executed` are adapted in the task that wires the dispatcher (D1), not here.

## Red-phase result (2026-11-08)

`pytest tests/atdd/test_story_2_4.py -q --tb=short`: **32 failed, 4 passed**, the same in four consecutive runs. The 4 that pass are the regression guards. Every failure is missing behaviour: `ExecutorPort` does not exist (14 cases, a deliberate `pytest.fail` without the chained import error), the new routes answer `404`, and the confirm still answers `confirmed` where `executed` is expected. No import error, fixture error or syntax error is in the log.

## Handoff

- The user waived the review of the red log and asked for the commit without showing it (2026-11-08); the red commit holds the ATDD file, `docs/evidence/impl2/red-2-4.log` and this file. Then `bmad-dev-story` for Tasks 2 to 6. The ATDD file must not be edited to get green.
