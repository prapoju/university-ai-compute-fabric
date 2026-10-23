# Wireframe 01 — Primary Operations Console

**Scenario(s):** 01 (Access Denial Diagnosis), 02 (Night Schedule Inquiry), 03 (Node Triage Runbook) — shown here mid-answer for S1.
**Surface:** Conversational Operations Console (three-pane instrument).
**References:** `DESIGN.md` (Layout & Spacing, Components); `EXPERIENCE.md` (Answer Anatomy, Key Flow 1).

---

## 1. Purpose

The operator's primary surface: a conversational investigation instrument. The center thread renders the answer anatomy (answer chain → diagnosis card → evidence strip → runbook/delegation as applicable), while the right panel provides tabbed Evidence / Inspector / Audit context bound to the focused answer, and the left rail provides sessions + entity quick-nav. It is an **operations console with conversational investigation**, never a generic chat app.

## 2. Wireframe

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ⬛ CONSOLE — AI Ops Copilot     │  session: S-102 · operator: nadia-class · [🔍][🌓]  [New session] [⏻] │  <- chrome
├──────────────────┬──────────────────────────────────────────────────────────────┬──────────────────────────┤
│  LEFT RAIL 240px │  CENTER — conversation thread                               │  RIGHT INSPECTOR 380px   │
│  (rail-width)    │  (fluid)                                                     │  (inspector-width)       │
│                  │                                                              │  ┌─[Evidence][Inspector]─┐│
│  SESSIONS         │                                                              │  │ [Audit]      (e/i/a)  ││
│  ─────────        │                                                              │  └───────────────────────┘│
│  ● S-102 today    │  ┌─ turn 1 · user ──────────────────────────────────────┐   │                          │
│  ○ S-099 today    │  │ "why was alex denied deepseek-coder"                  │   │  EVIDENCE  (bound to    │
│  ○ S-088 yesterday│  │   └ entity chips: [alex:user] [deepseek-coder:model]  │   │  focused answer)        │
│  [+ New session]  │  └───────────────────────────────────────────────────────┘   │                          │
│                  │                                                              │  ┌─ citation card ──────┐│
│  ENTITIES         │  ┌─ turn 2 · copilot ────────────────────────────────────┐   │  │ ┌───────────────┐     ││
│  ─────────        │  │  [Audit trail ▸]  [🧭 answer chain]                   │   │  │ │ [S1:user]     │     ││
│  👤 Users & Roles │  │  │ Observation → │EVIDENCE│ │DIAGNOSIS│ ○ Rec ○ Prop  │   │  │ │ user          │     ││
│  📦 Models+Catalog│  │  ┌─ diagnosis card ───────────────────────────────┐   │   │  │ └───────────────┘     ││
│  🖥 Nodes          │  │  │ DIAGNOSIS                                     │   │   │  │  role: "student"       ││
│  📥 Jobs/Queue     │  │  │  Access to deepseek-coder is denied for role   │   │   │  │  [open in Inspector ↗] ││
│  👥 Groups         │  │  │  student by policy#catalog.4.2 [S1:policy]      │   │   │  └──────────────────────┘│
│  📅 Reservations   │  │  │  reason class: not-in-allowlist [S1:model]      │   │   │  ┌─ citation card ──────┐│
│  🏛 Policy         │  │  └─────────────────────────────────────────────────┘   │   │  │ ┌───────────────┐     ││
│  📜 Events         │  │  ┌─ evidence strip ────────────────────────────────┐   │   │  │ │ [S1:policy]   │     ││
│  (g u / g m / g n  │  │  │ OBSERVATION:                                   │   │   │  │ │ policy        │     ││
│   g j / g r ...)   │  │  │  user alex, role student [S1:user]             │   │   │  │ │ policy#catalog.4.2 │ ││
│                  │  │  │  deepseek-coder catalog entry [S1:model]         │   │   │  │ └───────────────┘     ││
│                  │  │  │  denial event evt-4711 [S1:event]                │   │   │  │  "student role is    ││
│                  │  │  └─────────────────────────────────────────────────┘   │   │  │  not in the allowlist ││
│                  │  │                                                       │   │  │  for deepseek-coder"  ││
│                  │  │  [⏎ composer …why was ___ denied?           180/1000] │   │  │  [open in Inspector ↗] ││
│                  │  │                                                       │   │  └──────────────────────┘│
│                  │  │  shortcut hints:  c=composer  [=prev  ]=next  e/i/a   │   │                          │
│                  │  │                   g u/m/n/j/r = entity nav             │   │                          │
│                  └──────────────────────────────────────────────────────────┘   │                          │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Legend / notes:**
- **Answer chain** (🧭): chips `Observation → Evidence → Diagnosis → Recommendation → Proposal → Execution`; filled = reached, the Diagnosis chip emphasized, later stages muted. S1 stops at Diagnosis.
- **Evidence strip** renders retrieved records with `[S1:...]` evidence chips; every chip is clickable → its citation card + Inspector.
- **Right inspector** is the **State/Context panel** — Evidence / Inspector / Audit tabs bound to the focused answer or entity (`e`/`i`/`a`).
- **Audit trail** link on each copilot turn header opens the Audit tab for that answer.
- **Composer** shows a live character count; Enter submits, Shift+Enter newline.
- **Status indicators** are always text+icon+color (e.g., an `●` fault dot is never rendered without its label in dense tables).

## 3. Interaction & State Highlights (see SPECIFICATIONS.md for the full contract)

| Moment | Behavior |
|---|---|
| Submit | Loading skeleton shaped to answer anatomy; `aria-busy="true"`; no partial diagnosis; no auto-scroll until first render. |
| Valid diagnosis | Diagnosis card populated; Diagnosis chip emphasized; evidence strip + citation cards render. |
| `Entity Not Found in State` | Neutral card (not an error) listing unresolved refs in mono; Diagnosis chip **unpopulated**. |
| `Cannot confirm (insufficient evidence)` | Diagnosis stage unpopulated; card states what was checked and what is not claimed. |
| Provider failure | `Provider unavailable — cannot answer.` banner at thread top; query retained; Retry. |
| Runbook answer (S3) | Recommendation stage populated with runbook card (steps, tools, danger warning, provenance). |

## 4. Validation against design constraints

- Three-pane instrument matches `DESIGN.md` rail/inspector widths (240px / 380px); flat surfaces, 1px borders, no decorative elevation.
- Never color alone: every status carries text + icon; mono is reserved for identifiers/payloads (`JetBrains Mono`), prose stays Inter.
- Retrieved content rendered as **data** (mono, bounded, un-styled) — never auto-linked or executable (`FR-15`).
- Keyboard-first shortcuts (`[`/`]`, `e`/`i`/`a`, `g u/m/n/j/r`, `c`, `Esc`) per `EXPERIENCE.md` Interaction Primitives.
- No control on this surface mutates state; the Safety/Confirmation surface (Wireframe 02) owns the destructive flow.