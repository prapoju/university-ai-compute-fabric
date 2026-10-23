---
name: AI Operations Copilot — Conversational Operations Console
status: final
description: Data-dense administrative/observability console for a cited, evidence-level deterministic AI ops assistant. Operations-console vocabulary, not consumer chat.
colors:
  surface-base: '#F4F6F8'
  surface-raised: '#FFFFFF'
  surface-overlay: '#0B1220'
  surface-warning: '#FFF7ED'
  surface-danger: '#FEF2F2'
  surface-evidence: '#EEF2FF'
  surface-proposal: '#F0FDFA'
  surface-status: '#F1F5F9'
  surface-base-dark: '#0B1220'
  surface-raised-dark: '#141E30'
  surface-input-dark: '#1A2638'
  surface-warning-dark: '#33240F'
  surface-danger-dark: '#331616'
  surface-evidence-dark: '#1A213F'
  surface-proposal-dark: '#0F2B28'
  surface-status-dark: '#1A2638'
  ink-primary: '#111827'
  ink-secondary: '#4B5563'
  ink-muted: '#5F6673'
  ink-on-accent: '#FFFFFF'
  ink-primary-dark: '#E5E7EB'
  ink-secondary-dark: '#9CA3AF'
  ink-muted-dark: '#8790A4'
  ink-on-accent-dark: '#FFFFFF'
  border-hairline: '#E5E7EB'
  border-strong: '#D1D5DB'
  border-hairline-dark: '#24334D'
  border-strong-dark: '#3B4A68'
  status-available: '#15803D'
  status-reserved: '#96600A'
  status-active: '#1D4ED8'
  status-fault: '#B91C1C'
  status-available-dark: '#4ADE80'
  status-reserved-dark: '#FBBF24'
  status-active-dark: '#60A5FA'
  status-fault-dark: '#F87171'
  warning: '#C2410C'
  warning-dark: '#FB923C'
  danger: '#DC2626'
  danger-dark: '#F87171'
  evidence-accent: '#4F46E5'
  evidence-accent-dark: '#818CF8'
  proposal-accent: '#0F766E'
  proposal-accent-dark: '#2DD4BF'
  focus-ring: '#2563EB'
  focus-ring-dark: '#60A5FA'
  skeleton: '#E2E8F0'
  skeleton-dark: '#24334D'
updated: 2026-09-28
typography:
  display:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '650'
    lineHeight: '1.3'
  headline:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: '1.4'
  title:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1.45'
  body:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.55'
  body-emphasis:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1.55'
  caption:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: '1.45'
  label:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: '1.4'
    letterSpacing: '0.06em'
  technical:
    fontFamily: 'JetBrains Mono'
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.5'
  technical-sm:
    fontFamily: 'JetBrains Mono'
    fontSize: 11.5px
    fontWeight: '400'
    lineHeight: '1.45'
  technical-label:
    fontFamily: 'JetBrains Mono'
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.4'
rounded:
  sm: 2px
  md: 4px
  lg: 6px
  full: 9999px
spacing:
  '1': 4px
  '2': 8px
  '3': 12px
  '4': 16px
  '5': 24px
  '6': 32px
  gutter: 16px
  rail-width: 240px
  inspector-width: 380px
components:
  status-badge:
    background: '{colors.surface-status}'
    border-color: '{colors.border-strong}'
    foreground: '{colors.ink-primary}'
    radius: '{rounded.full}'
    label-typography: '{typography.technical-label}'
  status-dot:
    size: 8px
    radius: '{rounded.full}'
  citation-card:
    background: '{colors.surface-evidence}'
    border-color: '{colors.evidence-accent}'
    radius: '{rounded.md}'
    source-typography: '{typography.technical-label}'
    snippet-typography: '{typography.caption}'
  diagnosis-card:
    background: '{colors.surface-raised}'
    border-color: '{colors.border-hairline}'
    radius: '{rounded.md}'
  runbook-card:
    background: '{colors.surface-raised}'
    border-color: '{colors.border-hairline}'
    radius: '{rounded.md}'
  runbook-step:
    number-typography: '{typography.technical-label}'
    body-typography: '{typography.body}'
  refusal-banner:
    background: '{colors.surface-danger}'
    border-color: '{colors.danger}'
    foreground: '{colors.ink-primary}'
    radius: '{rounded.md}'
  dry-run-panel:
    background: '{colors.surface-warning}'
    border-color: '{colors.warning}'
    radius: '{rounded.md}'
  confirmation-dialog:
    background: '{colors.surface-raised}'
    border-color: '{colors.border-strong}'
    radius: '{rounded.lg}'
    destructive-button: '{colors.danger}'
    destructive-button-foreground: '{colors.ink-on-accent}'
  delegation-card:
    background: '{colors.surface-proposal}'
    border-color: '{colors.proposal-accent}'
    radius: '{rounded.md}'
  audit-row:
    background: '{colors.surface-raised}'
    hover-background: '{colors.surface-status}'
    radius: '{rounded.sm}'
    timestamp-typography: '{typography.technical-sm}'
  inspection-field:
    label-typography: '{typography.technical-sm}'
    value-typography: '{typography.technical}'
    divider: '{colors.border-hairline}'
  entity-chip:
    background: '{colors.surface-raised}'
    border-color: '{colors.border-strong}'
    radius: '{rounded.full}'
    id-typography: '{typography.technical-label}'
  composer:
    background: '{colors.surface-raised}'
    border-color: '{colors.border-strong}'
    radius: '{rounded.md}'
    text-typography: '{typography.body}'
  turn-copilot:
    background: '{colors.surface-raised}'
    border-color: '{colors.border-hairline}'
    radius: '{rounded.md}'
  answer-chain-chip:
    radius: '{rounded.full}'
    label-typography: '{typography.label}'
  provider-unavailable-banner:
    background: '{colors.surface-warning}'
    border-color: '{colors.warning}'
    radius: '{rounded.md}'
  empty-state:
    headline-typography: '{typography.headline}'
    body-typography: '{typography.caption}'
  loading-skeleton:
    background: '{colors.skeleton}'
    radius: '{rounded.sm}'
---

## Brand & Style

Module 12 is an **operations console with conversational investigation**, not a consumer chat product. The aesthetic is that of a professional tool the operator trusts under time pressure: dense, quiet, inspectable, and honest. Every element that looks like an answer must be able to prove itself on demand; nothing is decorative, and nothing asserts more than the evidence supports.

Two visual contracts govern everything:

- **Evidence before persuasion.** Answers are built from retrieved state and policy, never from confident prose. The UI renders the diagnosis and its support as separate, labeled layers. Uncertainty is a first-class visual state with the same weight as a confident answer.
- **Status is never communicated by color alone.** Every colored signal carries a label, an icon, or both. Color supports meaning; it never carries meaning by itself.

## Colors

The palette is a cool-gray neutral base (an instrument panel, not a canvas) with a disciplined set of semantic accents. Light and dark are full modes; dark is the operator-preferred default at night-shift and the equal of light — neither is a downgrade.

### Neutrals

- **`{colors.surface-base}`** is the console canvas. Cool, slightly blue-gray, chosen to sit under dense tables without glare.
- **`{colors.surface-raised}`** is the card/panel surface: answer turns, inspector fields, runbook cards, dialog bodies.
- **`{colors.ink-primary}` / `{colors.ink-secondary}` / `{colors.ink-muted}`** — primary text, supporting text, and placeholders/de-emphasis. Contrast-targeted per the Accessibility section.
- **`{colors.border-hairline}` / `{colors.border-strong}`** — structural separation and interactive control borders.

**Contrast verification (WCAG 2.1 AA, ≥ 4.5:1 for text):** recomputed with the corrected tokens (D18). Ratios recorded so the accessibility claim is checkable.

| Token | On surface | Contrast |
|---|---|---|
| `ink-primary #111827` | `surface-base #F4F6F8` | 15.2:1 |
| `ink-secondary #4B5563` | `surface-base #F4F6F8` | 7.0:1 |
| `ink-muted #5F6673` | `surface-base #F4F6F8` | 5.3:1 |
| `ink-muted #5F6673` | `surface-raised #FFFFFF` | 5.8:1 |
| `ink-primary-dark #E5E7EB` | `surface-base-dark #0B1220` | 13.8:1 |
| `ink-secondary-dark #9CA3AF` | `surface-base-dark #0B1220` | 7.4:1 |
| `ink-muted-dark #8790A4` | `surface-base-dark #0B1220` | 5.9:1 |
| `ink-muted-dark #8790A4` | `surface-raised-dark #141E30` | 5.2:1 |
| `status-reserved #96600A` | `surface-status #F1F5F9` | 4.8:1 |

### Operational status colors

These map to state vocabulary used across nodes, jobs, and reservations (PRD FR-12; user-specified semantics). They are **always paired with a text label and an icon/dot**.

| Token | Semantics | Light | Dark |
|---|---|---|---|
| `status-available` | Available / healthy / idle | `{colors.status-available}` | `{colors.status-available-dark}` |
| `status-reserved` | Reserved / constrained / window applies | `{colors.status-reserved}` | `{colors.status-reserved-dark}` |
| `status-active` | Active / busy / in-flight | `{colors.status-active}` | `{colors.status-active-dark}` |
| `status-fault` | Fault / offline / cordoned / failed | `{colors.status-fault}` | `{colors.status-fault-dark}` |

### Semantic state colors

- **`{colors.warning}`** — degraded operation: provider unavailable, malformed input, dry-run emphasis, insufficient-evidence emphasis. Amber-orange, deliberately distinct from `status-reserved` gold so a constrained *state* and a degraded *condition* never collide on hue alone (they also differ in icon and label).
- **`{colors.danger}`** — destructive-action refusal, destructive confirmation, executor failure. Always shown with a warning icon and explicit wording.
- **`{colors.evidence-accent}`** — citations, evidence cards, audit references. The visual signature of "this claim can be checked."
- **`{colors.proposal-accent}`** — proposed delegated action and executor results. The visual signature of "this is a proposal or an executor-applied mutation, not a copilot action."
- **`{colors.focus-ring}`** — keyboard focus and selected states.

### State surface tints

Background fills that reinforce state surfaces without shouting: `surface-warning`, `surface-danger`, `surface-evidence`, `surface-proposal`. They are used on panels/banners/cards, and always combined with the matching border color and a text label — never a color field alone.

**Avoid:** gradients, saturated brand fills behind body text, decorative use of semantic colors, red fills for anything non-destructive, and any color whose only differentiator is hue.

## Typography

Two families, one job: **read fast, verify fast.**

- **Inter** for all prose, controls, and labels. Density-optimized at 14px body with 1.55 line-height — readable without wasting vertical space.
- **JetBrains Mono** for technical identifiers and payloads *only*: node IDs, job IDs, user/group IDs, error codes, timestamps, tool names, log lines, and JSON/state payloads. **The console is not monospace overall** — mono is the marker of "this is an identifier you may need to copy or match exactly."

Roles:

- `display` — surface headlines (rare; empty states, session header).
- `headline` — answer block titles, inspector section titles.
- `title` — card titles, runbook titles.
- `body` / `body-emphasis` — prose, explanations, runbook steps.
- `caption` — supporting text, snippet text.
- `label` — small-caps section labels and the answer-chain chips.
- `technical` / `technical-sm` / `technical-label` — identifiers, timestamps, JSON, field values, badge text.

Rules:

- Identifiers that will be copied (IDs, codes) render in mono at `13px` minimum — never anti-aliased into illegibility at `technical-sm` for values a user must transcribe.
- `label` all-caps is reserved for structural section headers and the answer chain — never for sentences.
- Body text never dips below 12px (`caption` floor); `technical-sm` at 11.5px is permitted only for non-critical timestamps and log metadata.

## Layout & Spacing

**Desktop-first, data-dense.** The console is a three-pane instrument:

- **Left rail** (`spacing.rail-width`, 240px) — session list, entity quick-nav (users / groups / models / nodes / jobs / reservations / policy / events).
- **Center** — the conversation thread and composer.
- **Right inspector** (`spacing.inspector-width`, 380px) — tabbed Evidence / Inspector / Audit panel bound to the focused answer or entity.

Scale: 4 / 8 / 12 / 16 / 24 / 32. Data rows breathe at 8–12px vertical rhythm; major panels separate at 16–24px. Dense tables use 8px row padding — density is a feature, but no control is smaller than a 24px touch/click target.

Grid: a 12-column grid above 1200px with the center pane fluid and fixed rails; below that, rails recede (see EXPERIENCE.md Responsive). Panels do not float over data — anchoring, not elevation, is the hierarchy device.

## Elevation & Depth

The console is flat by default: surfaces are distinguished by tone and 1px borders, not shadows. Shadows appear in exactly two places: the confirmation dialog (the one moment of literal gravity) and the right-panel tab bar when it scrolls (affordance of stacked panels). No ambient shadows behind cards — an operations console must not read as "layers to swipe through."

## Shapes

Small radii, crisp corners — this is a tool, not a consumer surface.

- `rounded.sm` (2px) — audit rows, skeleton blocks.
- `rounded.md` (4px) — cards, banners, panels, composer, dialog body.
- `rounded.lg` (6px) — the confirmation dialog frame.
- `rounded.full` — status badges and entity chips only.

Nothing else rounds. No pill buttons, no circular avatars-as-decoration.

## Components

Visual specs. Behavioral rules live in `EXPERIENCE.md` Component Patterns.

- **Status badge** — `{colors.surface-status}` background, `{colors.border-strong}` border, `rounded.full`. Composition: 8px `status-dot` (in the state color) + `technical-label` text. Every state also has an icon where semantics allow (e.g., ⚠ for fault). Never a bare colored dot. **In dense tables, the text label is always present per cell — a dot without its label is not a valid status rendering.**
- **Citation card** — `{colors.surface-evidence}` background, `{colors.evidence-accent}` 1px border, `rounded.md`. Header: mono `source id` + record type; body: `caption` snippet. Always clickable to open the source record in the Inspector. A citation whose source record cannot be resolved never renders — the answer downgrades to `Cannot confirm (insufficient evidence)`.
- **Evidence chip** — inline `mono` source reference `[S1:policy#clause-4.2]` in answer prose, linking to its citation card.
- **Diagnosis card** — `{colors.surface-raised}`, hairline border. Contains: headline diagnosis, reason class, and evidence chips. The **only** component allowed to state a diagnosis.
- **Answer chain** — a horizontal run of `rounded.full` chips labeling each stage reached: `Observation → Evidence → Diagnosis → Recommendation → Proposal → Execution`. Filled chips = populated stages; the current stage is the filled + emphasized one; unpopulated later stages are muted. This is the single visual contract that makes the six-stage distinction explicit on every answer.
- **Runbook card** — `surface-raised`, hairline border. Title = error code in `technical-label`. Ordered steps, each `number. body`. Steps with physical-safety content carry a `danger` warning strip labeled with the approved-source provenance line.
- **Refusal banner** — `{colors.surface-danger}`, `{colors.danger}` border, ⚠ icon. Title: `Action refused.` Body explains the copilot performs no mutation and shows the first-stage dry-run entry point.
- **Dry-run panel** — `{colors.surface-warning}`, `{colors.warning}` border. Enumerates each affected item as a mono list row with per-item status. Header notes this is a proposal, not an action.
- **Confirmation dialog** — `rounded.lg`, `{colors.surface-raised}`, strong border, shadow. Body restates the dry-run count and scope. Primary button is `{colors.danger}` and reads `Confirm & propose to executor`. Label under the buttons, `caption`: `This confirms a proposal for delegation. It does not grant or assert authorization.`
- **Delegation card** — `{colors.surface-proposal}`, `{colors.proposal-accent}` border. Shows the proposed action payload (mono), then the executor result line with timestamp and status. The proposal and the executor-applied mutation are visually distinct lines, labeled `Copilot proposal` and `Executor-applied mutation`.
- **Audit row** — mono timestamp + tool name + params summary + status badge; `rounded.sm`; hover fill `surface-status`. Clicking a row opens the affected entities in the Inspector.
- **Inspection field** — mono-sm label, mono value, hairline divider. Renders raw state field-for-field (`FR-12`); JSON payloads in a mono scrollable block.
- **Entity chip** — `rounded.full`, mono ID, clickable → Inspector.
- **Composer** — `surface-raised`, strong border, `rounded.md`. Query text in `body`. Enter submits; Shift+Enter newline. A mono used/limit countdown (`180/1000`) protects the 1,000-char limit (FR-01) without shouting — it always reads *characters used out of the cap* and can never display a value above it; an over-limit paste is blocked and surfaced as a clarification/validation state, not a counter value (D16).
- **Provider-unavailable banner** — `surface-warning` + `warning` border, top of the thread. `Provider unavailable — cannot answer. Your query is not lost.` with a Retry action.
- **Loading skeleton** — `loading-skeleton` blocks shaped to the expected answer anatomy (headline bar, evidence strip, citation placeholders).
- **Empty state** — `headline` line + `caption` guidance. No celebratory copy. First-session example: `Ask a question about your fleet — e.g. "why was Alex denied deepseek-coder?"`.
- **Entity Not Found state** — a neutral (non-error) card titled in mono `Entity Not Found in State`, listing each unresolved reference, with an option to inspect the raw state or correct the reference. It is visually *neutral*, not alarming — the system did its job correctly.

## Do's and Don'ts

| Do | Don't |
|---|---|
| Label every status with text + icon + color | Communicate status with color alone |
| Render IDs and payloads in mono, prose in Inter | Make the whole UI monospace |
| Show the answer chain (Observation → … → Execution) on every answer | Blend evidence, diagnosis, and recommendation into one paragraph |
| Treat `Entity Not Found in State` and `Cannot confirm (insufficient evidence)` as canonical, verbatim strings | Paraphrase the canonical non-fabrication responses |
| Mark every proposal vs. executor mutation distinctly | Let a proposal read as an executed action |
| Render retrieved content as data (mono, bounded, un-styled) | Render retrieved content as instructions, links, or executable UI |
| Use `{colors.danger}` only for destructive/refusal surfaces | Use red for general errors, warnings, or decoration |
| Keep densities high but targets ≥ 24px and text ≥ 12px | Compress to shave the layout below legibility |
| Anchor hierarchy with layout and tone | Use shadows or elevation as the hierarchy device |
| Support light and dark as equal modes | Treat dark as a dimmed afterthought |