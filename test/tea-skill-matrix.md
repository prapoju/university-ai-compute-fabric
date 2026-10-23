# Step 3.7 - TEA Skill Matrix

This table shows what each BMad TEA skill produced.
It also shows what problem it found in our package.
Simple words only.

| Quality / Test Workflow | BMad TEA Skill | Artifact you produced | Defect it caught |
|---|---|---|---|
| Risk-Based Test Strategy | `/bmad-testarch-test-design` | `test/test-design.md` | It found we had big safety risks but no test harness for them. We had no metrics sink. We had no concurrency harness. We had no fake LLM port. It also forced the hallucination Edge Case to P0. |
| Framework Initialization | `/bmad-testarch-framework` | `pytest.ini`, `tests/conftest.py`, `tests/support/*`, `tests/README.md` | It found that the real DB guards had no test. Nothing ran the actual SQL. The guards are the append-only audit, the proposal state machine, and the claim-keeps-citation rule. We fixed this with the `db` fixture and `tests/integration/test_db_schema.py`. |
| ATDD Test Generation | `/bmad-testarch-atdd` | `test/atdd/module12_contracts.test.py` (121 red tests) and `module12_interface.py` | It found holes in the contract. The executor result needed a `source` field. The `dry_run_ref.proposal_id` had to equal `proposal_id`. A canonical 200 reply had to be an `ErrorBody` object, not a bare string. |
| CI Quality Gate Scaffold | `/bmad-testarch-ci` | `pytest.ini` and `requirements-test.txt` | It found the 121 red tests would run with the green tests. Then no gate could ever pass. We split them. The gate runs `tests/` only. The red suite runs on its own. There is no CI workflow file yet. |
| NFR Evidence Audit | `/bmad-testarch-nfr` | `test/nfr-evidence.md` | It found 4 NFRs with no harness at all. They are NFR-5 latency, NFR-6 concurrency, NFR-9 usability, and NFR-10 extensibility. We recorded them as open gaps T-4 to T-7. |
| Test Quality Review | `/bmad-testarch-test-review` | `test/test-review.md` | It found `H5`. The ATDD file is 1,500 lines. The cap is 1,000. It found `H3`. Two tests use `if else` to choose the assert. A wrong shape could still pass. Score is 97 of 100. The verdict is Request Changes. |
| Traceability Matrix and Gate | `/bmad-testarch-trace` | `test/traceability-matrix.md` | It found that FR-15 had no test at all. FR-15 is the prompt injection check. It also found the Story IDs were not bound. We bound every FR and NFR to its story. The gate is still NOT_EVALUATED. All tests are red and there is no code yet. |
