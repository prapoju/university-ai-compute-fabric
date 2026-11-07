# Impl-2 Walkthrough - Module 12: AI Operations Copilot

Work in progress. The sections on delivered stories, test flows and evidence are written as each story closes.

## Annex adaptations

The binding list is the "Annex-to-specification decisions" table in [`docs/impl2-rules.md`](docs/impl2-rules.md).
The shift-left review ([`reviews/review-impl2-shift-left.md`](reviews/review-impl2-shift-left.md)) settled these:

| Annex text | What the build does | Why |
|---|---|---|
| 12.4: "Terminate all active jobs for CS-101" | `CS-101` resolves exactly to the new fixture group `group#CS-101`. Job actions accept a group target. The selector is the group's `running` jobs, giving exactly 3 jobs. group-2, group-4 and S1/S2 are unchanged. | AD-7 allows only exact, case-folded matches, and `course` is not an entity type (log I2-08). |
| 12.4: "…across nodes ws-02, ws-05, ws-08" | The summary names the real node ids `ws-gpu-02`, `ws-gpu-05`, `ws-gpu-08`. | Same "assert the real ids" rule as the load query (OP-I2-2). |
| 12.4: refusal, dry-run summary and token in one reply | `POST /api/v1/copilot/chat` returns all three in one reply and executes nothing. Dispatch happens only through the separate confirm request. `/copilot/query` stays refusal-only. | Log I2-07. |
| 12.5: 50 operators, p95 < 800 ms | A story 1-6 acceptance criterion, measured with the deterministic fake prose adapter on one uvicorn worker. NFR-6 (≥ 5 sessions) and the NFR-5 real-LLM budget are unchanged and reported as a separate lane. | Log I2-09. |

## Delivered stories

- **1.4 (Flow B, foundations):** every claim is checked against its own evidence set before the LLM is called, and an unbound answer
  downgrades to `S_CNC`. `GET /api/v1/answers/{aid}/evidence` and `GET /api/v1/citations/{cid}` resolve every S1/S2 citation,
  `clock#` included. Three fresh-app runs with a frozen clock give identical evidence, citations and class
  (`tests/atdd/test_story_1_4.py`). Contract changes: log I2-13.
