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

Configuration is read from `M12_*` environment variables (see [.env.example](.env.example) for the
reference; real environment variables only, no `.env` file is loaded); every variable has a working
default. The service serves exactly the routes of
[`openapi.yaml`](planning/detailed-design/schemas/openapi.yaml); the generated `/docs` is disabled.

## Session API (stories 1.2 and 1.3)

The service exposes the session lifecycle of the contract (`planning/detailed-design/schemas/openapi.yaml`):

```bash
# 1. open a session
curl -s -X POST localhost:8000/api/v1/sessions -H 'content-type: application/json' \
     -d '{"operator_role": "role-operations"}'
#    -> 201 {"session_id": "sess-0000000000000001", "status": "active", "context": {...}, ...}

# 2. ask a question (routed and diagnosed by deterministic code; the LLM only writes prose)
curl -s -X POST localhost:8000/api/v1/sessions/sess-0000000000000001/queries \
     -H 'content-type: application/json' -d '{"query_text": "why was alex denied deepseek-coder"}'
#    -> 200 {"answers": [{"intent": "diagnose_access_denial",
#          "answer_chain": ["observation", "evidence", "diagnosis"],
#          "diagnosis_class": "access_denial_not_in_allowlist", "claims": [...], "evidence": [...], ...}]}
#    an out-of-domain query ("what's the weather?") is a 200 clarification:
#    {"code": "CLARIFICATION_REQUIRED", "message": "Clarification required: no registered intent matches this query.", ...}

# 3. read it back, then clear it
curl -s localhost:8000/api/v1/sessions/sess-0000000000000001       # 200 context + turns
curl -s -X DELETE localhost:8000/api/v1/sessions/sess-0000000000000001   # 204
```

Errors are always the typed `ErrorBody` JSON (`code`, `status`, `message`, `retryable`): empty or
over-1000-character queries are `400`, an unknown session `404`, a reset/expired or 30-minutes-idle
session `410`, a dependency failure `503`. Sessions and turns live in SQLite (`M12_DB_PATH`;
`:memory:` by default, a file in Docker): with a file database - what Docker uses - sessions and
turns survive restarts; with `:memory:` they do not. The session ids shown above are illustrative.

### What an access-denial answer looks like (story 1.3)

`why was alex denied deepseek-coder` resolves `user#alex` and `model#deepseek-coder` by exact, case-folded
match (never fuzzy), reads the policy clauses and `access_denied` events through the read-only ports and
returns structured **claims** (role, clause `policy#catalog.4.2` with rule `RULE-CAT-04` and its text, reason
class, denial event `event#evt-4711`), each citing entries of the **evidence** set (`user`, `model`, `policy`,
`event`, `clock`; positions `0..n-1`). The diagnosis class, claims and citations are computed by pure code and are
identical on every run; the LLM (simulated in this delivery) is called once and only writes connective prose,
which is rejected if it repeats any fact (one retry, then `503 LLM_PROSE_REJECTED`).

* an unknown user or model is a `200` `ENTITY_NOT_FOUND` body naming every unresolved reference (`Entity Not Found in State: user#ghost.`);
* existing entities with no matching clause/denial event are `CANNOT_CONFIRM` (the gathered evidence is kept on the stored turn);
* `and what about mateo?` resolves `mateo` and reuses the model from the session context.

### Night schedule inquiry (story 3.1)

`why can't group 4 run their fine-tuning job right now` resolves `group#group-4`, reads its pending job
(`job#job-8823`, constrained to `night`), the policy window `window#night` and the clock read, and answers
with class `schedule_window_restricted`: at `2026-10-16T15:00:00.000Z` the window is closed, and the next open
window is `2026-10-16T22:00:00.000Z` to `2026-10-17T06:00:00.000Z` (UTC), each fact cited. The window is half-open
`[start, end)`; a group with no constrained job gets `schedule_no_constraint` and no window, an unknown group is
`ENTITY_NOT_FOUND`, and a failed clock read is a `503 CLOCK_UNAVAILABLE` (a window is never invented).

The clock is simulated (`M12_CLOCK_START`) and does not advance on its own.

## Architecture (Ports & Adapters)

```
src/
├── domain/                 # pure logic: no FastAPI, no DB driver, no real clock, no randomness
├── application/            # use-case implementations: session service, answer pipeline
├── ports/
│   ├── inbound/            # use-case interfaces (session use cases)
│   └── outbound/           # read-only provider ports + id generator + session store
├── adapters/
│   ├── inbound/            # FastAPI app, routers, error envelope
│   └── outbound/
│       ├── sim/            # fixture-backed simulated providers, freezable clock, id generator
│       └── db/             # SQLite connection, migration runner, session store (Module-12-owned)
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
