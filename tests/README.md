# Module 12 — Test Harness

Test harness for **Module 12 · AI Operations Copilot**, in three layers:

| Layer | Runner | Where | Target |
|---|---|---|---|
| Unit / integration / API / ATDD | `pytest` (+ `pytest-asyncio`, + `hypothesis`) | `tests/` | `make harness`, `make cov` |
| E2E | Playwright (`playwright.config.ts`) | `tests/e2e/*.spec.ts`, page objects in `tests/e2e/pages/` | `make e2e`, `npm test` |
| NFR | k6 | `tests/nfr/*.js` | `make nfr` |

pytest is the primary suite. The E2E and NFR layers drive a real uvicorn process
(`create_app --factory`, `M12_DB_PATH=:memory:`): Playwright starts it through `webServer`,
and `make nfr` starts a temporary one and stops it after k6 exits. Today both layers hold a
`/healthz` smoke. Browser specs and page objects arrive with the React console (story 1-7).

The harness is **independently runnable today**: it imports no Module 12 source, so it
does not depend on Phase 0 provisioning. Fixtures model the contracts, not the code.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-test.txt
npm ci                                   # @playwright/test for the E2E layer
```

The NFR layer needs the `k6` binary on `PATH` (k6 2.x).

Requires **Python 3.11+** and **SQLite >= 3.35** (AD-10: `RETURNING` + JSON1). The
harness asserts the SQLite version at DB-fixture time and fails loudly otherwise.

## Run

```bash
pytest                                   # everything (config in pytest.ini)
pytest -m unit                           # fast, isolated
pytest -m integration                    # migrated-schema tests
pytest -m determinism                    # I2 / FR-14 identity checks
make cov                                 # pytest, branch coverage of src, floor 90%
make e2e                                 # Playwright; starts uvicorn itself
make nfr                                 # k6 smoke against a temporary uvicorn
make ci                                  # ruff + cov + schemas + e2e + nfr
```

Make uses `PY=python3`. Without an activated venv, pass `PY=.venv/bin/python`.

`asyncio_mode = auto`: a plain `async def test_...` is collected and awaited.

## Layout

```
tests/
├── conftest.py            # fixture registry (all mandatory fixtures)
├── support/               # test doubles + factories (the "seam")
│   ├── clock.py           # fake_clock     -> OP-10 clock_port
│   ├── fleet.py           # seed_fleet     -> OP-6 nodes_port estate
│   ├── telemetry.py       # sim_telemetry  -> scripted metrics + fault generation
│   ├── db.py              # db             -> ephemeral SQLite from 001_*.sql
│   ├── explain.py         # explain_assert -> rule + observed-values + citation checks
│   ├── ids.py             # IdFactory      -> OP-13 idgen_port (seeded, deterministic)
│   └── builders.py        # SampleData     -> schema-valid rows + §0.3 records
├── unit/                  # default share of the pyramid (pure, no I/O)
├── integration/           # real DDL, triggers, partial indexes
├── api/                   # /api/v1, /executor/v1 (placeholder until FastAPI app lands)
├── e2e/                   # Playwright specs against the running app
│   ├── smoke.spec.ts      # GET /healthz
│   └── pages/             # page objects (console, story 1-7)
├── nfr/                   # k6 scripts; load paced by executors, never fixed waits
│   └── smoke.js           # /healthz, constant-arrival-rate, thresholds on p95 and errors
└── test_example.py        # smoke: every mandatory fixture wired together
```

## Mandatory fixtures

| Fixture | Contract anchor | Guarantees |
|---|---|---|
| `fake_clock` | OP-10 `clock_port`; §0.1 `ClockRead` | Advanceable, deterministic; `read_id` = `^clk-[0-9a-f]{16}$`; **never** reads wall-clock (I-CLK-1). `cite = clock.now().citation_id` → `clock#clk-…`. |
| `seed_fleet` | OP-6 `nodes_port`; §0.3 `NodeRecord` | Many 1×24 GB nodes + one 2×48 GB node, all `available/healthy`. `get()`/`select()`; `fault()`/`cordon()` mutate the estate. `DEFAULT_STANDARD_NODE_COUNT` is a knob, not a contract. |
| `sim_telemetry` | fleet mutation (no port) | Scripted GPU util/mem/temp + heartbeats. `script_thermal_fault()` reproduces **S3** (`node#ws-gpu-11`, `ERR_THERMAL_88`, cordoned). Time steps come from `fake_clock`. |
| `db` | `001_module12_copilot_schema.sql`; AD-10 | Migrated **in-memory** SQLite (function-scoped isolation). `insert()/query()/count()/tables()/triggers()`; `open_rotation_gate()` for the D42 delete path. |
| `explain_assert` | AD-2, AD-8, AD-11; §0.5 `Intent` | Asserts a decision names ≥1 rule id, the observed values it acted on, and ≥1 citation. Duck-typed: accepts a dict, dataclass, or future `Intent`/`Diagnosis`/`Answer`. |

Supporting: `ids` (`IdFactory`), `sample` (`SampleData` bound to `ids` + `fake_clock.now`),
`schema_path`.

### Recipes

```python
def test_node_triage_grounds_every_claim(fake_clock, seed_fleet, sim_telemetry, explain_assert):
    sim_telemetry.script_thermal_fault("node#ws-gpu-11")
    node = seed_fleet.get("node#ws-gpu-11")
    explain_assert(decision, rule_id="rule.node_triage",
                   values={"error_code": node.error_code})
```

```python
def test_audit_is_append_only(db, sample):
    db.insert("audit_records", sample.audit_row(actor="copilot"))
    # mutation/deletion denied unless the D42 rotation gate is open
```

## Conventions (enforced by review)

- **No real time.** Advancing the clock is the only way time passes; `sim_telemetry` uses it.
- **No `uuid4`/`random`.** Every id comes from `IdFactory` (OP-13, R2) so runs reproduce.
- **Contract-name fidelity.** Use `FR-*`, `NFR-*`, `AD-*`, `I*`, `OP-*`, `D*` and the
  canonical codes (`S_ENF`, `S_CNC`, `S_PUA`, `S_ARF`, `S_RBX`, `S_CAP`) as written in
  `planning/detailed-design/contracts.md`.
- **Records are exact.** §0.3 says "extra fields are a contract violation" — assert the
  full key set, not a subset.
- **Faults are scripted, never slept through.** Reproduce S1–S3 and the mandatory edge
  case (hallucination prevention, test-design.md R-01) with fixtures, not timing tricks.
- **No fixed waits in E2E or k6.** Use web-first assertions, and pace load
  with `constant-vus` or `constant-arrival-rate`. `make e2e` and `make nfr` fail on either.

## Environment knobs

| Var | Default | Purpose |
|---|---|---|
| `TEA_DB_PATH` | `:memory:` | Point the `db` fixture at a temp file (e.g. to inspect state after a failure). |
| `TEA_SCHEMA_PATH` | `planning/detailed-design/schemas/001_module12_copilot_schema.sql` | Override the DDL under test. |

## Coverage targets

Impl-2 gate (`test/test-design.md` §6.5, `docs/impl2-rules.md`): branch coverage of `src/`
**≥ 90%**, enforced by `make cov` (`--cov=src --cov-branch --cov-fail-under=90`). This
supersedes the per-area `service/` floors in §3.2. Every P0 case must also be shown red
before it goes green (§3.4, §6.3): coverage does not prove that. Higher coverage is not a
goal for prose and rendering.

## Next steps (Impl-2)

- `tests/atdd/test_story_<id>.py`: one ATDD suite per Impl-2 story (2-1..2-4, 1-6, 3-3, 1-7),
  calling the real app. `test/atdd/` stays a red, read-only source of contract cases
  (`test/atdd/README.md`).
- `tests/nfr/copilot-load.js`: the story 1-6 k6 budget (50 `constant-vus`, p95 < 800 ms with
  the fake prose adapter, `http_req_failed == 0`, `checks == 1.0`), exported to
  `docs/evidence/impl2/` (§6.3.5).
- `tests/e2e/`: browser specs and page objects for the React console (story 1-7, §6.3.7).
- CI: `.github/workflows/quality-gate.yml` mirrors `make ci`: a banned-wait grep, ruff +
  branch coverage, schema checks, k6 (every `tests/nfr/*.js`, summaries uploaded) and
  Playwright with `--trace on --fail-on-flaky-tests` (TG-I2-5).
