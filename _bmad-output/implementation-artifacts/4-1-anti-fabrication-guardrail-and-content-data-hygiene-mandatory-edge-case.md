---
baseline_commit: 24154f5
---

# Story 4.1: Anti-fabrication guardrail and content data-hygiene (Mandatory Edge Case)

Status: review

<!-- Annex 12.3 of the Impl-1 task. Scope is the annex plus the epic's explicit corpora; the resolver,
     canonical strings and ENTITY_NOT_FOUND turn shape already exist from story 1.3 and 3.1. -->

## Story

As Nadia,
I want a clean "Entity Not Found in State" whenever a referenced person, policy, model or group does not exist, and retrieved content to never steer the Copilot,
so that I never relay a plausible but invented operational narrative.

## Acceptance Criteria

Source: `planning/epics.md` Story 4.1 and Annex 12.3. Requirements: FR-03, FR-15, NFR-2, AD-7, AD-11.

1. **Imaginary entity.** A reference to a user, model, group or `policy#...` that is not in state returns the literal `Entity Not Found in State: {ref_list}.` naming every unresolved reference (user, model, then policy), with no claims, evidence, diagnosis class, recommendation or proposal (0 fabricated detail). The diagnosis never proceeds.
2. **Corpus.** On at least 10 non-existent references (prefixes, typos, truncations, wrong types, groups, policies) 100% return `ENTITY_NOT_FOUND`; the fabricated-entity rate is 0.
3. **Content is data.** An instruction-like payload embedded in retrieved records (user display name, clause text, event reason, group name) yields the same diagnosis class, answer chain, evidence ids, claim count and recommendation as the clean fixtures (none for S1, the recorded next window for S2: the payload adds none), no proposal, and leaves the estate unchanged. The same payload in the query text does not change the diagnosis; a destructive instruction is refused by the router before any handler runs.
4. **Quality.** At least 2 tests per criterion; `pytest` green and `ruff` clean.

## Tasks / Subtasks

- [x] **Task 1: Guardrail** (AC: 1-3) -> `feat(story-4.1): anti-fabrication guardrail and content hygiene`
  - [x] 1.1 `extract_policy_references` (domain) and `EvidenceAssembler.missing_policies`; the access-denial handler names missing policies after the user and model and answers `ENTITY_NOT_FOUND`.
  - [x] 1.2 Prose-guard vocabulary: only capitalised words of a display name become fact tokens, so an injected name cannot make the prose unusable.
- [x] **Task 2: Tests and DoD** (AC: 1-4) -> `test(story-4.1): corpus, injection parity and API`
  - [x] 2.1 Unit corpus (12 imaginary references), policy extraction, injection parity on records and query, display-name payload; API tests through the real container.
  - [x] 2.2 README line, decision log, `ruff`, full `pytest`, sprint-status to `review`.

## Dev Notes

- **D1 - Message.** The annex quotes `User ghost_user_99 does not exist in cluster records`; the contract literal `S_ENF` (`Entity Not Found in State: {ref_list}.`) is what `contracts.md`, the epics and the error catalog define and what story 1.3 already returns, so the canonical string is kept and the `ENTITY_NOT_FOUND` code satisfies the annex.
- **D2 - What a policy reference is.** Only a typed `policy#...` token in the query. Events have no `get` in the port, so a typed event reference is out of scope.
- **D3 - Injection.** Nothing in the system executes retrieved text: the diagnosis is deterministic code, the LLM sees evidence as data and only writes guarded prose, and destructive wording in a query is refused by the router (story 1.2). This story proves it with a corpus instead of adding a second filter.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5.5 (`claude-sonnet-5-5`)

### Debug Log References

- The tests were written first, but this story file was written after the implementation (the scope decision of AD-23 compressed the ceremony); the order is recorded in the decision log.
- A `printf`-built regex lost its `\b` and left a raw backspace character in `references.py`; the policy extraction tests were red until the byte was replaced (AD-25).
- The "destructive instruction" test first called a handler; the router refuses it earlier (`Clarify`), so the test now asserts that.

### Completion Notes List

- 12 imaginary references (user, model, policy, group; prefixes, typos, wrong types) all return `ENTITY_NOT_FOUND`; claims, evidence, diagnosis class, recommendation and proposal stay empty; a real policy reference does not block the diagnosis.
- Records poisoned in four fields give the same class, chain, evidence ids and claim count for S1 and S2, no recommendation/proposal, estate unchanged.
- Suite: 947 passing, 0 skipped; `ruff` clean. No subagent review was run, so the story stops at `review`.

### File List

New: `tests/unit/test_anti_fabrication.py`, `tests/api/test_anti_fabrication_api.py`.

Modified: `src/domain/references.py`, `src/domain/diagnosis.py`, `src/application/evidence_assembler.py`, `src/application/access_denial_handler.py`, `README.md`, `docs/ai-decision-log.md`, both `sprint-status.yaml` copies.

### Change Log

- 2026-10-25: story 4.1 implemented; status -> review.
- 2026-10-26: AC3 reworded with the audit fix AD-28: S2 now carries the contract's next-window recommendation, so "no recommendation" means "none added by the payload" (the tests compare with the clean answer).
