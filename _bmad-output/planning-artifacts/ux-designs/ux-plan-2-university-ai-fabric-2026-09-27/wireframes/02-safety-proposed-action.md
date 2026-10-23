# Wireframe 02 — Safety / Proposed Action Screen

**Scenario(s):** 04 (Destructive-Action Safety Guardrail — "Delete all pending jobs for CS201").
**Surface:** Safety / Confirmation — reached only via a destructive intent; the destructive flow never lives on the Console surface alone.
**References:** `DESIGN.md` (Refusal banner, Dry-run panel, Confirmation dialog, Delegation card); `EXPERIENCE.md` (Safety & Confirmation Model, Flow 4); PRD `FR-09`, `FR-10`, `FR-11`.

---

## 1. Purpose

The safety state machine that makes destructive scope fully visible before anything is proposed, requires an explicit procedural confirmation, and then renders the propose-only handoff with the executor result — with the **Copilot proposal** and the **Executor-applied mutation** kept visibly distinct and fully audited. The UI never implies Module 12 executes anything.

## 2. Wireframe

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ⬛ CONSOLE — AI Ops Copilot     │  session: S-104 · operator: nadia-class · [🔍][🌓]  [New session] [⏻] │  <- chrome
├──────────────────┬──────────────────────────────────────────────────────────────┬──────────────────────────┤
│  LEFT RAIL       │  CENTER — destructive flow (safety state machine)           │  RIGHT INSPECTOR 380px   │
│                  │                                                              │  ┌─[Evidence][Inspector]─┐│
│  SESSIONS         │  1) REFUSAL ─────────────────────────────────────────────┐  │  │ [Audit]      (e/i/a)  ││
│  ● S-104 today   │  │ ⚠ ACTION REFUSED                                     │  │  └───────────────────────┘│
│  ○ S-099 today   │  │  The Copilot performs no mutations.                   │  │  AUDIT  (this answer)    │
│                  │  │  The intent was classified destructive.               │  │                          │
│  ENTITIES        │  │  ▸ [Review the dry-run →]                             │  │  ┌─ audit rows ─────────┐│
│  👤 Users & Roles│  │  └───────────────────────────────────────────────────┘  │  │  │ 09:15:02 intent:…    ││
│  📦 Models+Catalog│  │                                                       │  │  │   classify destructive││
│  🖥 Nodes        │  │  2) DRY-RUN ──────────────────────────────────────────┐  │  │  │ 09:15:03 jobs.list   ││
│  📥 Jobs/Queue   │  │  │ ⚠ THIS IS A PROPOSAL, NOT AN ACTION.              │  │  │  │   params: course=CS201││
│  👥 Groups       │  │  │  Snapshot: 2026-09-27T09:15:03Z (re-validated)     │  │  │  │   → 3 pending jobs   ││
│  📅 Reservations │  │  │  ┌ affected items (3) ─────────────────────────┐  │  │  │  │ 09:15:11 confirm:…   ││
│  🏛 Policy       │  │  │  │ [job#job-8821]  pending   │ CS201          │  │  │  │  │   procedural gate    ││
│  📜 Events       │  │  │  │ [job#job-8822]  pending   │ CS201          │  │  │  │  │ 09:15:12 handoff:…   ││
│                  │  │  │  │ [job#job-8823]  pending   │ CS201          │  │  │  │  │   executor.dispatch  ││
│                  │  │  │  └──────────────────────────────────────────────┘  │  │  │  │ 09:15:15 executor…   ││
│                  │  │  │  [Confirm & propose to executor]  [Dismiss]        │  │  │  │   applied (3)        ││
│                  │  │  └───────────────────────────────────────────────────┘  │  │  └──────────────────────┘│
│                  │  │                                                       │  │  read-only · paged      │
│                  │  │  ⚠ awaiting re-validation: dry-run snapshot at 09:15:03│  │                          │
│                  │  └───────────────────────────────────────────────────────┘  │                          │
├──────────────────┴──────────────────────────────────────────────────────────────┴──────────────────────────┤
│  3) CONFIRMATION DIALOG  (role=alertdialog · modal overlay, gravity shadow)                                  │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  ⚠ Confirm proposal to executor                                                                      │  │
│  │  This will propose deleting 3 pending jobs for CS201: [job-8821] [job-8822] [job-8823].              │  │
│  │  A dry-run snapshot taken at 09:15:03 was re-validated — scope unchanged.                             │  │
│  │                                                                                                      │  │
│  │            [Cancel (Esc)]      [ ⚠ Confirm & propose to executor ]                                   │  │
│  │                                                                                                      │  │
│  │  caption: This confirms a proposal for delegation. It does not grant or assert authorization.         │  │
│  └────────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
├──────────────────┬──────────────────────────────────────────────────────────────┬──────────────────────────┤
│                  │  4) DELEGATION CARD (post-confirm) ─────────────────────────┐  │  AUDIT (final)          │
│                  │  │  ✅ Copilot proposal — handoff dispatched 09:15:12      │  │  … full append-only      │
│                  │  │  │  payload (propose-only): { action: delete, target:    │  │  sequence with proposal  │
│                  │  │  │    [job-8821, job-8822, job-8823], gate: confirmed }  │  │  vs. mutation distinct   │
│                  │  │  ✅ Executor-applied mutation — 09:15:15, applied 3 of 3  │  │  (read-only marker)      │
│                  │  │  │  source: executor (logged executor-originated)         │  │                          │
│                  │  │  └───────────────────────────────────────────────────────┘  │                          │
│                  │  └───────────────────────────────────────────────────────────┘  │                          │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Legend / notes:**
- **The destructive flow is a fixed state machine** (Request → Refusal → Dry-run → Explicit confirmation → Proposed delegated action → Executor result → Audit result) and is never collapsed into a single "delete" button.
- **Proposal vs. mutation are visually distinct, labeled lines**: `Copilot proposal` (propose-only payload) vs. `Executor-applied mutation` (executor-originated result + timestamp). A success never reads as a Copilot action (`FR-10`).
- The **confirmation dialog** is a modal `alertdialog` with the procedural-gate caption under the button (`D9`, `C-8`); Esc returns to the dry-run, never confirms.
- **Dry-run snapshot is timestamped and re-validated at confirm**; a scope delta re-opens the dry-run (`UX-03`).
- An open confirmation dialog blocks session/rail navigation (`UX-07`).

## 3. Interaction & State Highlights

| Moment | Behavior |
|---|---|
| Destructive intent classified | Loading skeleton → refusal banner `Action refused. The Copilot performs no mutations.` |
| Unresolved target | `Entity Not Found in State` renders **before** any dry-run; dry-run never opens on a phantom target (`UX-01`). |
| Empty affected set | Dry-run shows `0 affected items` and **disables confirmation**; no no-op handoff (`UX-02`). |
| Confirmation | Explicit, distinct from the original query; procedural gate; provider-independent (`UX-05`). |
| Executor unavailable | Delegation card: `Executor-applied mutation` failure status + reason; `Copilot proposal` line preserved; no auto-retry; re-dispatch deliberate (`FR-16`). |
| Double apply | Applied-mutation count rendered; a second applied record surfaces as executor-failure, never as a second success (`UX-06`). |
| Final / audit | Audit tab shows the full append-only sequence with proposal vs. mutation separately logged; zero secrets (`FR-11`, `NFR-11`). |

## 4. Validation against design constraints

- **Module 12 never executes**: no console control mutates state; confirmed proposals are dispatched to the (simulated) executor contract; the Copilot holds no write path (`C-1`, `S-6`).
- **Confirmation is procedural, not authorization**: the dialog caption is contractually non-authorizing (`A-13`, `C-8`); a second confirm can only dispatch, never execute (`UJ-4`).
- **Retrieved content rendered as data**: job IDs, course names, payloads are mono, bounded, un-styled (`FR-15`).
- **Auditability**: the audit log distinguishes the Copilot's proposal from the executor-applied mutation, append-only, no edit/delete affordance (`FR-11`).
- Never color alone: danger surfaces always carry the ⚠ icon + explicit wording.