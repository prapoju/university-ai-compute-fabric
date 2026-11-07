<!-- Impl-2 task statement, trimmed to Module 12. The other 11 Annex modules are left out. -->

# Impl-2: Task Statement

## Advanced Implementation, Testing Alternatives & System Hardening for the Academic AI Compute Fabric

**Course Activity** · Group · 4–6 Hours · **BMad Method (Integrated Testing -TEA & Full Ceremony)**

**Prerequisites:** Completed Impl-1, Plan-2, and Unit 5 Testing Alternatives Presentation.

**Deliverable:** Hardened Codebase, Multi-Flow Automated Test Suite (ATDD, Unit, Integration, k6 NFR, Playwright E2E with POM & Traces), `sprint-status.yaml`, Traceability Matrix (`traceability-matrix.md`), AI Decision Log, and Impl-2 Walkthrough Report (`walkthrough-impl2.md`). All bmad related files included.

---

## 1. Executive Summary & Implementation Framing

### The Threshold of Resilient Engineering: From Scaffolding to Hardened Systems

In **Impl-1**, your engineering triad established the operational baseline of your assigned subsystem: the Ports & Adapters project layout, database schemas and migrations, simulated fleet fixtures, and **three core foundational stories** verifying nominal happy paths and primary state transitions.

In **Impl-2**, your team crosses the threshold into **mission-critical resilience, concurrency defense, fault recovery, and advanced testing alternatives**. In distributed compute environments, systems do not fail during textbook happy paths—they fail under high-concurrency race conditions, network packet loss, thermal emergency spikes, mid-stream token expirations, and unexpected hardware drops.

> **The Active Constraint Principle in Testing:** Tests are not passive compliance checkboxes written after code is completed to satisfy an arbitrary coverage score. Under the **BMad Integrated Testing with TEA** methodology (Unit 5 · Part 3), automated test scaffolds and NFR verification harnesses are **active design constraints** that force architectural modularity, prevent race conditions, and govern deployment. A test suite that was never witnessed failing for the authentic reason provides zero engineering assurance.

---

### Scope of Impl-2: 3 High-Complexity Stories + Advanced Verification Alternatives

To demonstrate senior-level software level, **Task Impl-2** requires each team to deliver:

1. **Three Additional High-Complexity Stories:** Implementation of the **three complex stories** detailed for your assigned module in the Annex (Stories X.4, X.5, and X.6). These stories focus on non-trivial decision algorithms, concurrency hazards, cascading failures, security boundaries, and multi-resource coordination.

2. **Execution of the BMad Testing Alternatives (The 5 Flows):** Rather than treating all code uniformly, each story must be paired with its optimal testing discipline:

   - **Flow A (ATDD-First):** At least one high-risk story must follow strict Acceptance Test-Driven Development using **Murat** (`bmad-testarch-atdd`), where an authentic red-phase test failure is recorded *before* any production code is written.
   - **Flow B (Test-Along):** Concurrent code and test construction with Ports & Adapters isolation and smart fixtures.
   - **Flow D (Quality Gate & NFR Audits):** Automated verification of non-functional requirements (k6 load testing, concurrency row locks, RBAC security gates, and latency budgets).
   - **Flow E (Playwright E2E with Page Object Model):** End-to-end browser verification of interactive workflows with auto-retrying web-first assertions and Playwright Forensic Tracing (`trace.zip`).

3. **Requirement-to-Evidence Traceability Matrix:** Compiling an explicit audit report (`traceability-matrix.md`) using `bmad-testarch-trace` demonstrating end-to-end linkage from PRD functional requirements to passing test execution evidence.

### Standalone Engineering Mandate & Determinism

As in previous phases:

- **Zero Cross-Team Blocking:** Each subsystem remains 100% standalone and decoupled. External dependencies are mocked or simulated via deterministic fixtures.
- **Hardware Agnosticism:** Physical NVIDIA GPUs are not required. The 32-node heterogeneous fleet (31 × 24 GB workstations, 1 × 2 × 48 GB server) is fully modeled through software telemetry generators and seed state.
- **Deterministic Verification:** Any evaluator must be able to run a single command (`pytest`, `npm test`, or `npx playwright test`) and verify 100% passing tests with zero flaky sleep timeouts.

## 2. Learning Objectives

By completing Impl-2, your team will demonstrate mastery of:

1. **Integrated Test Architecture with TEA (Murat):** Operationalizing the Test Architect agent (`bmad-tea`) to conduct risk-based test design before code generation begins.
2. **Extreme Shift-Left & Pre-Story Test Scaffolding:** Initializing end-to-end testing frameworks (`bmad-testarch-framework`) and CI release quality gates (`bmad-testarch-ci`) prior to implementing complex feature logic.
3. **Acceptance Test-Driven Development (ATDD-First):** Executing the strict Red-Green-Refactor cycle for high-risk contracts, witnessing genuine test failures before allowing developer agents (**Amelia**) to construct solutions.
4. **Non-Functional Requirement (NFR) Verification:** Stress-testing software boundaries against the 5 NFR dimensions (Security, Concurrency, Performance, Resilience, Usability) using automated load scripts (k6) and race condition harnesses.
5. **Robust Browser Automation with Playwright:** Building maintainable E2E suites using the Page Object Model (POM), eliminating flaky timeouts with web-first assertions, and leveraging forensic visual traces (`trace.zip`) for CI debugging.
6. **Defeating the 4 Classic Testing Traps:** Structuring test suites that avoid the *Ice Cream Cone*, the *Flaky Sleeper*, the *Mocking Mirage*, and the *Blindly Green* vacuous assertions.
7. **Traceability & Release Governance:** Producing a verified Quality Gate sign-off (`PASS` / `CONCERNS` / `FAIL`) backed by cryptographic logs and test runner execution reports.

## 3. The Integrated Testing Architecture & The 5 BMad Flows

Impl-2 is directly structured upon **Unit 5 · Part 3 (Integrated Testing with TEA)**. Teams must understand and apply the following core pillars:

Phase A: Shift-left Governance:

- `bmad-testarch-framework`
- `bmad-testarch-ci`
- Winston & Murat Audit
- Test Pyramid Scaffolding

Phase B: The five flows

Phase C: Quality:

- `bmad-testarch-nfr` (k6 Load)
- Playwright E2E + POM
- `bmad-testarch-trace`
- Automated PASS/FAIL Gate

### The 5 Testing Flows: Matching Strategy to Risk

Every engineering challenge requires an appropriate verification model. In Impl-2, your 3 assigned stories must span these flows:

| Flow Identifier | Strategy Name | Primary Mechanism & Tooling | When to Apply in Impl-2 |
| --- | --- | --- | --- |
| **Flow A** | **ATDD-First** | `bmad-testarch-atdd` → Failing Red Scaffold → `bmad-build` → Green Pass | **Mandatory for at least 1 story.** Apply to high architectural risk, strict contract rules, or atomic state transitions. |
| **Flow B** | **Test-Along** | Concurrent domain code + unit/integration tests in identical git commit | Standard velocity pattern for well-understood business logic and repository adapters. |
| **Flow C** | **Test-After** | `bmad-testarch-automate` → Coverage scan → Gap analysis → Regression suite | Applied to harden Impl-1 code, remediate legacy debt, or backfill edge-case tests. |
| **Flow D** | **Quality Gate (NFR)** | `bmad-testarch-nfr` → k6 load scripts, concurrency row locks, RBAC audits | **Mandatory for at least 1 story.** Stress tests concurrency limits (p95 latency, zero double-allocation). |
| **Flow E** | **Playwright E2E** | Interactive exploration → Crystallized `.spec.ts` using Page Object Model (POM) | **Mandatory for interactive UI workflows.** Asserts complete user journeys with forensic visual traces. |

---

### The 70 / 20 / 10 + NFR Testing Pyramid

Your Impl-2 test suite must adhere to an economically optimized distribution:

- **70% Unit Tests:** Isolated in-memory tests executing in < 10 ms. Verifies domain entities, policy rule evaluators, state machine transitions, and DTO validations without network or database I/O.
- **20% Integration Tests:** Verifies real database transactions (PostgreSQL / SQLite), repository adapters, OpenAPI contract compliance, and mock simulator message exchanges.
- **10% E2E Browser Tests:** Verifies critical user journeys via Playwright, using Page Objects to decouple DOM selectors from test specs.
- **NFR Verification Layer:** Automated k6 load scripts and concurrency hammers executing in CI, asserting numeric latency and data integrity thresholds.

---

### Playwright E2E Architecture: Page Object Model & Forensic Traces

For all browser-based scenarios in Impl-2:

1. **Page Object Model (POM):** UI selectors and user interactions must live in dedicated Page Object classes (e.g., `HostDashboardPage`, `FleetMapPage`, `ReservationCalendarPage`). Test specs must read like human user stories, not CSS selector spaghetti.
2. **Web-First Auto-Retrying Assertions:** Use `await expect(locator).toBeVisible()` or `toHaveText()`. **Zero hardcoded timeouts (`waitForTimeout`) are permitted.**
3. **Forensic Visual Tracing:** Configure Playwright with `trace: 'on-first-retry'`. On test failure, Playwright automatically packages a `trace.zip` containing frame-by-frame DOM snapshots, network waterfalls, console logs, and action video.

---

### Coaching Playbook: Avoiding the 4 Classic Student Testing Traps

During evaluation, your submission will be strictly audited against the **4 Classic Testing Traps**:

1. The Ice Cream Cone (Inverted Pyramid): Everything tested via slow fragile browser E2E tests.
2. The Flaky Sleeper (Timing Hacks): Arbitrary `sleep(5)` or `waitForTimeout(5000)` calls.
3. The Mocking Mirage (Over-Mocking): Mocking the entity under test, verifying nothing real.
4. The Blindly Green: AI-generated tests without meaningful `expect()` checks

---

## 4. Technical Baseline, Scaffolding Extensions & Tooling Standards

Building upon Impl-1, your repository structure must be extended to incorporate the integrated testing infrastructure.

## 5. Deliverables & Acceptance Checklist

### Required Deliverables

Each student team must submit their extended repository containing:

1. **Hardened Source Code:** Complete, running codebase implementing the 3 foundational stories (from Impl-1) plus the **3 additional complex stories** (Stories X.4, X.5, and X.6 from the Annex).
2. **Multi-Flow Automated Test Suite:**
   - Unit and integration tests passing with ≥ 90% branch coverage on core domain logic.
   - At least **1 story verified via Flow A (ATDD-First)** with documented red-phase failure logs.
   - At least **1 story verified via Flow D (Quality Gate / NFR)** with k6 script and passing latency/concurrency assertions.
   - At least **1 interactive workflow verified via Flow E (Playwright E2E)** with Page Object Model and zero hardcoded sleeps.
3. **Updated `sprint-status.yaml`:** Tracking all 6 stories (X.1 through X.6) through to `ready-for-review` / `done`.
4. **Traceability Matrix (`traceability-matrix.md`):** Formatted audit artifact generated via `bmad-testarch-trace`, mapping:

   PRD Requirement → User Story → Automated Test Files → CI Evidence → Verdict (PASS)
5. **Implementation Walkthrough Report (`walkthrough-impl2.md`):**
   - Architectural hardening and concurrency defense summary.
   - For each of the 3 complex stories: Technical challenge, testing flow applied, code implemented, and terminal test evidence.
   - Red-phase ATDD evidence (terminal output proving test failed before production code existed).
   - k6 load test summary table (p95, p99, error rate).
   - Playwright E2E run log and trace confirmation.
6. **AI Decision Log (`ai-decision-log.md`):** Minimum 8 documented AI interactions across Impl-2, including at least **2 instances** where the team corrected an AI testing mistake (e.g., rejecting an AI attempt to insert a `sleep()` timeout or catching an over-mocked test).
7. **All bmad related files including the specs, planning and solutioning.**

---

### Student Checklist (DoR)

Before submitting, verify that your project satisfies every check:

- [ ] **Unified Execution:** Running `pytest` (or `npm test`) and `npx playwright test` succeeds with 100% pass rate.
- [ ] **ATDD Evidence:** Terminal log captures the initial failing red-phase test run for your Flow A story.
- [ ] **Zero Flaky Sleeps:** Codebase contains zero instances of `time.sleep()`, `waitForTimeout()`, or `sleep(5000)`.
- [ ] **Concurrency Defense:** Concurrency test hammers database/state with simultaneous requests, proving zero race conditions or double-allocations.
- [ ] **NFR Load Proof:** k6 script runs successfully, verifying p95 latency budget and zero unhandled server crashes under burst traffic.
- [ ] **Page Object Model:** All Playwright E2E tests interact with web views exclusively through Page Objects.
- [ ] **Traceability Signed Off:** `traceability-matrix.md` contains zero unmapped requirements and awards a formal `PASS` verdict.
- [ ] **AI Governance:** AI Decision Log explicitly details how human engineering steered agent construction.

---

## 6. Academic Evaluation Rubric (100 Points)

| Assessment Dimension | Weight | Outstanding (90–100%) | Proficient (75–89%) | Developing (60–74%) | Beginning (<60%) |
| --- | --- | --- | --- | --- | --- |
| **1. Architecture, Hardening & Concurrency** | **20%** | Pristine Ports & Adapters extension. Flawless concurrency defense (atomic locks, row locks, idempotency). Graceful degradation and circuit breakers under failure states. | Solid architecture; minor concurrency rough edges (e.g. potential lock contention without deadlock). Handles core failure modes well. | Architecture leaks framework logic into domain; weak concurrency handling; edge cases crash service instead of returning structured errors. | Fragile, monolithic code; severe race conditions; system crashes under basic concurrent requests. |
| **2. Functional Delivery of 3 Complex Stories** | **25%** | All 3 complex stories fully implemented and verified. Deep algorithmic and state-machine correctness. Strictly upholds all binding Architectural Invariants (AD-n). | All 3 stories functional; minor edge-case oversight in complex state transitions. Invariants upheld. | 2 of 3 stories functional, or complex logic bypassed with over-simplified stubs. | Stories incomplete; business rules fail on edge inputs; placeholder mocks in core logic. |
| **3. Testing Alternatives & Flow Implementation** | **25%** | Flawless application of the 5 Flows. Genuine ATDD-First red phase documented. Robust k6 NFR load test meeting latency budgets. Playwright E2E uses POM with zero flaky timeouts. | All flows applied; ATDD red phase captured; k6 test passes; minor POM coupling or sub-optimal assertion retry in Playwright. | Testing pyramid inverted (Ice Cream Cone); ATDD red phase missing or faked; hardcoded sleeps present; vacuous assertions. | No ATDD; missing k6 NFR tests; broken E2E suite; extensive over-mocking verifying nothing real. |
| **4. Traceability, Quality Gate & CI/CD** | **15%** | Comprehensive `traceability-matrix.md` mapping all requirements to test evidence. Automated quality gate awards clean `PASS`. Reproducible single-command CI setup. | Matrix present with clear mapping; minor formatting gaps; quality gate passes with documented notes. | Traceability matrix incomplete; unmapped stories; quality gate reports unresolved concerns. | Missing traceability matrix; broken CI configuration; no evidence linking tests to requirements. |
| **5. Code Craft, Forensic Traces & AI Governance** | **15%** | Exemplary typing and idiomatic code. Playwright forensic traces (`trace.zip`) captured on CI. AI Decision Log documents deep human oversight and ≥ 2 critical test corrections. | Clean code with good readability. Playwright trace configured. AI Decision Log documents prompts and review notes. | Inconsistent styling; sparse comments; AI Decision Log lacks critical scrutiny of generated test code. | Sloppy code; hardcoded credentials; zero AI oversight evidence; unreviewed AI copy-paste. |

---

## Annex: The 12 Subsystem Modules & 3 Recommended Complex Stories (Impl-2)

Each group may implement the **3 complex stories** detailed below for their assigned module, mapping each story to its mandated testing alternative. The stories are recommendations that groups may adapt to their specifications or replace by stories that are better suited to their previous work.

---

### Module 12: AI Operations Copilot

*Focus: Destructive action safety guardrails, high-concurrency tool-calling budgets, and cited runbook cards.*

#### Story 12.4: Destructive Action Safety Guardrail & Administrative Confirmation Two-Step

- **Mandated Flow: Flow A: ATDD-First** (`bmad-testarch-atdd`)
- **As the** AI Operations Copilot Guardrail Engine,
- **I want to** intercept natural language requests with destructive blast radius (e.g., *"Delete all pending jobs"* or *"Cordon entire lab"*),
- **So that** direct execution is blocked, a dry-run impact card is generated, and a cryptographic confirmation token is required.
- **Technical Context:** Inbound `POST /api/v1/copilot/chat`; Invariant `AD-30`: Zero autonomous execution of state-mutating destructive operations. Mandatory dry-run calculation and explicit two-step tokenized confirmation.
- **Technical Tasks:**
  1. *Murat Red Phase:* Scaffold failing test prompting destructive prompt and asserting rejection of unconfirmed execution.
  2. Implement intent safety classifier and dry-run blast radius calculator.
  3. Return dry-run impact schema with single-use confirmation token valid for 60 seconds.
- **BDD Acceptance Scenarios:**

```gherkin
Scenario: Copilot intercepts destructive command and requires explicit confirmation
  Given an operator prompts Copilot "Terminate all active jobs for CS-101"
  When the copilot parses the intent
  Then it refuses immediate execution
  And responds with a dry-run impact summary: "3 active jobs will be terminated across nodes ws-02, ws-05, ws-08"
  And provides a single-use confirmation token valid for 60 seconds
  And cluster state remains completely unchanged until the token is confirmed
```

#### Story 12.5: High-Concurrency Diagnostic Tool-Calling Under k6 Latency Budget

- **Mandated Flow: Flow D: Quality Gate (Performance & NFR)**
- **As the** Copilot Query Orchestrator,
- **I want to** execute multi-tool diagnostic queries (querying policy engine, twin state, and catalog) for 50 concurrent operators,
- **So that** responses complete within p95 < 800 ms without tool execution deadlocks.
- **Technical Context:** Inbound `POST /api/v1/copilot/query`; k6 script: `tests/nfr/copilot-load.js`.
- **Technical Tasks:**
  1. Implement parallel tool-calling dispatcher (`asyncio.gather`) querying mock service adapters.
  2. Build k6 script simulating 50 concurrent diagnostic inquiries.
  3. Assert p95 < 800 ms latency budget and 100% cited source accuracy.
- **BDD Acceptance Scenarios:**

```gherkin
Scenario: Copilot multi-tool diagnostic queries satisfy 800 ms latency budget
  Given 50 concurrent operators asking "Why was job #402 denied access to deepseek-coder?"
  When k6 executes the load test
  Then 100% of responses return HTTP 200 with citations to Policy Rule PR-04 and Catalog Entry CE-12
  And the measured p95 response latency is strictly less than 800 ms
  And zero unhandled tool timeout exceptions occur
```

#### Story 12.6: Conversational Diagnostic Console with Cited State Cards E2E

- **Mandated Flow: Flow E: Playwright E2E with Page Object Model**
- **As a** Frontline Helpdesk Specialist (*Nadia*),
- **I want to** submit user operational complaints into a chat console and receive answers containing cited state cards and copyable troubleshooting runbooks,
- **So that** I can resolve student tickets quickly through an interactive UI.
- **Technical Context:** Web View `/helpdesk/copilot`; Page Object: `CopilotConsolePage.ts`.
- **Technical Tasks:**
  1. Build `CopilotConsolePage` modeling chat stream container, prompt input, citation badges, and runbook card.
  2. Implement auto-retrying assertions verifying appearance of cited state pills and runbook markdown formatting.
  3. Capture Playwright trace validating message rendering and "Copy Runbook" clipboard action.
- **BDD Acceptance Scenarios:**

```gherkin
Scenario: Helpdesk specialist investigates access denial and copies verified runbook
  Given Nadia is on the Copilot Operations Console
  When she inputs "Student Alex was denied model deepseek-coder. Diagnose and provide runbook."
  And clicks "Submit Inquiry"
  Then the response stream renders with cited badge "Verified via Policy Engine [Rule PR-12]"
  And displays a troubleshooting runbook card with formatted step-by-step instructions
  When Nadia clicks "Copy Runbook to Clipboard"
  Then a success checkmark badge confirms the runbook was copied
```
