---
stepsCompleted: ['step-01-preflight-and-context', 'step-02-generation-mode', 'step-03-test-strategy', 'step-04-generate-tests', 'step-05-validate-and-complete']
lastStep: 'step-05-validate-and-complete'
lastSaved: '2026-11-07'
storyId: '2.1'
storyKey: '2-1-destructive-intent-classification-and-refusal'
storyFile: '_bmad-output/implementation-artifacts/2-1-destructive-intent-classification-and-refusal.md'
atddChecklistPath: '_bmad-output/test-artifacts/atdd-checklist-2-1-destructive-intent-classification-and-refusal.md'
generatedTestFiles: ['tests/atdd/test_story_2_1.py']
inputDocuments: ['_bmad-output/implementation-artifacts/2-1-destructive-intent-classification-and-refusal.md', 'planning/epics.md', 'test/test-design.md', 'docs/impl2-rules.md', 'test/atdd/module12_contracts.test.py']
---

# ATDD checklist - story 2.1 (destructive-intent classification and refusal)

Murat (`bmad-testarch-atdd`), Flow A of the Impl-2 task statement. Red phase, written before any production code.

## Stack and mode

- Stack: Python backend (FastAPI, pytest). `test_stack_type` in the TEA config says `fullstack`; this story has no browser surface, so only the API level applies and there is no E2E scaffold.
- Mode: AI generation from the story, the contracts and the stub suite. No recording, no subagents (sequential, run by the reviewer).

## Deliberate departures from the skill defaults

- **No `test.skip()` and no `xfail`.** The skill's red-phase convention emits skipped scaffolds and does not run them. The task statement requires an authentic failure recorded before production code, so the cases run and fail on their own assertions. The log is `docs/evidence/impl2/red-2-1.log`.
- Pytest in `tests/atdd/test_story_2_1.py`, not Playwright `*.spec.ts`. The knowledge fragments for Playwright utilities do not apply (`tea_use_playwright_utils: false`).

## Acceptance criteria to cases

| AC | Case | Level | Priority |
|---|---|---|---|
| 1, 10 | `test_a_destructive_request_is_refused_on_every_inbound_route` (3 routes) | API | P0 |
| 2 | `test_every_destructive_verb_is_refused_whatever_its_case` (13) | API | P0 |
| 3 | `test_a_resolvable_target_of_any_kind_is_refused` (6), `test_an_unresolved_target_is_entity_not_found_and_never_a_refusal` (6) | API | P0 |
| 4 | `test_a_verb_on_the_wrong_kind_of_target_is_a_400_and_stores_nothing` (5) | API | P1 |
| 5 | `test_a_fleet_wide_scope_is_refused_without_resolving_an_entity` (6) | API | P0 |
| 6 | `test_a_compound_destructive_query_is_clarified_never_decomposed` (4) | API | P0 |
| 7 | `test_the_refusal_turn_is_recorded_in_the_session_and_audited` | API | P1 |
| 8 | the two concurrency cases, and the `proposals` and `gt-` checks inside every refusal case | API | P0 |
| 9 | `test_injected_confirmation_text_does_not_lift_the_refusal` | API | P0 |
| 10 | `test_copilot_chat_is_declared_in_the_contract_and_served`, `..._rejects_a_body_with_extra_fields`, `..._answer_a_diagnosis_alike` | API | P0 |
| 11 | 4 regression guards (pass today, must not be edited) | API | P1 |
| red proof | `test_terminate_is_a_jobs_verb_so_it_is_refused_on_a_group_and_a_400_on_a_node` | API | P0 |

Out of scope here (plan D-P1): the dry-run summary, the gate token, `POST /destructive/*`. They belong to 2-2 and 2-3.

## Red-phase result (2026-11-07)

`pytest tests/atdd/test_story_2_1.py -q --tb=short`: **51 failed, 4 passed**. The 4 that pass are the regression guards. Every failure is an assertion on missing behaviour: `CLARIFICATION_REQUIRED` instead of `ACTION_REFUSED` (30), `CLARIFICATION_REQUIRED` instead of `ENTITY_NOT_FOUND` (6), `200` instead of `400` (5), a no-intent clarification instead of the compound one (4), `404` for `POST /copilot/chat` (4 cases), the turn intent `clarification` instead of `propose_destructive_action` (1), the concurrent refusals answered as clarifications (1). There is no import error, fixture error or syntax error in the log.

## Handoff

- Next: the user confirms the log, the red commit is made (`tests/atdd/test_story_2_1.py`, `docs/evidence/impl2/red-2-1.log` and this file), then `bmad-dev-story` for Tasks 2 to 5 of the story. The ATDD file must not be edited to get green.
