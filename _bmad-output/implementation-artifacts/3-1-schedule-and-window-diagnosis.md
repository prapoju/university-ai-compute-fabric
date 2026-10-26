---
baseline_commit: 93f67cd24aa10a4e9f0dda18eeb1dd92b669e629
---

# Story 3.1: Schedule and window diagnosis

Status: review

<!-- Annex 12.2 of the Impl-1 task ("Night schedule inquiry"). Scope is deliberately the annex, not
     the full epic: one diagnoser, reusing the 1.3 pipeline, resolver pattern and prose guard. -->

## Story

As Dr. Aris Thorne (through Nadia),
I want to know why my group's fine-tuning job can't run now and when it next can,
so that I can plan the launch instead of retrying blindly.

## Acceptance Criteria

Source: `planning/epics.md` Story 3.1 and Annex 12.2. Requirements: FR-05, AD-2, AD-14, NFR-5.

1. **S2 diagnosis.** Given the clock at `2026-10-16T15:00Z` and the Night window `window#night` (`22:00-06:00`, UTC, half-open `[start, end)`), when Nadia asks `why can't group 4 run their fine-tuning job right now`, the answer (class `schedule_window_restricted`, chain `observation -> evidence -> diagnosis -> recommendation`) states that the job `job#job-8823` is constrained to `night`, that the clock read is outside the window, and the **next open window with explicit date and timezone** (`2026-10-16T22:00:00.000Z` to `2026-10-17T06:00:00.000Z`, UTC), which it also returns as `recommendation.next_open_window = {start, end, timezone}` (contracts.md `diagnose_schedule_window` Q1; `planning/ux/EXPERIENCE.md` S2: "recommendation = next window"; amended by the audit, AD-28). Every claim cites the group, job, window and clock read; evidence positions are `0..n-1`.
2. **No constraint.** A group whose jobs carry no scheduling constraint gets class `schedule_no_constraint` with an explicit "no restriction applies" and **no** window rendered.
3. **Boundary and clock.** The window is half-open: at exactly `22:00:00.000Z` it is open (no restriction now), at `06:00:00.000Z` it is closed. Past the only recorded window the answer is `schedule_window_restricted` with `next_open_window: null` and says that no later window is on record; a constraint whose window is not on record is `schedule_no_constraint` with no window (contracts.md `diagnose_schedule_window` Q1, D55; amended by the audit, AD-29). A failed clock read is `CLOCK_UNAVAILABLE` (503), never a fabricated window.
4. **Entity not found.** A group that does not exist returns the canonical `ENTITY_NOT_FOUND` naming it (`group#group-99`), with no diagnosis.
5. **LLM prose only (AD-2).** Same guard as story 1.3: prose once, guarded, one retry, then `LLM_PROSE_REJECTED`; canonical outcomes never call the LLM.
6. **Quality.** At least 10 window variants of the question route to the intent (>= 95%); `pytest` green, `ruff` clean; ports stay read-only and the estate unchanged.

## Tasks / Subtasks

- [x] **Task 1: Domain (pure)** (AC: 1-3) -> `feat(story-3.1): pure window diagnosis and group reference`
  - [x] 1.1 `src/domain/window_diagnosis.py`: `extract_group_reference(query)`; `diagnose_schedule_window(group, jobs, windows, clock)` returning a diagnosis (evidence, claim drafts, fact tokens, class) with the half-open rule; `parse_instant` for comparisons only.
  - [x] 1.2 `src/domain/intent.py`: rule `diagnose_schedule_window` (`RULE-INTENT-SCHEDULE-WINDOW`).
- [x] **Task 2: Application** (AC: 1-5) -> `feat(story-3.1): window diagnosis through the pipeline`
  - [x] 2.1 `EntityResolver.resolve_group`; shared `write_prose` helper (guard + one retry) extracted from the 1.3 handler.
  - [x] 2.2 `src/application/window_diagnosis_handler.py` and registration in `bootstrap.py`.
- [x] **Task 3: Tests and DoD** (AC: 1-6)
  - [x] 3.1 Unit tests (domain, handler) and API tests through the real container: S2, boundary, no-constraint, not-found, clock failure, 10 variants.
  - [x] 3.2 README line, decision-log entry, `ruff`, full `pytest`, sprint-status to `review`.

## Dev Notes

- **D1 - Night window.** The annex and the fixture use `22:00-06:00` UTC; the epics text said `20:00-08:00`. The fixture/annex win (assumption 4 of the decision log); the epic AC was aligned by the audit (AD-30).
- **D2 - Constraint to window.** A job's `scheduling_constraint` `night` governs `window#night`; the group's *constrained, not finished* job (status `pending`/`running`) is the one diagnosed. Several: lowest `job_id`.
- **D3 - Group reference.** `group 4`, `Group-4`, `group#group-4` resolve to `group#group-4` (exact after a fixed canonical form, never fuzzy). Anything else is `ENTITY_NOT_FOUND` named as typed.
- **D4 - Reuse.** Same pipeline seam (`AnswerPipeline.register`), `LlmProsePort`, `scan_prose`, canonical strings and the claim-id-after-prose order as story 1.3. No new endpoint, no schema or DTO change.
- **D5 - Next open window.** The fixture holds one window; the next open window is the first window with `start > now` (contracts.md Q1). Inside the window nothing is restricted and none is recommended. ~~Past all windows: `CANNOT_CONFIRM`.~~ Superseded by the audit (AD-29): `CANNOT_CONFIRM` contradicted contracts.md Q1 (D55), which asks for `next_open_window: null` plus an explicit no-future-window state, and `schedule_no_constraint` for an empty window set.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5.5 (`claude-sonnet-5-5`)

### Debug Log References

- Adding the schedule rule to the intent registry broke two story-1.2 tests (registry contents; the extension test reused the same intent code and now matched twice). Fixed in the tests, not in the router.
- My "no constraint" test assumed group-2 had no constrained job; the fixture has `job-8824` (pending, `night`). Switched to group-7.

### Completion Notes List

- Pure domain `src/domain/window_diagnosis.py` (group extraction, half-open window rule, claims, fact tokens) and the `diagnose_schedule_window` intent rule; application `EntityResolver.resolve_group`, `WindowDiagnosisHandler`, shared `turn_support.py` (guarded prose, claim ids, canonical turns) extracted from the 1.3 handler; registered in `bootstrap.py`. No endpoint, schema or DTO change.
- AC1 S2 diagnosis with next open window + timezone, every claim citing group/job/window/clock; AC2 no-constraint; AC3 half-open boundary and `CLOCK_UNAVAILABLE` 503 (nothing stored); AC4 `ENTITY_NOT_FOUND group#group-99`; AC5 prose once, guarded; AC6 10 phrasings route and diagnose identically.
- Tests: 65 new (domain, handler, API through the real container); suite 916 passing, 0 skipped; `ruff` clean. Scope kept to the annex on purpose (decision log AD-23); no subagent review was run, so the story stops at `review`.

### File List

New: `src/domain/window_diagnosis.py`, `src/application/window_diagnosis_handler.py`, `src/application/turn_support.py`, `tests/unit/test_window_diagnosis.py`, `tests/unit/test_window_diagnosis_handler.py`, `tests/api/test_window_diagnosis_api.py`.

Modified: `src/domain/intent.py`, `src/domain/diagnosis.py`, `src/domain/references.py`, `src/domain/canonical_strings.py`, `src/application/entity_resolver.py`, `src/application/access_denial_handler.py`, `src/bootstrap.py`, `tests/unit/test_intent.py`, `README.md`, `docs/ai-decision-log.md`, both `sprint-status.yaml` copies.

### Change Log

- 2026-10-25: story 3.1 implemented (Tasks 1-3); status -> review.
- 2026-10-26: audit fix (AD-28): AC1 had dropped the contract's `recommendation.next_open_window` and the UX's `recommendation` stage; both are returned now.
- 2026-10-26: audit fix (AD-29): past the only window and with no window on record the answer follows contracts.md Q1 (D55) instead of `CANNOT_CONFIRM` (AC3, D5).
