## Deferred from: code review of story-1-1 (2026-10-24)

- Q-port-3 audit seam: story 1.5 introduces the audit writer; wrap the ports in the composition root, no adapter edits needed.
- `/readyz` 503 body exposes absolute paths and exception text: acceptable for an internal prototype; trim before any public exposure.
- Non-editable `pip install .` breaks `PROJECT_ROOT` (top-level package named `src`): consequence of the course layout; the README documents the editable install.
- `select` silently truncates at the 10,000-row cap and deep-copies the store per call: fine for 32 nodes; revisit if stores grow.
- Ids ending in a literal backslash before `#` cannot be expressed: no such id exists in the contract vocabulary.
- No dependency lock file: range pins only; packaging policy for the team to decide.
- `select()` selector vocabulary (`method="filter"`) is provisional and cannot take `Selector.params.node_ids` (contracts.md OP-6 / D55): decided with the user to define it in story 2.2, where dry-run selectors are used.

## Deferred from: code review of story-1-2 (2026-10-25)

- `append_turn` refuses answers with claims/evidence (retryable 503): story 1.3 must persist claims/evidence and remove this guard before registering a diagnosis handler.
- Session context (`prior_intents`, `active_answer_ids`) grows per turn: fine for 30-minute prototype sessions; revisit with the retention decision (OQ-13).
- Id counters are seeded once and only for `session`/`answer`, assuming a single process: extend `highest_counters` when other id kinds are first persisted.
- All `sqlite3.Error` become a retryable 503, including permanent faults: the catalog has no code for them; revisit with the audit stories.
- `isolation_level` of the shared connection is not pinned explicitly: the default is what the store relies on; covered by the atomicity tests.
