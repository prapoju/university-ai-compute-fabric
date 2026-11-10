# Impl-2 standing rules (Module 12, AI Operations Copilot)

The task statement is docs/task-impl2.md. The Annex allows groups to adapt its stories
to their own specifications. Every adaptation below is deliberate, so record it in the
walkthrough and do not re-litigate it.

## Story map
| Annex | Stories | Flow |
|---|---|---|
| 12.1 | 1-3 (scaffold 1-1, 1-2) | done |
| 12.2 | 3-1 | C |
| 12.3 | 4-1 | C |
| foundations | 1-4, 1-5, 4-2 | B |
| 12.4 | 2-1, 2-2, 2-3, 2-4 | A |
| 12.5 | 1-6 | D |
| 12.6 | 3-3 (B), 1-7 (E) | B + E |

## Annex-to-specification decisions
| Topic | Annex says | Repo specification | Decision |
|---|---|---|---|
| Destructive inbound | POST /api/v1/copilot/chat | /copilot/query, /sessions/{sid}/queries, /destructive/* | Add /copilot/chat as a thin route over the same use cases and add it to openapi.yaml (precedent: log entry AD-26). Keep /destructive/*. |
| Token lifetime | valid for 60 seconds | contracts.md confirm_and_dispatch P2: 15 min | Change to 60 s in contracts.md, configurable. Test expiry with the fake clock. |
| Single-use token | single-use | P5: identical confirm is idempotent | A replay returns the persisted proposal and never dispatches again. A differing confirm is rejected. |
| Cryptographic token | cryptographic | GateToken ^gt-[0-9a-f]{32}$, ids through idgen_port (R2) | Production adapter uses secrets.token_hex(16). Tests use the deterministic adapter. |
| "Terminate" verb | Terminate all active jobs for CS-101 | ActionVerb is closed: delete_jobs, cancel_jobs, cordon_node, drain_node | Map terminate to cancel_jobs. The enum stays closed. |
| Active CS-101 jobs | 3 jobs on ws-02, ws-05, ws-08 | Fixtures have no running CS101 jobs, and jobs have no node field | Add 3 running CS101 jobs and a nullable node field on ws-gpu-02, -05, -08 under a NEW group. Do not change group-4 or the S1/S2 scenarios. |
| Destructive target "CS-101" | Terminate all active jobs for CS-101 | AD-7 exact match; course is not an entity type; P3 job actions need a job target | The new group's id is `group#CS-101`. contracts P3 accepts a group target for job actions, selector `jobs_port.select({group_id, status: running})`. "Active" means running. Exactly 3 jobs (ws-gpu-02, -05, -08). group-2, group-4 and S1/S2 unchanged. |
| Load budget | 50 concurrent operators, p95 < 800 ms | NFR-6: ≥ 5 sessions; NFR-5: p95 ≤ 3 s with the real LLM | NFR-6 unchanged. The 50-operator p95 < 800 ms budget, measured with the fake prose adapter, is an acceptance criterion of story 1-6 only. |
| Load-test query | Why was job #402 denied... citing PR-04, CE-12 | No job-402. Real ids are RULE-CAT-04, policy#catalog.4.2, catalog entry deepseek-coder | Use "Why was student Alex denied access to model deepseek-coder?" and assert the real ids. |
| Console citation | Rule PR-12 | RULE-CAT-04 | Render "Verified via Policy Engine [RULE-CAT-04]". |
| Streaming output | response stream renders | Architecture: synchronous HTTP, no push | No SSE. Render when the response arrives, with a pending state. |
| Access-denial runbook | diagnose and provide runbook | Registry keyed by error code, holds only ERR_THERMAL_88 | Add a non-physical template as registry config only (NFR-10), rendered verbatim (AD-9). |
| Invariant numbers | AD-30 etc. | Architecture uses AD-1..AD-15; the decision log also uses AD-NN | Write "Annex AD-30" for Annex ids. Impl-2 log entries use I2-NN. |

## Code rules
- epics.md lists `service/...` paths. The real layout is `src/{domain,ports,application,adapters}` (log entry AD-03). Use `src/`.
- Follow planning/detailed-design/contracts.md and schemas/. If you must change a contract, change the document in the same commit.
- Pure rules go in src/domain. The domain, ports and application rings import no adapter or framework. Time comes only from the Clock port. Ids come only from idgen_port.
- The route audit requires registered routes to equal openapi.yaml. Update both together.
- The LLM never states a fact (AD-2, AD-8).

## Test rules
- No time.sleep, asyncio.sleep, setTimeout-based waits or waitForTimeout anywhere in src, tests or console. Use the fake clock, barriers, or web-first assertions.
- Never mock the unit under test. Assert on resulting state and on what did not happen.
- New ATDD suites go in tests/atdd/test_story_<id>.py and call the real app. Use the stub suite in test/atdd only as a source of contract cases: it can never go green.
- Keep branch coverage of src at or above 90%.
- Evidence goes in docs/evidence/impl2/. Never edit or fabricate an evidence file or a gate verdict.
- Keep planning/epics.md and _bmad-output/planning-artifacts/epics.md identical, and likewise both copies of sprint-status.yaml.
