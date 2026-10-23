---
name: AI Operations Copilot — Conversational Operations Console
status: final
sources:
  - {planning_artifacts}/prds/prd-plan-2-university-ai-fabric-2026-09-27/prd.md
  - docs/module_profile.md
updated: 2026-09-28
---

# AI Operations Copilot — Experience Spine

> Desktop-first responsive web. Administrative/observability console for lab helpdesk operators. No UI framework named (`DP-6` deferred to architecture) — this spine and `DESIGN.md` are framework-agnostic contracts. Paired spine: `DESIGN.md`. The experience is an **operations console with conversational investigation**, never a generic ChatGPT clone.

## Foundation

Desktop-first responsive web, data-dense, single application. Primary actor: a **Nadia-class operator** — moderately technical, trained on the console, no Kubernetes/infrastructure expertise required, working mid-shift with someone waiting (PRD §3, UJ-1–UJ-4; `A-15`, `NFR-9`). English-only in v1 (`A-8`). Operator identity/roles are minimal: the confirmation gate is a **procedural safety boundary, not an authorization mechanism** (`A-13`, `C-8`) — the UI must never imply administrative authority from seeing the confirmation control.

`DESIGN.md` is the visual identity reference. This spine is the experience: how the console behaves, states, and stays honest.

## Information Architecture

Four core surfaces, composed into a three-pane instrument on desktop:

| Surface | Reached from | Purpose |
|---|---|---|
| Console (conversation) | App open (default) | Thread + composer + answer anatomy (diagnosis, evidence, runbook, delegation) |
| State Inspection Viewer | Entity chip / citation card / audit row / left-rail browser | Read-only raw state of any entity, field-for-field (`FR-12`) |
| Tool-Call Audit Log | Answer header `Audit trail` / right-panel Audit tab | Append-only record of every copilot tool call (`FR-11`) |
| Safety / Confirmation | Only via a destructive intent | Refusal → dry-run → explicit confirmation → proposed delegated action → executor result → audit result |

Left rail (240px): sessions + entity quick-nav grouped by store (Users & Roles, Model Catalog & Access Policies, Nodes, Jobs/Queue, Groups, Reservations & Policy Windows, Events). Right inspector (380px): three tabs — **Evidence** (citation cards for the focused answer), **Inspector** (raw state of the focused entity), **Audit** (tool calls for the focused answer/session).

Surface closure: every stated need (query, inspect, audit, confirm) has a surface; every surface is reached by at least one journey (Key Flows). The destructive **flow** (refusal banner, dry-run panel, delegation card) renders inline in the console thread for scope visibility; only the **confirmation dialog** is a distinct surface — it never lives on the Console alone (D17).

→ No mockups in this run; the spines are the visual reference. **Spines win on conflict.**

## Voice and Tone

Microcopy. Brand voice lives in `DESIGN.md` Brand & Style. The voice here is **technical, calm, precise** — the operator relays these words to a professor.

| Do | Don't |
|---|---|
| `Access to deepseek-coder is denied for role student by policy clause policy#catalog.4.2.` | `Uh oh! Looks like Alex hit a snag with permissions.` |
| `Entity Not Found in State: "alexx", "deepseek-coder".` | `We couldn't find that user. Maybe try a different name?` |
| `Cannot confirm (insufficient evidence): no denial event for Alex on 2026-09-25.` | `It's likely the system denied access due to policy.` |
| `Provider unavailable — cannot answer. Your query is not lost.` | `Something went wrong. Please try again later.` |
| `Action refused. The Copilot performs no mutations.` | `I'm not allowed to do that.` |
| `Confirm & propose to executor. This confirms a proposal for delegation; it does not grant authorization.` | `Confirm deletion` |
| Use canonical response strings verbatim (`FR-03`–`FR-06`). | Paraphrase, hedge, or soften the canonical strings. |

Rules: no exclamation marks, no emoji, no encouragement, no invented certainty. Uncertainty is stated with the same composure as certainty (`S-3`).

## Answer Anatomy (evidence before persuasion)

Every copilot answer is assembled from **labeled layers**, rendered top-down. This is the core behavioral contract.

1. **Answer chain** — `Observation → Evidence → Diagnosis → Recommendation → Proposal → Execution`, rendered as chips (`DESIGN.md` answer chain). Populated stages are filled; the diagnosis stage is emphasized; unpopulated later stages are muted. The chain never skips a stage and never renders a stage the system did not reach.
2. **Diagnosis card** — the only component allowed to state a diagnosis. Rendered **only** when the system established one from retrieved evidence (`FR-04`–`FR-06`). If evidence is insufficient, the Diagnosis stage is **not** populated and the card is replaced by the canonical response.
3. **Evidence strip** — observation + evidence: the retrieved records and policy clauses, each with citation cards. Every factual claim in the diagnosis carries `≥ 1` resolvable citation (`FR-13`).
4. **Recommendation** — runbook steps (template-backed, provenance shown) or "no runbook available for code X" (`FR-07`, `FR-08`).
5. **Proposal → Execution** — appears only for destructive/actionable intents and only through the Safety/Confirmation flow.

**Hard rule:** a diagnosis is never rendered when the system cannot establish one from available evidence. The UI must not let the "Diagnosis" chip appear populated on a `Cannot confirm` answer.

## Component Patterns

Behavioral. Visual specs live in `DESIGN.md` Components.

| Component | Use | Behavioral rules |
|---|---|---|
| Composer | Console, always visible at thread bottom | Submit on Enter, Shift+Enter newline. ≤ 1,000 chars enforced with live count (`FR-01`). Empty submit disabled. |
| Turn (user) | Console | Mirrors the query verbatim in mono-quoted entity chips where entities were resolved. |
| Turn (copilot) | Console | Renders the answer anatomy. Includes an `Audit trail` link header. Never auto-scrolls the page while loading; scrolls once on first render. |
| Answer chain | Every copilot turn header | Six stages in fixed order; never reordered, never skipped; diagnosis chip emphasized only when established. |
| Citation card | Evidence strip | Click → opens source record in Inspector tab. Keyboard: focusable, Enter opens. **Never renders as evidence if the source record cannot be resolved — a broken citation downgrades the answer to `Cannot confirm (insufficient evidence)`** (`FR-03`, `FR-13`). |
| Evidence chip | Diagnosis prose | Inline mono reference; click opens its citation card and Inspector. |
| Status badge | Inspector, audit rows, runbook provenance | Text + icon + color always (`DESIGN.md`). No bare colored dot. |
| Runbook card | Recommendation stage | Steps in template order (`FR-07`). Physical-intervention steps carry the approved-source provenance line (`FR-08`, `OQ-11`). **A template whose physical-intervention steps lack approved-source metadata renders unavailability, not the steps.** Unknown code → `no runbook available for code X`, never invented steps. |
| Refusal banner | Destructive intent start | `Action refused.` + first-stage dry-run entry point. No confirmation control here yet. |
| Dry-run panel | After refusal, before confirmation | Enumerates every affected item with per-item status; header: `This is a proposal, not an action.` |
| Confirmation dialog | After dry-run review | Requires a deliberate confirm distinct from the original query (`FR-09`). Stated scope + count. Never dismissible by the operator as "authorized". |
| Delegation card | After confirmation | Two labeled lines: `Copilot proposal` then `Executor-applied mutation` with result + timestamp (`FR-10`). Distinct visual treatment per `DESIGN.md`. |
| Audit row | Audit tab | Append-only; no edit/delete affordance exists (`FR-11`, `S-5`). Renders tool name + **parameter summary only — no credentials, tokens, or secrets** (`NFR-11`). Click → Inspector. |
| Inspection field | Inspector tab | Renders raw state as-is, field-for-field (`FR-12`). Retrieved content rendered as **data**, never executable (`FR-15`). |
| Entity chip | Prose, Inspector, audit rows | Mono ID; click → Inspector; copies on a dedicated copy control (not on click). |
| Empty state | First session / empty lists | Guidance sentence, one primary action. No celebratory copy. |
| Loading skeleton | In-flight answers | Shaped to answer anatomy; `aria-busy` announced. |
| Provider-unavailable banner | Any in-flight request on dependency failure | `Provider unavailable — cannot answer.` + Retry. No partial fabrication (`FR-16`). |

## State Patterns

All thirteen mandatory states, mapped to surfaces. Canonical strings verbatim.

| State | Surface | Treatment |
|---|---|---|
| Loading | Console, Inspector | Answer-anatomy skeleton; `aria-busy`. Never a partial diagnosis. |
| Empty | Console first session / Inspector empty list | Guidance + one action. |
| Valid diagnosis | Console | Diagnosis card populated + evidence strip + citations. Diagnosis chip emphasized. |
| `Entity Not Found in State` | Console answer, Inspector | Neutral card listing each unresolved reference (mono). Verbatim string. Not an error — correct system behavior (`FR-03`, `FR-12`). |
| Insufficient evidence / `Cannot confirm (insufficient evidence)` | Console answer | Diagnosis stage **unpopulated**; card states what was checked (e.g., no event, no clause) and what is therefore not claimed (`FR-04`–`FR-06`, `S-3`). |
| Provider unavailable | Console (banner), Inspector | `Provider unavailable — cannot answer.` Retry; query retained (`FR-16`). |
| Malformed/invalid input | Console | Clarification prompt; never force-routed to an intent (`FR-01`). Over-length blocked at composer. |
| Delegated service/executor failure | Delegation card | Executor result line shows failure status + reason; proposal line preserved; safe-failure copy, no retry auto-fire (`FR-10`, `FR-16`). |
| Rejected/destructive action | Confirmation flow | Refusal banner (`Action refused.`) → dry-run panel. |
| Confirmation required | Confirmation flow | Confirmation dialog after dry-run; procedural-gate wording under the button. |
| Proposed action | Delegation card | `Copilot proposal` line; never rendered as executed. |
| Successful delegated execution | Delegation card | `Executor-applied mutation` line with success status + timestamp; proposal and mutation visually distinct (`FR-10`). |
| Audit result | Audit tab | Full append-only sequence for the session/answer; row count + `read-only` marker. |
| Clock/time source failure | Console (schedule diagnosis) | Treated as a safe-failure: `Cannot confirm (insufficient evidence)` or provider-unavailable banner — a window is never fabricated from a failed clock read (`FR-05`, `FR-16`). |
| Empty audit | Audit tab | `No tool calls in this session.` — paged, never infinite-scroll (`FR-11`). |

Cross-cutting rule: **a state is never communicated by color alone** — every state above carries text (and where apt, an icon).

## Interaction Primitives

**Keyboard-first.** The operator works mid-shift with someone waiting; the keyboard is the fast path, the mouse is fallback. All shortcuts are simple (no chords):

- `Enter` — submit in composer; `Shift+Enter` — newline.
- `Tab` — moves in DOM order; focus ring always visible (`DESIGN.md` `{colors.focus-ring}`).
- `[` / `]` — previous / next session in the rail.
- `e` — toggle right panel to Evidence; `i` — Inspector; `a` — Audit.
- `g u` / `g m` / `g n` / `g j` / `g r` — go to Users / Models / Nodes / Jobs / Reservations in the left rail (vim-style, matching the ops-console idiom).
- `c` — focus the composer. `Esc` — close the confirmation dialog (returns to dry-run, never confirms).
- `Enter` on a citation card / entity chip — open in Inspector.

**Pointer:** click citation/entity chips to inspect; a small copy icon copies mono IDs (click-on-chip must *not* copy — it navigates). Hover reveals per-row actions in the Audit tab on `md+`.

**Banned everywhere:** infinite scroll in the audit log (paged only, `FR-11` retention cap respected in display), hover-only affordances on small viewports, drag-to-reorder, modal stacks deeper than one level, and any auto-fire of a destructive handoff.

## Accessibility Floor

Behavioral. Contrast and visual rules live in `DESIGN.md`.

- **WCAG 2.1 AA** across all surfaces, light and dark. All text ≥ 12px; status contrast verified against `{colors.surface-status}` and `{colors.surface-base}` — contrast ratios for the text tokens are recorded in the `DESIGN.md` token table (D18), so the claim is checkable.
- **Never color alone** — every status/state carries text label + icon; verified by the design rule, not by luck.
- **Screen readers:** copilot answer region is `aria-live="polite"` announcing answer stages (`Diagnosis ready`, `Evidence 3 citations`, `Action refused`). Loading skeleton sets `aria-busy="true"`. Canonical strings announced verbatim.
- **Confirmation flow is fully keyboard-operable** and its dialog sets `role="alertdialog"` with `aria-describedby` restating scope. Esc returns to dry-run; the confirm button is reachable but never auto-focused on a destructive control.
- **Focus order matches reading order** on every surface. Focus ring visible on all interactive elements.
- **Reduce Motion:** skeleton uses a subtle pulse at most; no parallax, no slide-in answers. Confirm dialog appears without animation.
- **Copy controls** on mono identifiers are labeled (`Copy node id`) — not icon-only.
- Touch/click targets ≥ 24px minimum; interactive rows ≥ 32px.

## Responsive & Platform

Desktop-first. The full instrument is the target surface; mobile is degraded gracefully, not equal.

| Breakpoint | Behavior |
|---|---|
| `≥ 1280px` | Three-pane instrument: rail + center + inspector. |
| `1024–1279px` | Inspector tabs collapse into the center as a bottom sheet bound to the focused answer/entity. Rail stays. |
| `768–1023px` | Rail collapses to icons; center thread remains primary. |
| `< 768px` | Single column; rails become top-bar menus; confirmation dialog is full-screen modal; dense tables become horizontally scrollable with a sticky first column. |

Never: port the full data-dense instrument to a phone portrait as-is. The inspector and audit remain available via the sheet, but the conversation is the mobile center of gravity.

## Inspiration & Anti-patterns

- **Lifted from Grafana / Datadog / Sentry:** the data-dense instrument posture — mono identifiers, status vocabulary, dense tables, read-only inspection of raw records. Ops operators already read these; Module 12 should feel like a member of the family, not a chat app wearing a clipboard.
- **Lifted from `kubectl describe` / `git status`:** the discipline of showing the operator the raw record plus a human explanation, not the explanation alone.
- **Lifted from ChatGPT/GitHub Copilot conversation affordances:** the thread, follow-up resolution, and session reset — but *only* the conversation mechanics, never the visual skin.
- **Rejected — generic ChatGPT clone:** rounded everything, gradient user bubbles, "Assistant" avatar, celebratory streaming states. This is an instrument.
- **Rejected — implying authorization via the confirmation control:** the confirm button must read as a procedural gate (`C-8`, `A-13`), never as "I am admin so I may." The caption under the confirm button is load-bearing, not flavor.
- **Rejected — decorative streaming / typing animation:** the loading skeleton is shaped to the answer anatomy so the operator can plan, not watch a cursor blink.

## Safety & Confirmation Model

The destructive-action path is a **state machine with a fixed, visible order** (`S-1`):

`Request → Refusal → Dry run → Explicit confirmation → Proposed delegated action → Executor result → Audit result`

- **Request** — any destructive/mutating intent (delete, cancel, drain, cordon…) enters this flow. The console classifies the intent; the Composer never offers a destructive verb as an action button.
- **Refusal** — `Action refused.` banner. No mutation performed. `0` copilot-originated mutations is an invariant (`NFR-8`).
- **Dry run** — enumerates every affected item before any confirmation. The scope of the action is fully visible before anything is proposed (`UJ-4` climax).
- **Explicit confirmation** — a deliberate second operator action distinct from the original query (`FR-09`). It is a **procedural safety boundary**, not identity/authorization. The UI states this. A second confirm still cannot make the copilot execute — it can only dispatch (`UJ-4` edge case).
- **Proposed delegated action** — propose-only handoff to the (simulated) executor (`FR-10`, `C-6`). Rendered as `Copilot proposal`.
- **Executor result** — the executor applies the mutation exactly once, post-confirmation, and the result is rendered as `Executor-applied mutation` (`FR-10`).
- **Audit result** — the full sequence is present, append-only, proposal distinguished from applied mutation (`FR-11`).

The Copilot **never holds a write path** (`C-1`, `S-6`). No console control mutates state directly. The confirmation dialog's wording is contractually non-authorizing.

Closed edge cases (resolved in this spine):

- **Unresolved destructive target** — if intent classification names a target that does not exist in state, the flow renders `Entity Not Found in State` **before** any dry-run; the dry-run never opens on an unresolved target (`FR-03`, `FR-09`).
- **Empty dry-run** — a destructive intent matching zero items renders a dry-run listing `0 affected items` and **disables confirmation**: there is nothing to propose. Nadia dismisses it; no no-op handoff is ever dispatched (`FR-09`).
- **Stale dry-run snapshot** — the dry-run is a timestamped snapshot. At the confirm moment the console re-validates the affected-item set against current state; if the scope changed, the dialog closes back to a re-rendered dry-run with the delta surfaced, and the operator re-reviews. Confirmation never fires against a stale list (`FR-09`, `FR-10`).
- **Compound queries containing a destructive intent** — a compound query that includes any destructive/mutating verb is never decomposed; it routes to clarification, because decomposition of destructive intent is unsafe (`FR-01`).
- **Provider-independent confirm gate** — the confirmation step is procedural and requires no LLM/provider; a provider outage affects diagnosis stages only. If the executor is unavailable at dispatch, the delegation card renders executor failure (safe-failure, `FR-16`) — the proposal line is preserved and re-dispatch is a deliberate operator action.
- **Double-apply guard** — the delegation card renders the applied-mutation count; `FR-10`'s exactly-once invariant surfaces a second applied record as an executor-failure state, never as a second success.
- **Open dialog blocks session switching** — an open confirmation dialog blocks `[`/`]` and rail navigation until dismissed or confirmed; the safety state is never abandoned silently mid-flow.
- **Session reset mid-flow** — reset clears context and cancels any in-flight request; a destructive flow in progress returns to its refusal/dry-run stage and never auto-continues after reset (`FR-02`).

## Boundary Contradictions (flagged, not expanded)

Where a UX requirement could read as Module 12 mutating infrastructure or becoming a system of record, the design **flags the contradiction** rather than absorbing the scope. No finding here expands Module 12 past `PRD §2`/`§16`.

- **Inspection of reservations and policy windows** — the Inspector renders these records **read-only**; reservation *management* remains out of scope (`§2.4`). The viewer shows a `read-only` marker on these stores.
- **Job/queue inspection vs. cancellation** — the Inspector and audit show jobs; no control on any surface can cancel/delete directly. Cancellation appears only as a delegated proposal through the Safety flow.
- **Node health/cordon/error codes** — displayed as state; cordon/uncordon and remediation are node-management's job. Runbooks are consumed templates, never copilot-authored steps (`FR-08`).
- **"Successful delegated execution" state** — the success is the *executor's*, logged executor-originated (`FR-10`); the delegation card never renders the mutation as copilot action.
- **Procedural confirmation ≠ authorization** — seeing the confirmation control confers no admin authority (`A-13`, `C-8`); the UI is contractually forbidden from implying it.
- **Retrieved content is data** — citation snippets, policy text, job names, event reasons are rendered bounded and un-styled; nothing rendered becomes a control, link, or instruction (`FR-15`, `S-7`).

## Key Flows

Named protagonists per PRD: **Nadia** (primary), with **Dr. Aris Thorne** and **Mateo** as the complainants behind flows 1–2.

### Flow 1 — Access Denial Diagnosis (UJ-1): Nadia answers "Why was Alex denied deepseek-coder?"

1. Nadia opens the console on the shared lab machine; a student (Mateo) is upset at the counter. The session list is empty; the empty state suggests a sample query.
2. She types `why was alex denied deepseek-coder` and presses Enter.
3. Loading: skeleton shaped to answer anatomy; `aria-busy`; no partial content.
4. The copilot resolves `alex` and `deepseek-coder`; the answer renders. Answer chain: `Observation → Evidence → Diagnosis` filled.
5. The diagnosis card states: role `student`, policy clause `policy#catalog.4.2` denying the model, reason class `not-in-allowlist`. Each factual claim carries an evidence chip.
6. **Climax:** Nadia clicks the citation card for `policy#catalog.4.2`; the Inspector opens the exact clause text. She can point to it.
7. Resolution: she relays the clause to Mateo, closes the session. The Audit tab shows the retrieval calls.
8. **Failure — entity not found:** if Alex or the model did not exist, the answer renders `Entity Not Found in State: "alex", "deepseek-coder"` as a neutral card. Nadia tells Mateo the claim is unverifiable; nothing is invented (`FR-03`).
9. **Failure — insufficient evidence:** if Alex exists but no denial event or policy clause matches, the diagnosis stage is unpopulated; the answer is `Cannot confirm (insufficient evidence)` with what was checked. Nadia relays uncertainty and offers escalation (`S-3`).

### Flow 2 — Night Schedule Inquiry (UJ-2): Nadia answers "Why can't Group 4 run their fine-tuning job right now?"

1. Dr. Aris Thorne sent Nadia a screenshot of a failed launch; it is 15:00.
2. Nadia continues the current session, types `why can't group 4 run their fine-tuning job right now`.
3. Loading skeleton; then the answer renders. Chain: `Observation → Evidence → Diagnosis → Recommendation` (recommendation = next window).
4. The diagnosis cites the Night Policy clause; the answer states the window restriction and computes `next open window: today 20:00–08:00`, citing the clock read.
5. **Climax:** the next-open-window value is rendered in mono as a first-class fact with its own citation — not buried in prose.
6. Resolution: Nadia relays the window to Thorne. No further action.
7. **Failure — no constraint:** if the job has no scheduling constraint, the answer explicitly states no constraint applies and renders **no** window — never an implied one (`FR-05`).
8. **Failure — provider unavailable:** if the policy source or LLM runtime fails, a `Provider unavailable — cannot answer.` banner appears with Retry; no window is computed, nothing fabricated (`FR-16`).

### Flow 3 — Node Triage Runbook (UJ-3): Nadia gets a runbook for ws-gpu-11

1. A monitoring alert surfaces: `ws-gpu-11` cordoned, `ERR_THERMAL_88`.
2. Nadia types `ws-gpu-11 is cordoned with ERR_THERMAL_88. what should i do`.
3. Loading skeleton; answer renders. Chain: `Observation → Evidence → Diagnosis → Recommendation`.
4. Diagnosis card confirms cordon status + error code with citations to the node record. Recommendation renders the runbook card: ordered fan/airflow inspection steps from the registered template, in template order, with a `danger` safety warning and the approved-source provenance line (`FR-07`, `FR-08`).
5. **Climax:** the safety warning and the required-tools step are visible before any action; the provenance line names the approved template + version, so Nadia knows this is sanctioned content.
6. Resolution: Nadia follows the runbook; uncordon remains node-management's job. Physical-safety certification remains the institutional content owner's (`OQ-11`).
7. **Failure — unknown code:** if the code had no template, the recommendation renders `no runbook available for code X` and never fabricates steps (`FR-07`).
8. **Failure — node not found:** if `ws-gpu-11` does not exist in state, `Entity Not Found in State: "ws-gpu-11"`; no runbook is offered.

### Flow 4 — Destructive-action Safety Guardrail (UJ-4): Nadia accidentally types "Delete all pending jobs for CS201."

1. Mid-hurry, testing the console, Nadia types `delete all pending jobs for cs201` and hits Enter.
2. The intent is classified destructive. Loading skeleton; then the refusal banner: `Action refused. The Copilot performs no mutations.`
3. The dry-run panel enumerates every pending CS201 job, each with its job ID and status, and states `This is a proposal, not an action.`
4. **Climax:** the dry-run makes the full scope visible before anything is proposed — Nadia can see exactly what would be affected.
5. Nadia triggers the confirmation dialog. It restates the count and scope; the primary button reads `Confirm & propose to executor`; the caption reads `This confirms a proposal for delegation. It does not grant or assert authorization.`
6. On confirm, a delegation card renders: `Copilot proposal` (payload), then `Executor-applied mutation` with the executor's result and timestamp — visually distinct lines (`FR-10`).
7. The Audit tab shows the full append-only sequence: refusal, dry-run, confirmation, handoff, executor result — proposal and mutation separately logged (`FR-11`).
8. **Failure — executor unavailable:** the delegation card shows `Executor-applied mutation` with a failure status and reason; the proposal line is preserved; no auto-retry fires; the operator can choose to re-dispatch (`FR-16`).
9. **Edge case — double confirm:** a second confirm still cannot make the copilot execute — it can only dispatch. The UI never exposes an execution control (`UJ-4`, `FR-09`).