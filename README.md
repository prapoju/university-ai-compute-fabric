# Module 12 — AI Operations Copilot

Impl-1 build of the **AI Operations Copilot** for the Academic AI Compute Fabric: a read-only,
evidence-grounded assistant that explains operational questions (access denials, schedule windows,
node triage) from a **simulated** fleet (31 × 24 GB workstations + 1 server with 2 × 48 GB GPUs).
No GPU, cluster or network is needed.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # or: pip install -r requirements-test.txt

python -m src.dependency_check     # validates Python, SQLite >= 3.35, packages, fixtures
pytest                             # unit + integration + api, no skips
ruff check src tests               # lint

uvicorn src.adapters.inbound.app:create_app --factory   # http://127.0.0.1:8000
curl http://127.0.0.1:8000/healthz                       # liveness
curl http://127.0.0.1:8000/readyz                        # readiness (dependencies, migrations, ...)
```

Or with Docker: `docker compose up --build` (service on port 8000, healthchecked).

Configuration is read from `M12_*` environment variables (see [.env.example](.env.example));
every variable has a working default.

## Architecture (Ports & Adapters)

```
src/
├── domain/                 # pure logic: no FastAPI, no DB driver, no real clock, no randomness
├── ports/
│   ├── inbound/            # use-case interfaces
│   └── outbound/           # read-only provider ports (users, catalog, nodes, clock, ...)
├── adapters/
│   ├── inbound/            # FastAPI app, routers, error envelope
│   └── outbound/
│       ├── sim/            # fixture-backed simulated providers + freezable clock
│       └── db/             # SQLite connection + migration runner (Module-12-owned stores only)
├── config.py               # validated settings (M12_* variables)
├── dependency_check.py     # startup environment validation
└── bootstrap.py            # composition root: the only place adapters are wired
fixtures/                   # seeded estate (JSON, read-only) — single source of truth
migrations/                 # numbered SQL, applied by the stdlib runner
tests/                      # pytest: unit/, integration/, api/, support/ (harness doubles)
planning/                   # PRD, architecture, contracts, OpenAPI, epics (the active constraints)
```

Dependency direction: `adapters → ports → domain`. The planning documents were written with a
`service/` layout; this repo follows the course layout instead (`service/core → src/domain`,
`service/ports/in|out → src/ports/inbound|outbound`, `service/api → src/adapters/inbound`,
`service/adapters/* → src/adapters/outbound/*`).

## Project status

Tracked in [`implementation-artifacts/sprint-status.yaml`](implementation-artifacts/sprint-status.yaml).
