# Automation Summary: Flow C branch-coverage gap analysis

Date: 2026-11-07 · Workflow: bmad-testarch-automate (Create) · Rules: docs/impl2-rules.md

## Coverage (pytest tests --cov=src --cov-branch)

| Scope | Before | After |
|---|---|---|
| src/application/evidence_assembler.py | 94% (miss 42) | 100% |
| src/application/entity_resolver.py | 92% (miss 123, 142, 153, 160, 162, 164, 184) | 100% |
| src/application/window_diagnosis_handler.py | 92% (miss 70, 73, 81) | 100% |
| src/application/session_service.py | 95% (miss 77, 122, 149, 174) | 96% (miss 77, 122, 174) |
| src total | 96% (72 stmts, 45 partial branches missed) | 97% (96.63%; 60 stmts, 33 partial branches missed) |
| Tests | 1011 passed | 1025 passed |

The task brief quoted 83% and 91%. Those figures predate the uncommitted story 4-1 edit that moved
`missing_policies` from EvidenceAssembler to EntityResolver. The "before" column was measured on
the working tree as found.

## Root-cause finding

The estate loads all or nothing (`SimProviders.from_fixtures`). Deleting one fixture file fails
**every** port. Two existing tests looked like they covered a specific port outage but never
reached it:

- `test_follow_up_provider_failures_propagate` deletes catalog.json, but the users lookup fails
  first. The "catalog down while users answer" and "outage during D35 context re-resolution"
  paths had never run.
- `test_a_failed_estate_aborts_before_any_prose` deletes windows.json, but the group lookup fails
  first. The jobs and windows failure branches of the window diagnosis had never run.

The new tests wrap the real ports (real fixture records) and fail one port for chosen ids: an
entity key, a `group_id` or an id kind. `windows.list()` takes no id, so that port fails as a
whole. The session-save test uses the real SQLite store and aborts its last statement with a
TEMP trigger.

## Test count

Round 1 added 7 cases (1011 → 1018). Round 2 added 6 (1018 → 1024). The audit deleted 1
(P2) and added 2 (P4), giving **14 new cases** and 1025 tests. One older test was strengthened
(P1, `:125`). An earlier version of this summary claimed 14 cases when there were 13 (P6).

## Tests added or changed

tests/unit/test_entity_resolver.py
- `test_a_context_entity_is_re_resolved_against_the_provider_before_use`: *pre-existing, strengthened (P1)*. An older model that still resolves sits in the context and must not stand in for the stale one.
- `test_a_model_follow_up_without_a_user_in_the_session_cannot_proceed`: MissingContext.
- `test_a_context_user_removed_since_is_named_not_silently_replaced`: D35. An older resolvable user sits in the context (P1).
- `test_a_catalog_outage_after_the_user_resolved_is_never_a_model_not_found`: AD-12.
- `test_a_catalog_outage_on_the_follow_up_ref_aborts_the_turn`: AD-12.
- `test_an_outage_while_re_resolving_the_session_entity_is_not_a_miss` (2 params): AD-12 + D35.

tests/unit/test_evidence_assembler.py
- `test_a_policy_outage_aborts_before_any_event_is_read`: AD-12. Asserts the exact injected failure (P3) and that the event store is never queried.

tests/unit/test_window_diagnosis_handler.py
- `test_a_jobs_outage_for_the_group_aborts_before_windows_or_prose`: AD-12.
- `test_a_windows_outage_is_never_read_as_no_window_on_record`: AD-12 / D55.
- `test_a_claim_id_failure_fails_the_turn_instead_of_an_answer_without_claims`: OP-13.
- `test_a_failed_prose_step_draws_no_claim_id` (2 params: LLM unavailable, prose rejected twice): FR-14, no id is burned on an LLM failure (P4).
- *Deleted:* `test_a_jobs_outage_for_one_group_leaves_other_groups_answerable`. It tested the fake, not production code (P2).

tests/unit/test_session_service.py
- `test_an_answer_that_could_not_be_saved_is_never_returned` (memory + file SQLite): a real SQLite abort on append_turn's last statement returns PROVIDER_UNAVAILABLE and leaves no answer row, no turn and an empty context. A second session saves exactly the returned answer id (P5).

## Mutation check (each mutant applied alone; src restored byte-for-byte, git diff unchanged)

| Mutant | Caught by |
|---|---|
| Main guard `_is_miss`: every failure treated as "not found" | 7 tests (5 new cases, 2 existing) |
| Context re-resolution outage reported as Unresolved | 2 resolver cases |
| Catalog outage in resolve_user_and_model reported as not found | 1 resolver test |
| Follow-up ignores a catalog outage on the ref (line 142) | 1 resolver test |
| Model follow-up with no user in context → Unresolved (line 160) | 1 resolver test |
| Stale context user → MissingContext (line 164) | 1 resolver test |
| Stale newest entity silently replaced by an older one that resolves | **survived before P1**; now 2 tests |
| Events queried before the clause failure check | assembler test |
| Jobs outage read as "the group has no jobs" | jobs-outage test |
| Windows outage read as "no window on record" | windows-outage test |
| Claim-id failure ships an answer with no claims | claim-id test |
| Claim ids minted before the prose step | 3 cases (P4 test ×2 + claim-id test) |
| Failed append_turn ignored, answer returned anyway | session-save test (both DB modes) |
| Store skips its rollback after a failed statement | session-save test (both DB modes) |

## Audit against the four testing traps

- Ice Cream Cone: none. All new cases are unit tests on the application layer.
- Flaky Sleeper: none. No sleep, real clock or timer in any new test.
- Mocking Mirage: none. Every test runs the real unit with real fixtures and fakes only a port.
  Caveat: the sim estate cannot produce a single-port outage, so those scenarios come from the
  port contract (AD-12).
- Blindly Green: two cases found and fixed. P1 was a silent-replacement mutant that survived.
  P5's "nothing saved" assertions could not fail, because the earlier fake failed before
  touching the database.

## Remaining gaps, triaged (not addressed)

| Location | What | Verdict |
|---|---|---|
| session_service.py:77, 122, 174 | idgen (session / answer) and list_turns failure propagation | Real but low risk. One parametrised test would cover them. |
| access_denial_handler.py:101 | follow-up rule matched but no reference extracted | Real. Check reachability from the intent classifier first. |
| dependency_check.py:76-87 | CLI main() output and exit codes | Glue code. Skip unless the exit codes are a contract. |
| dto.py, bootstrap.py, adapters | defensive / wiring branches | Mostly number-chasing. Skip. |
