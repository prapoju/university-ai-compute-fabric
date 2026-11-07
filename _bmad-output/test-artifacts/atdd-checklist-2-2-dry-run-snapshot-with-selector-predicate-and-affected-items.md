---
stepsCompleted: ['step-01-preflight-and-context', 'step-02-generation-mode', 'step-03-test-strategy', 'step-04-generate-tests', 'step-05-validate-and-complete']
lastStep: 'step-05-validate-and-complete'
lastSaved: '2026-11-07'
storyId: '2.2'
storyKey: '2-2-dry-run-snapshot-with-selector-predicate-and-affected-items'
storyFile: '_bmad-output/implementation-artifacts/2-2-dry-run-snapshot-with-selector-predicate-and-affected-items.md'
atddChecklistPath: '_bmad-output/test-artifacts/atdd-checklist-2-2-dry-run-snapshot-with-selector-predicate-and-affected-items.md'
generatedTestFiles: ['tests/atdd/test_story_2_2.py']
inputDocuments: ['_bmad-output/implementation-artifacts/2-2-dry-run-snapshot-with-selector-predicate-and-affected-items.md', 'planning/epics.md', 'test/test-design.md', 'docs/impl2-rules.md', 'test/atdd/module12_contracts.test.py']
---

# ATDD checklist - story 2.2 (dry-run snapshot, selector and affected items)

Murat (`bmad-testarch-atdd`), Flow A of the Impl-2 task statement. Red phase, written before any production code, fixture or contract change.

## Stack and mode

- Stack: Python backend (FastAPI, pytest); only the API level applies, no E2E scaffold. Mode: AI generation from the story, the contracts and the stub suite; sequential, no subagents.
- Same deliberate departures as story 2.1: **no `test.skip()` and no `xfail`** (an authentic failure must be recorded, task statement section 3), and pytest instead of Playwright `*.spec.ts`. One outbound port is doubled in the outage case (`support.faults`, patched before `create_app`).

## Acceptance criteria to cases

| AC | Case | Priority |
|---|---|---|
| 1 | `test_the_annex_scenario_answers_refusal_summary_and_token_in_one_reply` | P0 |
| 3 | `test_the_persisted_row_matches_the_reply_and_its_selector_re_executes` | P0 |
| 16 | `test_the_refusal_turn_and_the_audit_of_a_chat_reply` | P1 |
| 2 | `test_cs_101_resolves_in_any_case` (3); guard for `CS101`, `cs201`, `group 99`, `ws-gpu-99` (4) | P0 |
| 4, 5, 6, 8 | `test_the_dry_run_enumerates_every_item_with_its_own_status` (8 cases: group, job, terminal job, nodes, fault node, empty set, fleet), `test_a_fleet_wide_cordon_lists_every_node_and_skips_the_one_in_fault` | P0 |
| 4 | `test_the_cs_101_jobs_are_running_on_their_nodes` (3), `test_a_job_with_no_node_reports_a_null_node_never_a_made_up_one` | P0 |
| 9 | `test_the_dry_run_route_answers_the_contract_proposal`, `test_a_dry_run_that_cannot_be_built_creates_no_proposal` (6) | P0 |
| 10 | `test_two_dry_runs_on_one_session_are_two_proposals_with_two_tokens`, `test_fifty_concurrent_dry_runs_give_fifty_unique_tokens_and_no_server_error` | P0 |
| 11, 12 | `test_the_real_app_issues_a_different_token_on_every_start`, `test_the_token_lifetime_is_a_setting` | P0 |
| 13 | `test_a_jobs_outage_persists_nothing_and_keeps_the_refusal_turn`, `test_the_dry_run_route_answers_a_jobs_outage_as_a_safe_failure` | P0 |
| 14 | `test_copilot_query_stays_refusal_only` | P0 |
| 15 | 3 regression guards that pass today and must not be edited | P1 |

Out of scope here: confirmation, token expiry enforcement, `CONFIRMATION_STALE`, dispatch and the executor (stories 2-3 and 2-4).

## Red-phase result (2026-11-07)

`pytest tests/atdd/test_story_2_2.py -q --tb=short`: **33 failed, 7 passed**, the same in four consecutive runs. The 7 that pass are the regression guards. Every failure is an assertion on missing behaviour: no `proposal` in a chat reply (15 cases), a state record or a route that answers `404` instead of the contract (the CS-101 group and jobs, `POST /destructive/dry-runs` and its concurrency cases), `503` expected from a jobs outage, `ACTION_REFUSED` expected for `CS-101` on the query route, the `M12_GATE_TOKEN_TTL_SECONDS` setting unknown, the `node` field missing on a job, and `SESSION_NOT_FOUND` expected from a route that answers `404`. There is no import error, fixture error or syntax error in the log.

## Handoff

- Next: the user confirms the log; the red commit holds `tests/atdd/test_story_2_2.py`, `docs/evidence/impl2/red-2-2.log` and this file. Then `bmad-dev-story` for Tasks 2 to 7. The ATDD file must not be edited to get green.
