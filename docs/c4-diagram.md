# C4 diagram: AI Operations Copilot (Module 12)

Levels 1 (context) and 2 (containers). They are drawn with plain Mermaid flowcharts in C4 style,
because the experimental Mermaid C4 syntax does not render reliably. The containers follow the
ports and adapters layout in `src/`. The domain imports no adapter (enforced by ruff `TID251` and
`tests/unit/test_architecture_imports.py`).

## Level 1: System context

```mermaid
flowchart TB
    operator["👤 <b>Operator</b><br/>Helpdesk specialist who<br/>resolves student tickets"]
    copilot["<b>AI Operations Copilot</b><br/>Answers operational questions with<br/>cited, deterministic evidence.<br/>Never executes a destructive action."]
    estate["<b>Simulated lab estate</b><br/>External, read-only fixtures:<br/>users, jobs, nodes, policy, events"]
    executor["<b>Executor</b><br/>External, simulated.<br/>Applies an approved proposal."]

    operator -->|"asks diagnostic questions,<br/>confirms job and node actions"| copilot
    copilot -->|"reads state, policy, events"| estate
    copilot -->|"sends the confirmed action"| executor

    classDef person fill:#08427b,stroke:#052e56,color:#fff
    classDef system fill:#1168bd,stroke:#0b4884,color:#fff
    classDef external fill:#999,stroke:#6b6b6b,color:#fff
    class operator person
    class copilot system
    class estate,executor external
```

## Level 2: Containers

```mermaid
flowchart TB
    operator["👤 <b>Operator</b><br/>Helpdesk specialist"]

    subgraph boundary [AI Operations Copilot]
        console["<b>Console</b><br/>React 19, TypeScript, Vite<br/>chat, cited badges, runbook card<br/><i>console/</i>"]
        api["<b>HTTP API</b><br/>FastAPI, synchronous routes<br/><i>src/adapters/inbound/</i>"]
        app["<b>Application</b><br/>use cases: pipeline, sessions,<br/>dry-run, confirmation, dispatch<br/><i>src/application/</i>"]
        domain["<b>Domain</b><br/>pure rules: intent, safety,<br/>diagnosis, citations<br/><i>src/domain/</i>"]
        sim["<b>Simulated providers</b><br/>estate, prose, clock, ids, executor<br/><i>src/adapters/outbound/sim/</i>"]
        db[("<b>SQLite</b><br/>one writer: sessions, answers,<br/>proposals, audit<br/><i>src/adapters/outbound/db/</i>")]
    end

    fixtures["<b>Fixtures</b><br/>JSON: estate, policy, runbooks<br/><i>fixtures/</i>"]

    operator -->|uses| console
    console -->|"JSON over HTTP"| api
    api -->|calls use cases| app
    app -->|uses| domain
    app -->|reads ports, dispatches| sim
    app -->|"writes turns, proposals, audit"| db
    sim -->|loads at start-up| fixtures

    classDef person fill:#08427b,stroke:#052e56,color:#fff
    classDef container fill:#438dd5,stroke:#2e6295,color:#fff
    classDef external fill:#999,stroke:#6b6b6b,color:#fff
    class operator person
    class console,api,app,domain,sim,db container
    class fixtures external
```
