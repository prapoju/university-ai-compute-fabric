# C4 diagram: AI Operations Copilot (Module 12)

Levels 1 (context) and 2 (containers), in Mermaid C4 syntax. The containers follow the ports
and adapters layout in `src/`. The domain has no adapter imports (enforced by ruff `TID251` and
`tests/unit/test_architecture_imports.py`).

## Level 1: System context

```mermaid
C4Context
    title System context: AI Operations Copilot

    Person(operator, "Operator", "Helpdesk specialist (Nadia) who resolves student tickets")
    System(copilot, "AI Operations Copilot", "Answers operational questions with cited, deterministic evidence; never executes a destructive action")
    System_Ext(executor, "Executor", "Applies an approved proposal (simulated in this prototype)")
    System_Ext(estate, "Simulated lab estate", "Fixtures: users, groups, jobs, nodes, policy, events, runbooks (read-only)")

    Rel(operator, copilot, "Asks questions, confirms proposals", "HTTPS, browser")
    Rel(copilot, estate, "Reads state, policy, events", "in-process ports")
    Rel(copilot, executor, "Dispatches a confirmed proposal", "port call, once")
```

## Level 2: Containers

```mermaid
C4Container
    title Containers: AI Operations Copilot

    Person(operator, "Operator", "Helpdesk specialist")

    Container_Boundary(copilot, "AI Operations Copilot") {
        Container(console, "Console", "React 19, TypeScript, Vite", "Chat container, cited badges, runbook card, copy action (src: console/)")
        Container(api, "HTTP API", "FastAPI, sync routes", "Inbound adapter: /api/v1 routes, error envelope (src/adapters/inbound/)")
        Container(app, "Application", "Python", "Use cases: pipeline, session, dry-run, confirmation, dispatch, parallel reads (src/application/)")
        Container(domain, "Domain", "Python, pure", "Intent rules, safety, dry-run, confirmation, diagnosis, citations (src/domain/)")
        Container(sim, "Simulated providers", "Python", "Fixture-backed ports: estate, prose, clock, ids, executor (src/adapters/outbound/sim/)")
        ContainerDb(db, "SQLite", "SQLite, one writer", "Sessions, answers, proposals, tool-call audit (src/adapters/outbound/db/)")
    }

    System_Ext(fixtures, "Fixtures", "fixtures/: estate, policy, runbooks (JSON)")

    Rel(operator, console, "Uses", "HTTPS")
    Rel(console, api, "Calls", "JSON over HTTP, synchronous")
    Rel(api, app, "Calls use cases")
    Rel(app, domain, "Uses pure rules")
    Rel(app, sim, "Reads ports, dispatches executor")
    Rel(app, db, "Writes turns, proposals, audit", "single writer")
    Rel(sim, fixtures, "Loads at start-up")
```
