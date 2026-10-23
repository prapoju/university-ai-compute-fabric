# Module 12 — UX Specifications ([P])

**Surface specifications for the four core screens of the Conversational Operations Console.**
**References:** visual contract `DESIGN.md` (tokens: colors / typography / rounded / spacing / components); behavior contract `EXPERIENCE.md` (Answer Anatomy, Component Patterns, State Patterns, Interaction Primitives, Accessibility Floor, Responsive). All token names below resolve to `DESIGN.md`.

Four surfaces, per `EXPERIENCE.md` Information Architecture:

| # | Surface | Reached from | Role |
|---|---------|--------------|------|
| S-A | Console (conversation) | App open (default) | Thread + composer + answer anatomy |
| S-B | State Inspection Viewer | Entity chip / citation card / audit row / left-rail browser | Read-only raw state, field-for-field (`FR-12`) |
| S-C | Tool-Call Audit Log | Answer header `Audit trail` / right-panel Audit tab | Append-only tool-call record (`FR-11`) |
| S-D | Safety / Confirmation | Only via a destructive intent | Refusal → dry-run → explicit confirmation → delegation → executor result → audit |

**Design loop:** [C] conceptualize → wireframes (`wireframes/01-primary-operations-console.md`, `wireframes/02-safety-proposed-action.md`) → [P] these specifications → [V] `VALIDATION.md`. No unnecessary screens invented; S-A, S-B, S-C are the three-pane instrument; S-D is reached only by destructive intent.

---

## S-A — Console (Conversation)

### Layout and hierarchy

Three-pane instrument on desktop (`≥ 1280px`): left rail 240px (`spacing.rail-width`), fluid center thread, right inspector 380px (`spacing.inspector-width`). 12-column grid above 1200px with fixed rails and fluid center. Panels anchor by tone and 1px borders — no ambient shadows (elevation only for the confirmation dialog and the scrolled tab bar).

Hierarchy within a copilot turn (top-down, fixed):
1. Turn header: `Audit trail ▸` link + answer chain chips.
2. Diagnosis card (only when a diagnosis is established).
3. Evidence strip (retrieved records + citation cards).
4. Recommendation (runbook card / next-window value) when applicable.
5. Proposal → Execution (S-D only).
6. Composer (always at thread bottom).

### Components

- Composer (`{colors.surface-raised}`, `{colors.border-strong}`, `{colors.rounded.md}`), `body` text.
- Turn (user): mirrors the query verbatim; resolved entities rendered as entity chips (mono).
- Turn (copilot): renders the answer anatomy; `Audit trail` header link.
- Answer chain: six chips in fixed order (`Observation → Evidence → Diagnosis → Recommendation → Proposal → Execution`), `{typography.label}` all-caps, `rounded.full`.
- Diagnosis card (`surface-raised`, hairline border) — the only component allowed to state a diagnosis.
- Evidence strip: citation cards + inline evidence chips.
- Citation card (`surface-evidence`, `evidence-accent` border, `rounded.md`).
- Entity chip (`rounded.full`, mono ID, clickable → Inspector; dedicated copy control).
- Runbook card (S3): numbered steps, tools, danger warning strip, provenance line.
- Status badge: dot + text + icon (never color alone).
- Loading skeleton (`skeleton` blocks shaped to answer anatomy).
- Empty state (headline + caption + one action).
- Provider-unavailable banner (`surface-warning` + `warning` border).

### Component states

| Component | States |
|---|---|
| Composer | default / focus (focus-ring) / disabled (empty or over-limit) / error hint at >1000 chars |
| Citation card | default / hover / focus / (never renders if the source record is unresolvable — answer downgrades) |
| Entity chip | default / hover / focus / (copies only via labeled copy control) |
| Answer chain chips | populated (filled) / current stage (filled + emphasized) / not-reached (muted) |
| Diagnosis card | populated / absent (replaced by canonical response) |
| Runbook card | valid (steps render) / unavailability (`no runbook available for code X`) / provenance-missing (unavailability) |
| Status badge | always dot + text + icon; no dot-only rendering |

### Spacing

`DESIGN.md` scale 4/8/12/16/24/32. Page padding `spacing.5` horizontal; turn gap `spacing.4`; within-card element gap `spacing.3`; dense audit rows `spacing.2` padding; major panel separation `spacing.5`. All controls ≥ 24px targets; interactive rows ≥ 32px.

### Typography usage

- Prose/answers: `typography.body` (Inter 14px, 1.55).
- IDs, codes, timestamps, tool names, payloads: `typography.technical` / `technical-label` (JetBrains Mono) — never anti-aliased below 13px for copyable values.
- Section labels + answer chain: `typography.label` (11px all-caps).
- Card titles: `typography.title`; block titles: `typography.headline`.
- Caption floor 12px; `technical-sm` (11.5px) only for non-critical timestamps/log metadata.

### Status indicators

- Operational states map to `status-available` / `status-reserved` / `status-active` / `status-fault`; each renders as dot + `technical-label` text + icon where apt. Semantic conditions use `warning` / `danger` / `evidence-accent` / `proposal-accent` surfaces — always paired with text (e.g., ⚠ `Action refused.`).
- Uncertainty is a first-class state (`Cannot confirm (insufficient evidence)`) with the same visual weight as a confident answer.

### Button/action labels & triggers

| Control | Label | Trigger |
|---|---|---|
| Composer submit | Enter (keyboard) | Submit query (`FR-01`) |
| New session | `New session` | Creates/resets session (`FR-02`) |
| Citation card | click / Enter | Opens source record in Inspector |
| Entity chip | click / Enter | Opens Inspector (copy via labeled copy control) |
| Audit trail | `Audit trail ▸` | Opens Audit tab bound to the answer |
| Retry (degraded) | `Retry` | Re-submits the retained query (`FR-16`) |

### Navigation behavior

- `[` / `]` — previous / next session. `e`/`i`/`a` — Evidence/Inspector/Audit tab. `g u/m/n/j/r` — entity quick-nav. `c` — focus composer. `Esc` — close dialog (never confirms). Tab in DOM order; focus ring always visible.
- Open confirmation dialog blocks session/rail navigation (`UX-07`).

### Dynamic feedback

- Loading: skeleton + `aria-busy`; no partial diagnosis; no auto-scroll until first render.
- Answer stages announced to screen readers: `Diagnosis ready`, `Evidence 3 citations`, `Action refused`.
- Live character count on the composer.

### Loading behavior

Skeleton shaped to the expected answer anatomy (headline bar, evidence strip, citation placeholders); `aria-busy="true"`; provider failure → banner, not partial content (`FR-16`).

### Empty/error behavior

- Empty (first session): `Ask a question about your fleet — e.g. "why was Alex denied deepseek-coder?"` + composer focus.
- Error (provider): `Provider unavailable — cannot answer.` banner + Retry; query retained.
- Malformed input: clarification prompt; never force-routed (`FR-01`).
- `Entity Not Found in State`: neutral card, mono unresolved refs, inspect/correct options.
- `Cannot confirm (insufficient evidence)`: diagnosis stage unpopulated; states what was checked.

### Citation behavior

Every factual claim carries ≥ 1 resolvable citation (evidence chip → citation card → Inspector). A broken citation never renders; the answer downgrades to `Cannot confirm (insufficient evidence)` (`FR-03`, `FR-13`). Citation cards clickable/keyboard-openable.

### Accessibility behavior

WCAG 2.1 AA; text ≥ 12px; never color alone; `aria-live="polite"` on answer region; skeleton `aria-busy`; canonical strings announced verbatim; focus order = reading order; visible focus ring; copy controls labeled (`Copy node id`), not icon-only; touch targets ≥ 24px; Reduce Motion respected (no slide-in).

### Responsive behavior

`≥ 1280px` full instrument; `1024–1279px` inspector tabs become a bottom sheet; `768–1023px` rail collapses to icons; `< 768px` single column, rails become top-bar menus, dense tables horizontally scrollable with sticky first column. Conversation stays the center of gravity.

---

## S-B — State Inspection Viewer

### Layout and hierarchy

Right-inspector tab (`Inspector`) on desktop; bottom sheet at `1024–1279px`. Header: entity chip/ID + record type + `read-only` marker. Body: inspection fields rendered field-for-field (`FR-12`); JSON payloads in a mono scrollable block. Footer/actions: copy control for mono identifiers; `Entity Not Found` state when the entity is absent.

### Components

- Inspection field (mono-sm label + mono value + hairline divider).
- JSON block (mono scrollable).
- Status badge for state fields (dot + text + icon).
- Entity chip + labeled copy control.
- Empty/not-found card (neutral).

### Component states

| Component | States |
|---|---|
| Inspection field | default / (values always mono, un-styled) |
| JSON block | default / scrollable overflow |
| Status badge | dot + text + icon, per state |
| Copy control | default / hover / focus / copied (feedback `Copied`) |

### Spacing

Row padding `spacing.2`–`spacing.3`; field gap `spacing.3`; section gap `spacing.5`; inspector padding `spacing.4`.

### Typography usage

`technical-sm` labels, `technical` values (13px min for copyable values), `technical-label` for entity IDs; section titles `headline`.

### Status indicators

State fields use the four operational statuses with text+icon always; the `read-only` marker is a text label (never a color-only signal).

### Button/action labels & triggers

| Control | Label | Trigger |
|---|---|---|
| Copy | `Copy node id` | Copies the mono identifier (labeled, not icon-only) |
| Back to Evidence/Audit | tab `Inspector` ↔ `Evidence` / `Audit` | `i` / `e` / `a` or click |
| Open raw state (from citation) | `[open in Inspector ↗]` | Opens the record |

### Navigation behavior

- `i` focuses Inspector; entity chips and citation cards open records here.
- Left-rail entity quick-nav (`g u/m/n/j/r`) jumps the Inspector to that store.
- Reset clears context but never grants destructive power (`FR-02`).

### Dynamic feedback

- Copy control announces `Copied`.
- `Entity Not Found in State` renders as a neutral card (correct behavior, not an error).

### Loading behavior

- Skeleton rows while the record loads; `aria-busy`; no partial field renders.

### Empty/error behavior

- Non-existent entity → `Entity Not Found in State` (verbatim, neutral).
- Provider failure → `Provider unavailable — cannot answer.` banner; no fabricated fields (`FR-16`).
- Retrieved content rendered as data, never executable (`FR-15`).

### Citation behavior

The viewer is the citation target: citation cards open the exact source record here, field-for-field. Broken citation → answer downgrades (handled on S-A).

### Accessibility behavior

Mono values at readable size; focus order = reading order; copy controls labeled; never color-alone statuses; WCAG 2.1 AA.

### Responsive behavior

Desktop: fixed 380px right panel. `1024–1279px`: bottom sheet bound to the focused entity. `< 768px`: full-width sheet; tables horizontally scrollable with sticky first column.

---

## S-C — Tool-Call Audit Log

### Layout and hierarchy

Right-inspector `Audit` tab on desktop; bottom sheet at `1024–1279px`. Header: `Audit trail` + `read-only` marker + row count. Body: append-only rows (timestamp, tool name, parameter summary, status badge). Paged (never infinite-scroll, honoring the retention cap, `FR-11`). Clicking a row opens affected entities in the Inspector.

### Components

- Audit row (`surface-raised`, hover `surface-status`, `rounded.sm`): mono timestamp + tool name + params summary + status badge.
- Status badge (dot + text + icon).
- Pagination controls (`Prev` / `Next` / page indicator).
- Empty state (`No tool calls in this session.`).
- Read-only marker.

### Component states

| Component | States |
|---|---|
| Audit row | default / hover / focus |
| Status badge | per tool-call outcome (success / failure) |
| Pagination | enabled / disabled at bounds |

### Spacing

Row padding `spacing.2`; row gap `spacing.1`; section gap `spacing.4`; pager gap `spacing.3`.

### Typography usage

Timestamps `technical-sm`; tool names `technical-label`; parameter summaries `caption`/`technical-sm`; row count `label`.

### Status indicators

Per-row outcome badge (success/failure) with text + icon; the `read-only` marker labeled. Proposal vs. executor-applied mutation rows carry distinct provenance labels (`Copilot proposal` / `Executor-applied mutation`) — never color alone.

### Button/action labels & triggers

| Control | Label | Trigger |
|---|---|---|
| Open entities | click row | Opens affected entities in Inspector |
| Paginate | `Prev` / `Next` | Page the log |
| Switch tab | `Audit` / `Evidence` / `Inspector` | `a` / `e` / `i` |

### Navigation behavior

- `a` focuses Audit; answer header `Audit trail ▸` opens the tab bound to the answer.
- No edit/delete affordance exists anywhere (`FR-11`, `S-5`).
- Paged, respecting retention cap with rotation of oldest entries (`NFR-11`).

### Dynamic feedback

- New tool calls append in chronological order; `aria-live` announces log updates.
- Row hover reveals per-row actions on `md+` only (never hover-only on small viewports).

### Loading behavior

Skeleton rows while a session's log loads; `aria-busy`; empty session → `No tool calls in this session.`

### Empty/error behavior

- Empty: `No tool calls in this session.` + pager hidden.
- Audit-store failure → `Provider unavailable — cannot answer.` banner (safe-failure, `FR-16`); log never renders partial/fabricated entries.

### Citation behavior

Audit rows link to the entities touched by each tool call (click → Inspector); they are records of tool calls, not claims — evidence chips are not used here.

### Accessibility behavior

Rows keyboard-focusable; statuses never color-alone; WCAG 2.1 AA; no hover-only affordances on small viewports.

### Responsive behavior

Same inspector sheet behavior as S-B; dense rows horizontally scrollable below 768px with sticky first column.

---

## S-D — Safety / Confirmation Surface

### Layout and hierarchy

Reached **only** via a destructive intent. Fixed state machine, always in order:

`Request → Refusal → Dry-run → Explicit confirmation → Proposed delegated action → Executor result → Audit result`

Inline stages on the center thread (refusal banner → dry-run panel → delegation card); the confirmation is a modal `alertdialog` (the one gravity moment). The full sequence is mirrored in the Audit tab.

### Components

- Refusal banner (`surface-danger`, `danger` border, ⚠ icon): `Action refused.` + first-stage dry-run entry point.
- Dry-run panel (`surface-warning`, `warning` border): header `This is a proposal, not an action.` + snapshot timestamp + per-item mono rows + status.
- Confirmation dialog (`rounded.lg`, raised, strong border, shadow, `role="alertdialog"`): restated count + scope; primary danger button; non-authorizing caption.
- Delegation card (`surface-proposal`, `proposal-accent` border): `Copilot proposal` payload line + `Executor-applied mutation` result line (distinct labels).
- Audit rows (from S-C) with proposal vs. mutation distinct.

### Component states

| Component | States |
|---|---|
| Refusal banner | always refusal; no confirmation control here |
| Dry-run panel | populated / `0 affected items` (confirmation disabled) / re-validation delta (re-rendered) |
| Confirmation dialog | open / dismissed(Esc→dry-run) / stale-snapshot (re-opened dry-run) |
| Delegation card | proposal dispatched / executor success / executor failure (proposal preserved) / double-apply (executor-failure) |
| Confirm button | enabled / disabled (`0 items` or re-validation pending) |

### Spacing

Panels `spacing.4` padding; dialog padding `spacing.5`; item rows `spacing.2`; dialog margin `spacing.6` from viewport; button group gap `spacing.3`.

### Typography usage

Refusal title `headline`; dry-run header `title`; item rows `technical-label`; dialog scope `body`; caption (non-authorizing note) `caption` under buttons; payload/proposal lines `technical`.

### Status indicators

Danger surfaces always carry ⚠ + explicit wording; proposal vs. mutation distinguished by label + `proposal-accent`/border, never by color alone; executor outcome badges text+icon.

### Button/action labels & triggers

| Control | Label | Trigger |
|---|---|---|
| Open dry-run | `Review the dry-run →` | Renders the dry-run panel |
| Confirm | `Confirm & propose to executor` | Dispatches the propose-only handoff (post-gate) |
| Dismiss | `Dismiss` / `Cancel (Esc)` | Returns to dry-run; never confirms |
| Re-dispatch (executor failure) | `Re-dispatch proposal` | Deliberate operator action (`FR-16`) |

### Navigation behavior

- Entering S-D blocks session/rail navigation while the dialog is open (`UX-07`).
- Esc closes the dialog to the dry-run — never confirms.
- The confirm button is reachable but never auto-focused on a destructive control.

### Dynamic feedback

- `aria-live` announces `Action refused`, `Dry run ready`, `Proposal dispatched`, `Executor applied mutation` (or failure).
- Stale snapshot re-validation: on scope change the dialog closes back to a re-rendered dry-run with the delta surfaced (`UX-03`).

### Loading behavior

- Skeleton while the intent is classified and the dry-run is composed; `aria-busy`; no confirmation control during load.

### Empty/error behavior

- Unresolved target → `Entity Not Found in State` **before** any dry-run (`UX-01`).
- Empty affected set → `0 affected items`, confirmation **disabled**, no no-op handoff (`UX-02`).
- Executor unavailable → delegation card failure status + reason, proposal line preserved, no auto-retry (`FR-16`).
- Double apply → applied-mutation count surfaces a second record as executor-failure, never as success (`UX-06`).

### Citation behavior

Dry-run items are evidence-linked to job records (`[S4:job#job-...]`); the delegation card uses labeled lines, not citations, to distinguish proposal from applied mutation (`FR-10`).

### Accessibility behavior

`role="alertdialog"` + `aria-describedby` restating scope; fully keyboard-operable; Esc semantics; visible focus ring; confirm never auto-focused; WCAG 2.1 AA; Reduce Motion (no animation on dialog).

### Responsive behavior

`< 768px`: confirmation dialog becomes a full-screen modal; dry-run panel remains scrollable; otherwise same three-pane/responsive rules.

---

## Cross-surface consistency

- **No control on any surface mutates state directly** (`C-1`, `S-6`); only S-D proposes, and only via the executor contract (`FR-10`).
- **Retrieved content is data** — mono, bounded, un-styled, never auto-linked or executable (`FR-15`).
- **Status is never communicated by color alone** on any surface.
- **Canonical strings verbatim**: `Entity Not Found in State`, `Cannot confirm (insufficient evidence)`, `Provider unavailable — cannot answer.`, `Action refused.` (`FR-03`–`FR-06`, `FR-16`).
- Light and dark are equal modes; tokens resolve from `DESIGN.md`.

_Generated using Whiteport Design Studio (WDS) methodology._