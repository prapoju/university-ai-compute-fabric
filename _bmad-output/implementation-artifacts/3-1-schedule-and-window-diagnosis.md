---
baseline_commit: 93f67cd24aa10a4e9f0dda18eeb1dd92b669e629
---

# Story 3.1: Schedule and window diagnosis

Status: in-progress

<!-- Annex 12.2 of the Impl-1 task ("Night schedule inquiry"). Scope is deliberately the annex, not
     the full epic: one diagnoser, reusing the 1.3 pipeline, resolver pattern and prose guard. -->

## Story

As Dr. Aris Thorne (through Nadia),
I want to know why my group's fine-tuning job can't run now and when it next can,
so that I can plan the launch instead of retrying blindly.

## Acceptance Criteria

Source: `planning/epics.md` Story 3.1 and Annex 12.2. Requirements: FR-05, AD-2, AD-14, NFR-5.

1. **S2 diagnosis.** Given the clock at `2026-10-16T15:00Z` and the Night window `window#night` (`22:00-06:00`, UTC, half-open `[start, end)`), when Nadia asks `why can't group 4 run their fine-tuning job right now`, the answer (class `schedule_window_restricted`, chain `observation -> evidence -> diagnosis`) states that the job `job#job-8823` is constrained to `night`, that the clock read is outside the window, and the **next open window with explicit date and timezone** (`2026-10-16T22:00:00.000Z` to `2026-10-17T06:00:00.000Z`, UTC). Every claim cites the group, job, window and clock read; evidence positions are `0..n-1`.
2. **No constraint.** A group whose jobs carry no scheduling constraint gets class `schedule_no_constraint` with an explicit "no restriction applies" and **no** window rendered.
3. **Boundary and clock.** The window is half-open: at exactly `22:00:00.000Z` it is open (no restriction now), at `06:00:00.000Z` it is closed. A failed clock read is `CLOCK_UNAVAILABLE` (503), never a fabricated window.
4. **Entity not found.** A group that does not exist returns the canonical `ENTITY_NOT_FOUND` naming it (`group#group-99`), with no diagnosis.
5. **LLM prose only (AD-2).** Same guard as story 1.3: prose once, guarded, one retry, then `LLM_PROSE_REJECTED`; canonical outcomes never call the LLM.
6. **Quality.** At least 10 window variants of the question route to the intent (>= 95%); `pytest` green, `ruff` clean; ports stay read-only and the estate unchanged.

## Tasks / Subtasks

- [x] **Task 1: Domain (pure)** (AC: 1-3) -> `feat(story-3.1): pure window diagnosis and group reference`
  - [x] 1.1 `src/domain/window_diagnosis.py`: `extract_group_reference(query)`; `diagnose_schedule_window(group, jobs, windows, clock)` returning a diagnosis (evidence, claim drafts, fact tokens, class) with the half-open rule; `parse_instant` for comparisons only.
  - [x] 1.2 `src/domain/intent.py`: rule `diagnose_schedule_window` (`RULE-INTENT-SCHEDULE-WINDOW`).
- [ ] **Task 2: Application** (AC: 1-5) -> `feat(story-3.1): window diagnosis through the pipeline`
  - [ ] 2.1 `EntityResolver.resolve_group`; shared `write_prose` helper (guard + one retry) extracted from the 1.3 handler.
  - [ ] 2.2 `src/application/window_diagnosis_handler.py` and registration in `bootstrap.py`.
- [ ] **Task 3: Tests and DoD** (AC: 1-6)
  - [ ] 3.1 Unit tests (domain, handler) and API tests through the real container: S2, boundary, no-constraint, not-found, clock failure, 10 variants.
  - [ ] 3.2 README line, decision-log entry, `ruff`, full `pytest`, sprint-status to `review`.

## Dev Notes

- **D1 - Night window.** The annex and the fixture use `22:00-06:00` UTC; the epics text says `20:00-08:00`. The fixture/annex win (assumption 4 of the decision log).
- **D2 - Constraint to window.** A job's `scheduling_constraint` `night` governs `window#night`; the group's *constrained, not finished* job (status `pending`/`running`) is the one diagnosed. Several: lowest `job_id`.
- **D3 - Group reference.** `group 4`, `Group-4`, `group#group-4` resolve to `group#group-4` (exact after a fixed canonical form, never fuzzy). Anything else is `ENTITY_NOT_FOUND` named as typed.
- **D4 - Reuse.** Same pipeline seam (`AnswerPipeline.register`), `LlmProsePort`, `scan_prose`, canonical strings and the claim-id-after-prose order as story 1.3. No new endpoint, no schema or DTO change.
- **D5 - Next open window.** The fixture holds one window; the next open window is the first window with `end > now` (the current one if `now` is inside it). Past all windows: `CANNOT_CONFIRM`.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5.5 (`claude-sonnet-5-5`)

### Debug Log References

### Completion Notes List

### File List
