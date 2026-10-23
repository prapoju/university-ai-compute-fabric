---
title: Module 12 — AI Operations Copilot
status: draft
created: 2026-09-27
updated: 2026-09-27
canonical_path: _bmad-output/planning-artifacts/prds/prd-plan-2-university-ai-fabric-2026-09-27/prd.md
---

# PRD: Module 12 — AI Operations Copilot

*Working title — confirm.*

## 0. Document Purpose

This PRD specifies **Module 12: AI Operations Copilot**, an agentic conversational assistant that lets lab helpdesk operators diagnose operational complaints ("Why was my job cancelled?", "Why can't CS101 access Llama-3?") against simulated system state and institutional policy files, and receive cited, evidence-level deterministic explanations and operational runbooks. It is one module of the University AI Compute Management Platform (see `docs/project - university_ai_compute_management_platform_brief.md`) and is specified against `docs/module_profile.md`.

The PRD is written for the course evaluation, downstream workflows (UX, architecture, epics/stories), and the prototype build. It uses the assignment-mandated FR structure (system responsibility / trigger / inputs / validation rules / outputs / measurable test condition), explicit numeric NFRs, and a scenario-traceability matrix. It is a module-level spec and deliberately does **not** re-specify the platform's other modules. Decisions D1–D15 in `ai-decision-log.md` govern the boundaries asserted here. The adversarial review and its triage are recorded in `review-prd-adversarial.md`.

## 1. Vision

Lab operators lose significant time every week chasing complaints through scattered state and policy documents: a student was denied a model, a group's training job won't start, a node went down. `[ASSUMPTION A-14: the magnitude of current complaint-resolution time is illustrative, not a measured baseline from the brief; SM-5 measures prototype completion time instead.]` Module 12 is a Conversational Operations Console where an operator types the question and the Copilot — an agentic assistant — retrieves the relevant user, catalog, node, job, and policy records, and answers with a **cited, evidence-level deterministic** explanation (identical inputs → identical evidence set, citations, diagnosis class, and runbook steps; prose may vary) and, when appropriate, a step-by-step runbook. Nothing is invented: every entity, policy, and event is retrieved from simulated state, every factual claim carries a resolvable citation, and non-existent references produce a clean "Entity Not Found in State" rather than a plausible narrative.

The Copilot **explains, diagnoses, retrieves evidence, and recommends**. It never enforces access, never schedules, never reserves GPUs, never cordons nodes, and never deletes jobs itself. Destructive requests are refused with a dry-run and handed to an executor only after explicit administrative confirmation. The result is a safe, auditable, evidence-grounded front door to operations that the underlying systems of the platform remain fully responsible for.

## 2. Boundaries — What Module 12 Owns and Does Not

### 2.1 Owns
- The conversational natural-language console (operator-facing).
- Intent interpretation, entity resolution, and query planning against state + policy sources.
- Evidence-level deterministic, cited diagnostic explanations and retrospective diagnosis via the event log.
- Runbook generation from registered templates (curated content; no free invention).
- The standalone prototype's **mock** state/policy providers, accessed **only** through defined read-only contracts.
- Guardrails: hallucination prevention, destructive-action refusal, dry-run, confirmation flow, safe-failure behavior, and content data-hygiene.
- Tool-call audit log, state inspection viewer, citation cards.

### 2.2 Reads / Consumes (mocked or provided)
- Users & roles (e.g., student Alex); model catalog + access policy (CS101→Llama-3, deepseek-coder allowlist).
- Node state: cordon status, error codes (ERR_THERMAL_88), health.
- Jobs/queue state: pending jobs, groups, cancellations.
- Reservations; clock / policy windows (Night Policy).
- Minimal event log (denials, cancellations, cordons).
- Policy and runbook content files.

### 2.3 Delegates (explains, never performs)
- Authorization enforcement — access control subsystem.
- GPU reservations, quotas, fair-share — resource-allocator subsystem.
- Job scheduling and time-window enforcement — scheduler.
- Node cordon/uncordon and physical remediation — node management.
- Job deletion/cancellation execution — job-control subsystem (via propose-only handoff).

### 2.4 Explicitly Out of Scope
- Being the system of record for state or policy (read-only consumer).
- Performing mutations unilaterally — even confirmed destructive actions are handed off, not executed.
- Serving models / running training.
- Student/teacher self-service — console users are lab operations staff (Nadia-class operators); Nadia is the named primary persona, not a hard single-session limit (see A-15, NFR-6).
- Reservation/lecture-machine availability management — reservation conflicts are diagnosed elsewhere, not by Module 12.

`[ASSUMPTION A-1: boundaries defensively derived; validate against the full Annex when available — D1.]`

## 3. Named Academic Protagonists

- **Nadia — AI Lab Operations Engineer (Frontline Helpdesk).** The primary operator persona and a Nadia-class console user (the console may support multiple concurrent operator sessions with the same role/capability profile — A-15, NFR-6). She keeps a heterogeneous GPU fleet running for a whole faculty: when a student is locked out of a model or a professor's training job won't start, the complaint lands on her desk mid-shift, with someone waiting. She is moderately technical — comfortable operating consoles and following runbooks, but not a Kubernetes/infrastructure expert and with no time to read raw state files or policy YAML. Her professional stake: she must answer *correctly and confidently* the first time, because a wrong "reason" she relays to a professor is worse than a slow one; and she must never trigger a destructive action by accident. She drives UJ-1–UJ-4.
- **Dr. Aris Thorne — NLP Professor (CS101).** A secondary protagonist whose course is the source of most complaints: his students were blocked from Llama-3, and he expects a citable answer when a training job is held. He is not a console user — his complaints reach the Copilot through Nadia (UJ-1, UJ-2 only). Reservation/lecture-machine availability is explicitly out of Module 12's scope (§2.4, §16); the persona does not imply a reservation-diagnosis capability in this module.
- **Mateo — Undergraduate Student.** A secondary protagonist and the subject of UJ-1: his access to `deepseek-coder` was denied and he wants an understandable reason. He is not a console user; the Copilot answers him only through Nadia, who must relay a clear, evidence-backed explanation.
- **AI Ops Copilot Assistant.** The system protagonist — an agentic assistant that retrieves, explains, and recommends; it is explicitly not a system of record and not an executor.
- **Non-users (v1):** students and teachers do not talk to the Copilot directly; their complaints reach it through Nadia-class operators. Academic administration and privileged researchers are not direct users of Module 12.

## 4. Module Goals

- **G-1** Turn a natural-language operational complaint into a cited, evidence-level deterministic diagnosis in seconds (vs. the hours of manual correlation Nadia spends today — baseline illustrative, A-14).
- **G-2** Guarantee evidence grounding over the defined prototype state and evaluation corpus: zero fabricated entities, policies, or events in any answer.
- **G-3** Provide actionable, template-backed runbooks for triageable conditions.
- **G-4** Make the Copilot's own behavior safe and auditable: no direct mutations, dry-run + confirmation for destructive intents, and a complete append-only tool-call audit log.
- **G-5** Keep Module 12 cleanly separated from the underlying systems that actually manage authorization, reservations, quotas, scheduling, node state, and jobs.

## 5. Key User Journeys

- **UJ-1. Nadia answers "Why was Alex denied deepseek-coder?"**
  - **Persona + context:** Nadia, mid-shift, a student is upset at the counter; she opens the console on the shared lab machine.
  - **Entry state:** console open, no auth friction (v1), fresh session.
  - **Path:** types the query → Copilot resolves "Alex" and "deepseek-coder" → retrieves Alex's role and the catalog-policy clause → renders diagnosis with citation cards → Nadia reads it, sees the policy clause, and relays it.
  - **Climax:** the citation card shows the exact policy rule denying the model to Alex's role; Nadia can point to it.
  - **Resolution:** Nadia answers the student, closes the session. Audit log shows the retrieval calls.
  - **Edge case:** if Alex or the model does not exist, the Copilot returns "Entity Not Found in State" — Nadia flags the student's claim as unverifiable rather than inventing a reason.
- **UJ-2. Nadia answers "Why can't Group 4 run their fine-tuning job right now?"**
  - **Persona + context:** teacher sent a screenshot of a failed launch; it is 15:00.
  - **Entry state:** console open with current session.
  - **Path:** types query → Copilot resolves Group 4 and its pending job → checks the clock (15:00) against the Night Policy → explains the training window restriction → computes the next open window.
  - **Climax:** answer states the policy and shows "next open window: today 20:00–08:00".
  - **Resolution:** Nadia relays the window; no further action. **Edge case:** if the job has no scheduling constraint at all, the Copilot says so instead of implying a window.
- **UJ-3. Nadia gets a node-triage runbook for ws-gpu-11.**
  - **Persona + context:** monitoring alert: node cordoned, ERR_THERMAL_88.
  - **Entry state:** console open.
  - **Path:** types query → Copilot resolves the node, confirms cordon + error code → pulls the ERR_THERMAL_88 runbook template → renders ordered steps with safety warnings.
  - **Climax:** step-by-step fan/airflow inspection runbook with required tools and a safety warning.
  - **Resolution:** Nadia follows the runbook; the actual uncordon remains the node-management subsystem's job, and physical-safety certification of runbook content remains the institutional content owner's (OQ-11).
- **UJ-4. Nadia accidentally types "Delete all pending jobs for CS201."**
  - **Persona + context:** mid-hurry, testing the console.
  - **Path:** Copilot classifies the intent as destructive → refuses direct execution → produces a dry-run listing every pending CS201 job → asks for explicit administrative confirmation → only after Nadia confirms does it emit a propose-only handoff to the (simulated) executor.
  - **Climax:** the dry-run and the confirmation boundary make the scope of the action visible before anything is proposed.
  - **Resolution:** handoff logged and dispatched; zero mutations performed by the Copilot. The simulated executor applies the deletion only after the confirmation gate, and the audit log distinguishes the Copilot's proposal from the executor-applied mutation. **Edge case:** a second confirm step still cannot make the Copilot execute — it can only dispatch.

## 6. Glossary

- **Conversational Operations Console** — the standalone Module 12 UI: chat surface + state inspection viewer + tool-call audit log + citation cards.
- **Copilot** — the agentic assistant; receives natural-language operational inquiries, retrieves evidence, explains, recommends. Never a system of record and never an executor.
- **Nadia-class operator** — an operator with the same role and capability profile as Nadia (lab helpdesk engineer): moderately technical, trained on the console, no infra/platform expertise required. Used to scope concurrency (NFR-6) and usability (NFR-9) without implying a single literal session.
- **Simulated system state** — the mock stores (users/roles, model catalog + access policy, nodes, jobs/queue, groups, reservations, policy windows, event log) that Module 12 reads via read-only contracts. Owned by Module 12 for the prototype; not authoritative.
- **Institutional policy files** — curated policy content (catalog access policy, Night Policy) and runbook templates.
- **Citation card** — a UI element linking a factual claim to the retrieved state record or policy clause (source ID + snippet).
- **Tool-call audit log** — append-only, immutable record of every copilot tool invocation, capped at a defined prototype size with rotation (NFR-11); distinguishes copilot proposals from executor-applied mutations (FR-10).
- **Event log** — minimal simulated log of access denials, job cancellations, and node cordons, supporting retrospective diagnosis.
- **Dry-run** — enumeration of the actions a destructive proposal would perform, shown to the operator **before** any confirmation or handoff (FR-09).
- **Confirmation gate (procedural)** — the explicit operator action required before a destructive proposal is handed off. In V1 it is a deliberate **procedural** safety boundary, not an authentication/authorization mechanism (D9); real administrator identity and authorization are delegated to an external subsystem and mocked in the prototype.
- **Propose-only handoff** — the contract by which a confirmed proposed action is dispatched to an external/simulated executor; the copilot performs no mutation, and the executor applies the mutation only after the confirmation gate (FR-10).
- **Read-only contract** — the interface through which the copilot queries state/policy; the copilot has no write path.
- **"Entity Not Found in State"** — the canonical response when an explicitly referenced entity is absent from simulated state (FR-03).
- **"Cannot confirm (insufficient evidence)"** — the canonical response when the referenced entity exists but the available evidence cannot establish the requested diagnosis (e.g., no matching event, no applicable policy clause, no runbook template) (FR-04–FR-06).
- **Determinism (evidence-level)** — given identical query + state snapshot + policy + configuration, the same evidence set, citations, diagnosis class, and runbook steps are produced; prose may vary (D4).
- **Night Policy** — fixture policy restricting fine-tuning/training to a defined night window; exact hours are fixture content (A-10).

## 7. Features

### 7.1 Conversational Console & Intake

**Description:** The console accepts free-text operational inquiries, routes them to the correct diagnostic capability, and retains minimal session context across turns. Realizes UJ-1–UJ-4. English-only in v1 `[ASSUMPTION A-8]`.

#### FR-01: Conversational intake and intent routing

- **System responsibility:** Accept natural-language operational inquiries and route each to exactly one registered diagnostic intent; when no intent matches, ask for clarification instead of guessing; when a query expresses multiple supported intents, either decompose it into independently validated sub-queries or ask the operator to clarify when decomposition is unsafe or ambiguous.
- **Trigger:** Operator submits a query in the console.
- **Inputs:** query text (UTF-8, ≤ 1,000 chars), session id, timestamp.
- **Validation rules:** text non-empty; length ≤ 1,000 chars; every query maps to one registered intent, to the clarification path, or (for compound queries) to a set of intents that are decomposed and independently validated; no forced routing; a compound query is never silently truncated to a single intent.
- **Outputs:** routed intent + structured entity payload; or a clarification / not-supported prompt; or a decomposed set of sub-queries each with its own routed intent and entity payload.
- **Measurable test condition:** 100% of the four mandatory scenario queries route to the correct intent handler; ≥ 95% of a 20-query variant corpus route correctly; 100% of out-of-domain queries ("what's the weather?") return the clarification/not-supported response and are never force-routed; a defined compound-query set spanning two supported intents either produces two independently validated, cited answers or a clarification prompt (100%), and a compound query for which decomposition is unsafe triggers clarification (100%).

#### FR-02: Minimal session and conversation context

- **System responsibility:** Maintain minimal per-session conversational context: session creation on first query, retention of resolved entities and active context across turns, resolution of follow-up entity references (e.g., "and what about ws-gpu-12?"), and an explicit session reset/clear control. Context is limited to the prototype's operational scope; it is not a general conversational-memory system.
- **Trigger:** Operator submits a query in an active session; operator clears or resets the session.
- **Inputs:** session id, turn history (resolved entities, prior intents), current query.
- **Validation rules:** a session exists or is created on first query; follow-up references resolve against session context first, then against state via FR-03; reset clears all context; session context alone never authorizes a destructive action (a destructive intent always passes through FR-09's dry-run + confirmation gate).
- **Outputs:** updated session context; resolution of follow-up references; reset/clear confirmation.
- **Measurable test condition:** In a defined follow-up test set, references relying on prior-turn context resolve correctly (≥ 95%); reset clears all context (100%); follow-up entity resolution never invents entities (0 fabricated across the corpus); no session-context path can trigger a destructive dry-run or confirmation without an explicit FR-09 intent (0 occurrences).

#### 7.1.1 V1 Intent Taxonomy

| Intent | Purpose | Trigger shape | Required inputs | Associated FRs |
|--------|---------|---------------|-----------------|----------------|
| Access-denial diagnosis | Explain why a user was denied a model (UJ-1) | "why was `<user>` denied `<model>`?" | user id, model id, optional time | FR-01, FR-03, FR-04, FR-13 |
| Schedule/window inquiry | Explain why a job cannot run now + next window (UJ-2) | "why can't `<group>` run `<job>` right now?" | group/job id, clock time | FR-01, FR-03, FR-05, FR-13 |
| Node triage / runbook | Produce template runbook for a cordoned node (UJ-3) | node + cordon/error code | node id, error code | FR-01, FR-03, FR-07, FR-08 |
| Retrospective event diagnosis | Answer "why was X cancelled/denied/cordoned?" | past-event reference | entity id, event type, time window | FR-01, FR-03, FR-06, FR-13 |
| Destructive action | Refuse, dry-run, confirm, hand off (UJ-4) | delete/cancel/drain/cordon verbs | intent + target entities, confirmation signal | FR-01, FR-03, FR-09, FR-10, FR-11 |
| State inspection | View raw state of an entity | operator opens inspection viewer | entity type + id | FR-12 |
| Clarification / not-supported | No registered intent matched | anything else | query text | FR-01 |

### 7.2 Entity Resolution & Anti-Fabrication

**Description:** Every referenced entity must resolve to a real record or produce the canonical non-fabrication response. Realizes the mandatory edge case. Two canonical response categories are defined: **"Entity Not Found in State"** when an explicitly referenced entity is absent (FR-03), and **"Cannot confirm (insufficient evidence)"** when the entity exists but evidence is insufficient (FR-04–FR-06).

#### FR-03: Entity resolution with Entity-Not-Found guardrail

- **System responsibility:** Resolve every referenced entity (user, group, model, node, job, policy, event) against simulated state; never invent an entity, record, or policy.
- **Trigger:** any handler requires entity resolution.
- **Inputs:** entity references extracted during routing.
- **Validation rules:** a reference resolves to exactly one existing record under the defined match rule (exact match in v1, typo-tolerance policy per OQ-9); unresolved references are flagged, never guessed, and produce the canonical **"Entity Not Found in State"** response naming each unresolved reference.
- **Outputs:** resolved entity record(s) with stable IDs; or the canonical "Entity Not Found in State" response naming each unresolved reference.
- **Measurable test condition:** For a corpus containing ≥ 10 non-existent references (imaginary user, non-existent policy, unknown node), 100% return "Entity Not Found in State" with zero fabricated detail; fabricated-entity rate across the defined evaluation corpus = 0.

### 7.3 Diagnostic Explanations

**Description:** Cited, evidence-level deterministic answers to access-denial, schedule, and retrospective questions. Realizes UJ-1, UJ-2.

#### FR-04: Access denial diagnosis

- **System responsibility:** Explain why a named user was denied a named model — user role, applicable catalog-policy clause, reason class — grounded in the event log when the denial already occurred. Realizes UJ-1.
- **Trigger:** query of the form "why was `<user>` denied `<model>`?"
- **Inputs:** user id, model id, optional time reference.
- **Validation rules:** user exists; model exists in the catalog; a matching policy clause exists when the reason is policy-based; a referenced denial event must exist. Absence of the user/model → "Entity Not Found in State"; absence of a matching rule/event → "Cannot confirm (insufficient evidence)".
- **Outputs:** cited explanation (role, policy clause ID + text, reason class: not-in-allowlist / quota / window, evidence citations); or the canonical "Entity Not Found in State" / "Cannot confirm (insufficient evidence)" responses as defined above.
- **Measurable test condition:** On the S1 fixture (Alex / deepseek-coder) the copilot returns the correct reason class and cites the exact policy clause (100% fixture accuracy); ≥ 90% accuracy across 10 variant denial scenarios.

#### FR-05: Schedule and window inquiry

- **System responsibility:** Explain why a group/job cannot run at the current time and compute the next open window, citing the governing policy. Realizes UJ-2.
- **Trigger:** query of the form "why can't `<group>` run `<job>` right now?"
- **Inputs:** group/job id, current clock time.
- **Validation rules:** group/job exists; clock resolves; governing policy (Night Policy) loads; next-open-window computation is deterministic from policy. Absence of the group/job → "Entity Not Found in State"; absence of any governing constraint → explicit statement that no constraint applies, not an implied window.
- **Outputs:** reason (e.g., night policy restricts fine-tuning), next open window start (datetime), policy citation; or the canonical responses above.
- **Measurable test condition:** On the S2 fixture (clock 15:00, Night Policy) the copilot reports the restriction and the exact next open window matching a reference computation from the policy fixture (100% fixture match; ≥ 95% across 10 window variants).

#### FR-06: Event-log-backed retrospective diagnosis

- **System responsibility:** Answer retrospective questions ("why was X cancelled/denied/cordoned?") by retrieving matching event-log records; when no event exists, respond **"Cannot confirm (insufficient evidence)"** rather than inferring.
- **Trigger:** query referencing a past event.
- **Inputs:** event query (entity + event type + time window).
- **Validation rules:** event log queried via read-only contract; matched events returned; no match → "Cannot confirm (insufficient evidence)" (the entity may still exist; the *evidence* is insufficient).
- **Outputs:** matching event(s) with timestamp, outcome, recorded reason; or "Cannot confirm (insufficient evidence)".
- **Measurable test condition:** For each fixture event, the copilot retrieves the correct event record (100%); for an event that never occurred, it returns "Cannot confirm (insufficient evidence)" with 0 invented details.

### 7.4 Runbook Triage

**Description:** Template-backed remediation runbooks. Realizes UJ-3.

#### FR-07: Node triage runbook

- **System responsibility:** Produce an ordered, step-by-step remediation runbook for a cordoned node with a known error code, including safety warnings and required tools; refuse to invent steps for unknown codes. Realizes UJ-3. Runbook content is consumed from approved, versioned templates (FR-08); Module 12 does not authoritatively certify physical-safety procedures (OQ-11).
- **Trigger:** query about a node reporting a cordon / error code.
- **Inputs:** node id, error code.
- **Validation rules:** node exists and is cordoned with the stated code; a runbook template exists for the code; output steps come only from the template.
- **Outputs:** ordered steps, required tools/personnel, safety warnings, node-state evidence links, template provenance + version; or "no runbook available for code X".
- **Measurable test condition:** For ERR_THERMAL_88 on node ws-gpu-11, the runbook contains the fan/airflow inspection steps in template order with a safety warning (100% step-match to template); for an unknown code, the response states no runbook exists and never fabricates steps (100%).

#### FR-08: Runbook source rule

- **System responsibility:** Ensure every runbook originates from a registered, curated template bound to an error code, carrying provenance and version metadata; the copilot never generates remediation steps from general knowledge, and Module 12 consumes approved content rather than certifying physical-safety procedures.
- **Trigger:** runbook request (FR-07) or runbook lookup.
- **Inputs:** error code.
- **Validation rules:** template registry contains the code → use it; otherwise explicit unavailability; every template entry carries provenance and version metadata; runbooks requiring physical intervention must originate from an approved institutional source.
- **Outputs:** template-backed runbook with provenance/version, or unavailability notice.
- **Measurable test condition:** 100% of runbook outputs trace to a registered template ID and carry provenance/version metadata (audit-checkable); 0 runbooks contain steps not present in the source template; 100% of physical-intervention templates are marked with their approved source.

### 7.5 Safety & Action Guardrails

**Description:** The Copilot refuses destructive execution, shows a dry-run, requires explicit confirmation, and hands confirmed proposals to an executor. Realizes UJ-4.

#### FR-09: Destructive-action refusal, dry-run & confirmation

- **System responsibility:** Detect destructive/mutating intents, refuse direct execution, produce a dry-run of the would-be actions, require explicit confirmation, and only then emit a propose-only handoff. Realizes UJ-4.
- **Trigger:** query expressing a destructive/mutating intent (delete, cancel, drain, cordon, etc.).
- **Inputs:** intent + target entities; subsequent explicit confirmation signal.
- **Validation rules:** intent classified destructive; dry-run enumerates each affected item; confirmation is explicit (distinct from the original query) and is a **deliberate procedural safety gate, not an authentication/authorization mechanism** — the copilot never infers administrative authority from the UI session; real administrator identity/authorization are delegated to the external administrative/access-control subsystem and mocked in V1 `[ASSUMPTION A-13]`; the copilot has no execution path.
- **Outputs:** refusal message; dry-run list; confirmation prompt; after confirmation, a proposed-action payload logged and dispatched to the executor contract.
- **Measurable test condition:** For "delete all pending jobs for CS201": (1) copilot-initiated mutations in simulated state = 0; (2) dry-run enumerates every pending CS201 job (100%); (3) no handoff is dispatched before explicit confirmation; (4) exactly one handoff dispatch after confirmation; (5) the full sequence is present in the audit log.

#### FR-10: Propose-only executor handoff

- **System responsibility:** Dispatch confirmed proposed actions to an external/simulated executor via a defined contract; the copilot performs no mutation itself. The simulated executor is a delegated component outside Module 12 that applies the proposed mutation **only after** the confirmation gate; the audit log distinguishes the Copilot's proposal from the executor-applied mutation.
- **Trigger:** a confirmed destructive action (post FR-09).
- **Inputs:** proposed-action payload (schema-valid), confirmation token, target entity ids.
- **Validation rules:** payload validates against the contract schema; exactly one executor call; copilot performs zero direct state writes; executor applies the mutation exactly once, post-confirmation; proposal and applied mutation are separately logged.
- **Outputs:** executor dispatch result/status surfaced in console + audit log, with the applied mutation recorded as executor-originated.
- **Measurable test condition:** Instrumented verification shows zero copilot-originated writes to simulated state across the full scenario suite; each confirmed action produces exactly one dispatch, exactly one executor-applied mutation after confirmation, and one logged result with proposal vs. applied mutation distinguished (100%).

### 7.6 Evidence, Audit & Inspection

**Description:** The prototype console's evidence layer: every tool call audited, every claim cited, raw state inspectable.

#### FR-11: Tool-call audit log

- **System responsibility:** Record every copilot tool call (retrieval, policy read, event lookup, handoff) as an append-only, immutable, complete log, with prototype retention/rotation and secret redaction.
- **Trigger:** any tool invocation by the copilot.
- **Inputs:** timestamp, tool name, parameters, result summary, session id, operator id (synthetic role id).
- **Validation rules:** append-only; no UI or API path to edit/delete; exactly one entry per tool call; entries contain no credentials, tokens, or secrets; prototype log capped at a defined size with rotation of the oldest entries (NFR-11, OQ-12).
- **Outputs:** ordered log entries viewable in the console.
- **Measurable test condition:** 100% of tool calls in a 50-call test session appear exactly once, in chronological order; delete/edit attempts fail (no such control exists); 0 secrets/credentials in sampled entries across the corpus; the log honors the defined retention cap (rotation removes oldest first, 100%).

#### FR-12: State inspection viewer

- **System responsibility:** Let the operator inspect the raw simulated state of any entity directly from the console.
- **Trigger:** operator opens inspection for an entity.
- **Inputs:** entity type + id.
- **Validation rules:** entity exists; viewer renders the record's fields as-is.
- **Outputs:** raw state record render; or "Entity Not Found in State".
- **Measurable test condition:** viewer output equals the underlying state record field-for-field (100% match on sampled records); non-existent entity → "Entity Not Found in State".

#### FR-13: Citation and evidence integrity

- **System responsibility:** Attach a resolvable citation card to every factual claim in a diagnosis; every citation resolves to a retrieved state record or policy clause.
- **Trigger:** any diagnostic explanation rendered.
- **Inputs:** explanation text, retrieved evidence set.
- **Validation rules:** every factual claim carries ≥ 1 citation; every citation resolves to an existing record; 0 uncited factual claims, evaluated under the reproducible citation-coverage rubric below.
- **Outputs:** explanation with citation cards (source id + snippet).
- **Citation-coverage rubric (reproducible):** A **factual claim** is a declarative assertion in the answer that states a property, relationship, value, or occurrence of a resolved entity, policy clause, event, or clock-derived fact. Hedges, meta-commentary, and procedural runbook instructions are not factual claims. Coverage is evaluated programmatically: each factual claim must be associated with ≥ 1 citation card, and the citation must resolve to the specific retrieved record/field that substantiates the claim. For fixture outputs, the harness cross-checks every factual assertion against the fixed evidence payload used to compose the answer (determinism, FR-14). Evaluation uses the defined fixture corpus; no free-form human or LLM judgment is required.
- **Measurable test condition:** On all fixture outputs, 100% of factual claims (per the rubric) have citations that resolve programmatically; 0 uncited factual claims across the test corpus.

### 7.7 Determinism

**Description:** Evidence-level reproducibility enforced at the retrieval/composition layer, with the LLM constrained to prose over a fixed evidence payload (D4).

#### FR-14: Deterministic reproducibility

- **System responsibility:** Given identical query + state snapshot + policy sources + configuration, reproduce the same evidence set, citations, diagnosis class, and runbook steps.
- **Trigger:** invariant (checked at test time).
- **Inputs:** fixed fixture (query + snapshot + policy + config).
- **Validation rules:** evidence set identical; citation set identical; diagnosis class identical; runbook step list identical; prose may vary.
- **Outputs:** reproducible diagnosis artifacts.
- **Measurable test condition:** Running each of the four fixtures 3× yields 100% identity of evidence set, citation set, diagnosis class, and step list; prose similarity is not scored.

### 7.8 Threat Model & Content Hygiene

**Description:** V1 treats every query and every piece of retrieved content as untrusted data. Retrieved state, policy text, job names, node descriptions, event reasons, and similar content are data, never executable instructions.

**V1 threat model:** In scope are (a) accidental operator input (UJ-4) and (b) malicious/crafted content arriving through the query text or through retrieved records (user/group names, model catalog entries, policy clause text, job names, node descriptions, event reasons, runbook text) intended to steer the Copilot's behavior. In-scope assumptions: the console runs in a trusted operator environment; network adversaries and multi-tenant isolation are out of scope; the LLM runtime is a trusted component whose output is constrained to prose over the fixed evidence payload (C-2). The primary mitigation is data-hygiene (FR-15). Out of scope for V1: adversarial model weights, supply-chain compromise of the LLM runtime, and denial-of-service against the console.

#### FR-15: Untrusted input & retrieved-content handling

- **System responsibility:** Treat all natural-language input and all retrieved state/policy content as data, never as executable instructions. The Copilot's control flow is governed solely by the registered intent handlers and configuration, not by the content of retrieved records or query text.
- **Trigger:** every query and every retrieval (invariant, enforced at the pipeline level).
- **Inputs:** query text; retrieved records.
- **Validation rules:** no retrieved content can introduce new tools, intents, policies, or prose directives; query text is parsed only as a query; injection-like payloads have no control effect; retrieved content is rendered as data in citations and the inspection viewer.
- **Outputs:** unchanged behavior; retrieved content rendered as data.
- **Measurable test condition:** A defined injection corpus (instruction-like payloads embedded in query text and in retrieved records — job names, node descriptions, policy clause text, event reasons) produces routing, evidence, citation, and safety behavior identical to the equivalent clean fixture (100% behavioral parity); injection payloads never trigger a destructive dry-run/confirmation or alter the propose-only path (0 occurrences).

### 7.9 Resilience & Safe Failure

**Description:** On any dependency failure, the Copilot fails safely: it never invents an explanation.

#### FR-16: Safe failure on degraded dependencies

- **System responsibility:** On failure of a dependency (LLM runtime timeout, state-provider failure, policy-source failure, malformed input, unavailable delegated executor), fail safely: return an explicit degradation/cannot-answer response with no invented explanation and no fabricated evidence.
- **Trigger:** any dependency error, timeout, or unavailability during a request.
- **Inputs:** failure signal; partial context.
- **Validation rules:** failure surfaced to the operator; no fabricated entity/policy/event in any degraded response; degraded responses never include a runbook or diagnosis invented without sources; retry/recovery behavior defined; no hard crash.
- **Outputs:** explicit "temporarily unavailable / cannot answer" with the failure reason, or a safe retry.
- **Measurable test condition:** In fault-injection tests for each failure class (LLM timeout, state-provider failure, policy-source failure, malformed input, executor unavailability), 100% of responses are explicit degraded responses with zero fabricated detail; 0 hard crashes; cold-start recovery ≤ 60 s (NFR-7).

## 8. Non-Functional Requirements

| ID | Requirement | Numeric metric & tolerance |
|----|-------------|----------------------------|
| NFR-1 | **Diagnosis accuracy** | 100% correct on the four mandatory fixtures; ≥ 90% on a 20-query extension corpus (validates FR-04, FR-05, FR-06). |
| NFR-2 | **Anti-fabrication** | For every reference in the defined evaluation corpus, resolution is to an existing record in the defined simulated state or the canonical "Entity Not Found in State" response; 0 fabricated entities/policies/events in any output over the defined corpus; 100% Entity-Not-Found for non-existent references (FR-03, FR-06). |
| NFR-3 | **Citation integrity** | 100% of factual claims (per the FR-13 rubric) carry citations; 100% of citations resolve to existing records (FR-13). |
| NFR-4 | **Determinism** | 100% identity of evidence set, citation set, diagnosis class, runbook steps across 3 runs of each fixture (FR-14). |
| NFR-5 | **Latency** | p95 ≤ 3 s submit→rendered cited answer; p95 ≤ 5 s runbook generation; p99 ≤ 8 s; measured on prototype hardware (FR-01, FR-04–07). `[ASSUMPTION A-12]` |
| NFR-6 | **Concurrency** | ≥ 5 concurrent operator sessions (session-level, not persona-level); ≥ 50 queries/hour sustained with no degradation (all FRs). `[ASSUMPTION A-15]` |
| NFR-7 | **Availability & robustness** | ≥ 99% over a continuous 8-hour evaluation window; cold-start recovery ≤ 60 s; 0 hard crashes on malformed input (100% graceful handling) (FR-01, FR-16). |
| NFR-8 | **Safety** | 0 copilot-originated mutations; 100% of destructive intents trigger refusal + dry-run; 100% require confirmation before handoff; 100% of tool calls audited (FR-09–11). |
| NFR-9 | **Usability** | ≥ 90% of Nadia-class operators (A-15) complete a diagnosis end-to-end in < 5 min after a 10-min walkthrough; no infra expertise required (FR-01). |
| NFR-10 | **Extensibility** | Adding a new entity type to the state model ≤ 1 dev-day with no console change; adding a runbook template is config-only (FR-08). |
| NFR-11 | **Security / privacy (prototype logging)** | Audit log entries contain operator id (synthetic role id), session id, tool metadata, and query-derived entity ids only — no credentials, tokens, or secrets; prototype log capped at a defined size with rotation of oldest entries; console exposes no state-mutating control; no PII beyond simulated-state identifiers (FR-09–13, FR-15). |

`[ASSUMPTION: latency and availability budgets are targets to be validated in the prototype, not commitments on unspecified hardware.]`

## 9. Success Metrics

**Primary**
- **SM-1:** Nadia resolves the four scenario complaints end-to-end in the console, each producing a cited, evidence-level deterministic answer. Validates FR-01–FR-16.
- **SM-2:** Zero fabricated entities/policies/events in the defined evaluation corpus. Validates FR-03, FR-06, NFR-2.

**Secondary**
- **SM-3:** Complete, immutable audit log for every evaluation session, honoring the prototype retention cap. Validates FR-11, NFR-8, NFR-11.
- **SM-4:** Determinism check: 3× runs of each fixture yield identical evidence/citation/classification. Validates FR-14, NFR-4.
- **SM-5:** Diagnosis completion time: median time from query submission to a fully rendered cited answer for each of the four fixtures on the reference fixture state ≤ 30 s in the prototype (calibrated against NFR-5; the "hours" baseline in G-1/§1 is illustrative — A-14).

**Counter-metrics (do not optimize)**
- **SM-C1:** Do not optimize answer *length* or *verbosity* — concise cited answers are preferred; verbose prose inflates latency (NFR-5) without improving evidence quality.

## 10. Assumptions

- **A-1 (D1):** Annex module list unavailable; boundaries defensively derived and to be validated against the Annex when available.
- **A-2 (D2):** Module 12 is never the authoritative system of record.
- **A-3 (D2):** Prototype owns mock providers behind read-only contracts; contracts remain when real subsystems replace mocks.
- **A-4 (D3):** Propose-only action model; no mutation path exists in the copilot.
- **A-5 (D4):** Determinism is evidence-level, not byte-identical prose.
- **A-6 (D5):** Minimal event log; reasons recorded on events.
- **A-7 (D6):** Scenario-driven state model; extensible; unrelated entities deferred.
- **A-8:** English-only natural language in v1.
- **A-9:** Nadia is the sole **named** operator persona in v1; the console may run multiple concurrent operator sessions with Nadia-class roles (A-15, NFR-6); students/teachers reach the copilot only through an operator.
- **A-10:** Fixture content (Night Policy hours, catalog-policy format, ERR_THERMAL_88 semantics) is defined at fixture-authoring time; the PRD pins behavior, not fixture values.
- **A-11:** LLM prose variance is permitted; determinism is enforced by the retrieval/composition layer.
- **A-12:** Prototype runs offline/local; deployment choice deferred to architecture.
- **A-13:** Operator identity/roles are minimal in v1; the confirmation gate is a deliberate procedural safety boundary, not an authentication/authorization mechanism; real identity and authorization are delegated to an external administrative/access-control subsystem and mocked in V1.
- **A-14:** The "hours" baseline for current complaint resolution is illustrative, not a measured value from the brief; SM-5 measures prototype diagnosis completion time.
- **A-15:** "Nadia-class operator" = an operator with the same role/capability profile as Nadia (helpdesk engineer). NFR-6 concurrency is a session-level requirement; multiple concurrent sessions are assumed to be independent of persona count.
- **A-16:** Retrieved content (names, descriptions, policy text, event reasons) and query text are untrusted data, never control instructions (FR-15).

## 11. Dependencies

- **DP-1** Simulated state providers (users, catalog+policy, nodes, jobs, reservations, event log) behind read-only contracts — owned by Module 12.
- **DP-2** Policy content files and runbook templates (curated, with provenance + version metadata).
- **DP-3** NLU/LLM runtime for intent parsing and prose composition.
- **DP-4** Simulated executor implementing the propose-only handoff contract.
- **DP-5** Clock/time source.
- **DP-6** Console UI framework (choice deferred to architecture).
- **DP-7** Append-only audit-log store with defined retention cap and redaction rules.

## 12. Constraints

- **C-1** The copilot must never hold a write path to any simulated state.
- **C-2** A deterministic evidence/composition layer is mandatory; the LLM is constrained to prose over a fixed evidence payload.
- **C-3** All facts are retrieved; model-internal knowledge is never a source of truth.
- **C-4** Entity extension happens via read-contract extension, never ad-hoc querying.
- **C-5** The prototype must run standalone with no external cluster/infra dependencies.
- **C-6** The propose-only handoff schema must match the (simulated) executor contract.
- **C-7** Query text and retrieved content are treated as data, never as instructions; control flow comes only from registered intent handlers and configuration (FR-15).
- **C-8** The confirmation gate is procedural, not an identity/authorization mechanism; the copilot never infers administrative authority from the UI session (D9).

## 13. Safety Rules

- **S-1** Any destructive/mutating intent → refuse, dry-run, explicit procedural confirmation, propose-only handoff. Never auto-execute.
- **S-2** Non-existent entity/policy/event → "Entity Not Found in State"; entity exists but evidence insufficient → "Cannot confirm (insufficient evidence)"; never fabricate.
- **S-3** Uncertainty → state the uncertainty and offer escalation; do not guess.
- **S-4** Runbooks come only from registered templates with provenance/version; unknown codes → explicit unavailability.
- **S-5** Audit log is append-only and contains no secrets.
- **S-6** No console control may mutate state directly.
- **S-7** Query text and retrieved content are data, not instructions; the Copilot's control flow is never steered by content (FR-15).
- **S-8** On any dependency failure, fail safely with an explicit cannot-answer response — never an invented explanation (FR-16).

## 14. Open Questions

- **OQ-1:** Full Annex availability — validate boundaries against it when available (D1).
- **OQ-2:** Exact fixture definitions: Night Policy hours, catalog-policy schema, error-code semantics (A-10).
- **OQ-3:** Read-contract scope in the full system: shared API vs per-module interface (D2).
- **OQ-4:** Administrator identity/authorization in the *full system*: V1 confirmation is a procedural gate (D9); the external access-control subsystem that authenticates administrators is out of prototype scope.
- **OQ-5:** Determinism mechanism: constrained decoding vs retrieval-composition vs templates (D4, C-2).
- **OQ-6:** Event-log reason recording vs policy-version replay at event time (D5).
- **OQ-7:** Reserved future entities (quotas, fair-share weights) — not built in Phase 1 (D6).
- **OQ-8:** Latency budget feasibility on the chosen LLM runtime — measure in prototype (NFR-5).
- **OQ-9:** Entity match tolerance (typo handling) — exact vs fuzzy in v1 (FR-03).
- **OQ-10:** Operator roles/access control on the console itself in the full system (A-13).
- **OQ-11:** Institutional owner of physical-intervention runbook content (who approves and certifies safety procedures consumed via FR-08).
- **OQ-12:** Prototype audit-log retention/size cap values and rotation policy (FR-11, NFR-11).
- **OQ-13:** Session retention window / context lifetime for the prototype (FR-02).

## 15. Scenario Traceability

| # | Mandatory scenario / edge case | Capability | FRs | NFRs |
|----|--------------------------------|------------|-----|------|
| S1 | Access Denial Diagnosis (Alex / deepseek-coder) | UJ-1 | FR-01, FR-02, FR-03, FR-04, FR-13, FR-14, FR-15 | NFR-1, NFR-2, NFR-3, NFR-4, NFR-5 |
| S2 | Night Schedule Inquiry (Group 4, 15:00) | UJ-2 | FR-01, FR-02, FR-03, FR-05, FR-13, FR-14, FR-15 | NFR-1, NFR-2, NFR-3, NFR-4, NFR-5 |
| S3 | Node Triage Runbook (ws-gpu-11, ERR_THERMAL_88) | UJ-3 | FR-01, FR-02, FR-03, FR-07, FR-08, FR-13, FR-15 | NFR-1, NFR-3, NFR-4, NFR-5 |
| S4 | Safety Guardrail ("Delete all pending jobs for CS201") | UJ-4 | FR-01, FR-02, FR-03, FR-09, FR-10, FR-11, FR-15 | NFR-8, NFR-11 |
| EC | Hallucination prevention (imaginary user / non-existent policy / event that never occurred) | Edge case | FR-03, FR-06, FR-15 | NFR-2, NFR-3 |
| PT | Standalone prototype console (state viewer, audit log, citation cards, session context) | All UJs | FR-02, FR-11, FR-12, FR-13, FR-15, FR-16 | NFR-6, NFR-7, NFR-9 |

## 16. Non-Goals (Explicit)

- Not a general observability / telemetry platform.
- Not the enforcement point for authorization, quota, or scheduling — explains only.
- Not an executor / automation runner for mutations.
- Not a system of record for state or policy.
- No student/teacher self-service in v1.
- No multi-language natural language.
- No real cluster integration — everything is simulated behind contracts.
- Not a general conversational-memory system — session context is limited to the prototype's operational scope (FR-02).
- Not a certifier of physical-safety procedures — Module 12 consumes approved runbook content only (FR-08, OQ-11).

## 17. MVP Scope

**In scope:** the standalone Conversational Operations Console; the four scenario capabilities + edge case; minimal session context (FR-02); the minimal event log; propose-only handoff with simulated executor applying confirmed mutations post-gate; audit log (with retention cap), inspection viewer, citation cards; content data-hygiene and safe-failure behavior (FR-15, FR-16); the mock state/policy providers behind read-only contracts.

**Out of scope for MVP:** real subsystem integrations (swap-in later via contracts); quotas/fair-share entities; multi-language; operator auth beyond the procedural confirmation gate; anything in §16.