---
stepsCompleted: ['step-01-preflight-and-context', 'step-02-generation-mode', 'step-03-test-strategy', 'step-04-generate-tests', 'step-05-validate-and-complete']
lastStep: 'step-05-validate-and-complete'
lastSaved: '2026-11-08'
storyId: '2.3'
storyKey: '2-3-procedural-confirmation-gate-and-snapshot-re-validation'
storyFile: '_bmad-output/implementation-artifacts/2-3-procedural-confirmation-gate-and-snapshot-re-validation.md'
atddChecklistPath: '_bmad-output/test-artifacts/atdd-checklist-2-3-procedural-confirmation-gate-and-snapshot-re-validation.md'
generatedTestFiles: ['tests/atdd/test_story_2_3.py']
inputDocuments: ['_bmad-output/implementation-artifacts/2-3-procedural-confirmation-gate-and-snapshot-re-validation.md', 'planning/epics.md', 'test/test-design.md', 'planning/detailed-design/contracts.md', 'docs/impl2-rules.md', 'test/atdd/module12_contracts.test.py']
---

# ATDD checklist - story 2.3 (confirmation gate and snapshot re-validation)

Murat (`bmad-testarch-atdd`), Flow A of the Impl-2 task statement. Red phase, written before any production code, port method, route or contract change.

## Stack and mode

- Stack: Python backend (FastAPI, pytest); only the API level applies, no E2E scaffold. Mode: AI generation from the story, the contracts and the stub suite; sequential, no subagents.
- Same deliberate departures as stories 2.1 and 2.2: **no `test.skip()` and no `xfail`** (an authentic failure must be recorded, task statement section 3), and pytest instead of Playwright `*.spec.ts`.
- Two outbound doubles, both installed before `create_app` (`audited()` binds the method at build time): a switch on `SimJobs.select` (counts calls, outages, and changes what it answers, because the estate has no write path) and a `PortFault` on `SqliteAuditStore.append`. The clock is the real `SimClock`, moved with `advance`; no sleeps; concurrency ordered with `threading.Barrier`.
- "Exec = 1" of the test design reads here as one `dry_run -> confirmed` transition and one set of audit rows (there is no executor until 2-4).

## Acceptance criteria to cases

| AC | Case | Priority |
|---|---|---|
| 1 | `test_the_annex_dry_run_then_a_distinct_confirm_answers_a_confirmed_proposal` | P0 |
| 2 | `test_a_confirm_body_with_an_identity_claim_is_malformed_and_changes_nothing` (5), `test_a_session_reset_between_the_dry_run_and_the_confirm_changes_nothing`, `test_the_confirmation_records_no_identity_of_its_own` | P0 |
| 3 | `test_the_token_is_accepted_up_to_sixty_seconds_and_not_after` (+59.999, +60.000, +60.001 s), `test_the_token_lifetime_is_the_setting_in_force` (5 s) | P0 |
| 4 | `test_an_identical_replay_answers_the_persisted_proposal_and_changes_nothing`, `test_an_identical_replay_after_the_token_lifetime_still_answers_the_persisted_proposal` | P0 |
| 5 | `test_an_unknown_proposal_is_not_found`, `test_a_wrong_token_is_forbidden_...`, `test_another_proposals_token_is_forbidden`, `test_a_different_token_on_a_confirmed_proposal_is_a_conflict`, `test_a_malformed_token_is_a_malformed_body` (5), `test_a_proposal_in_the_refused_state_cannot_be_confirmed` | P0 |
| 6 | `test_a_set_with_nothing_actionable_is_refused_without_a_provider_read` (empty, cancelled job, succeeded job, node in fault) | P0 |
| 7 | `test_a_job_that_left_the_set_and_a_new_one_that_joined_it_...`, `test_a_status_that_changed_...`, `test_a_removed_item_...`, `test_an_unchanged_set_is_confirmed_after_the_selector_is_re_executed` | P0 |
| 8 | `test_a_jobs_outage_during_revalidation_is_a_safe_failure_and_recovery_works` | P0 |
| 9 | `test_simultaneous_identical_confirms_make_exactly_one_transition` (2, 50), `test_an_identical_confirm_raced_with_one_that_has_another_token_...`, `test_a_confirm_that_goes_first_wins_and_a_state_change_that_goes_first_...` | P0 |
| 10 | `test_a_failing_audit_write_leaves_the_proposal_in_dry_run` | P0 |
| 11 | `test_the_audit_after_a_confirm_has_the_head_and_the_revalidation_read`, `test_a_replay_and_a_rejection_add_no_audit_row` | P1 |
| 12 | `test_annex_12_4_end_to_end_up_to_confirmed` | P0 |
| 13 | 3 regression guards that pass today and must not be edited | P1 |

Out of scope here: the executor, dispatch, `get_proposal`, re-dispatch and `EXECUTOR_*` codes (story 2-4).

## Red-phase result (2026-11-08)

`pytest tests/atdd/test_story_2_3.py -q --tb=short`: **42 failed, 3 passed**, the same in four consecutive runs. The 3 that pass are the regression guards. Every failure is an assertion on missing behaviour: `POST /api/v1/destructive/proposals` answers `404` where `200`, `400`, `403`, `409` or `503` is expected (the route is declared and not served). There is no import error, fixture error or syntax error in the log.

One case was corrected before the official run: `test_a_replay_and_a_rejection_add_no_audit_row` passed on the first run only because a `404` also writes no audit row, so it could not fail; it now asserts the first confirm (200), the head and re-validation rows, the replay (200) and the conflict (409) before comparing the audit, and fails with the others. A tautology (a stored value compared with a second read of the same row) was replaced by a comparison with the value read before the confirm.

## Handoff

- Next: the user confirms the log; the red commit holds `tests/atdd/test_story_2_3.py`, `docs/evidence/impl2/red-2-3.log` and this file. Then `bmad-dev-story` for Tasks 2 to 6. The ATDD file must not be edited to get green.
