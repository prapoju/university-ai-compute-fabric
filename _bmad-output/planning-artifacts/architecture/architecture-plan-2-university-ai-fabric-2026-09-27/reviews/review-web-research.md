# Web-Research / Reality-Check Review — Module 12 Architecture

- **Reviewer role:** WEB-RESEARCH / REALITY-CHECK
- **Target:** `ARCHITECTURE.md` (created 2026-09-27), Stack section (§ Stack, lines 572–587)
- **Review date:** 2026-09-27
- **Method:** Read the full architecture + `.memlog.md` + PRD/UX sources for stack provenance; web-verified every named technology and pin against primary sources (PyPI, GitHub releases, python.org, react.dev, vite.dev, uvicorn.dev, typescriptlang.org/devblogs, Ollama releases) as of the project's "today" 2026-09-27; cross-checked against the repo for any existing starter/code pins (none exist — `design-artifacts/` is empty, no `package.json`/`requirements.txt`/`pyproject.toml` outside opencode tooling, no starter scaffold).

---

## Verdict

**The stack is ~85% verified-current and the three deliberate "non-decisions" (no ORM, no agent framework, no queue/broker) are all defensible and not missing — but one pinned version (TypeScript 5.x) is two majors out of date and directly contradicts the seed's "verified current at authoring" claim, and the Python 3.11.15 pin is one patch stale in a security-only line.**

## Verification Matrix (web-verified, 2026-09-27)

| Claim in ARCHITECTURE.md | Web reality (as of 2026-09-27) | Status |
|---|---|---|
| Python 3.11 (3.11.15 on build host) | 3.11.15 real (2026-03-03); **3.11.16 released 2026-08-01**; 3.11 is in "security fixes only" (source-only, no binaries) until Oct 2027 | ⚠️ stale-by-one, supported |
| Python "≥ 3.10 required" | FastAPI 0.141 `requires-python >=3.10` ✓; Uvicorn >=3.10 ✓; **but Python 3.10 EOLs Oct 2026 — next month** | ⚠️ floor about to EOL |
| FastAPI 0.141.x | Latest 0.141.1 (2026-07-29); current stable minor | ✅ current |
| Uvicorn "current stable" | Latest 0.53.0 (2026-09-14); `fastapi[standard]` still installs `uvicorn[standard]` | ✅ current (unpinned) |
| React 19.x | Latest stable **19.3.0** (2026-09-09); 19.2.8 LTS-ish line still maintained | ✅ current |
| TypeScript 5.x | **TS 6.0 (2026-03-23, final JS bridge) and TS 7.0 (2026-07-08, Go-native, current 7.0.2) both released; 5.9.3 was the last 5.x** | ❌ two majors stale |
| Vite 8.x | 8.0 (2026-03-12); latest 8.3.0 (2026-09-10); supported line | ✅ current |
| Ollama 0.34.x | 0.34.0 (2026-09-05) → 0.34.3 (mid-Sep 2026); current | ✅ current |
| SQLite (stdlib) | `sqlite3` bundled with CPython, but links platform/system `libsqlite3` (version varies by host); floor is 3.7.15 | ⚠️ loosely phrased |

## Critical

_None. No pinned technology is discontinued, deprecated, or wrong-shaped for the job. All three deliberate omissions (below) are correct calls, not missing decisions._

## High

### H1 — TypeScript 5.x is two major versions out of date and contradicts "verified current at authoring"

- **What:** The Stack table pins `TypeScript | 5.x` and the seed header claims "Seed — verified current at authoring (2026-09-27)." TypeScript 6.0 (final JavaScript-codebase release, 2026-03-23) and TypeScript 7.0 (Go-native compiler, released 2026-07-08, current patch 7.0.2) were both stable ~6 months before the architecture date. 5.x is the second-to-last major and is no longer the "current" line. This reads as the one version asserted from training data rather than verified.
- **Where:** `ARCHITECTURE.md` § Stack, line 582; also echoed in `Structural Seed` (line 593: "React 19 + TS + Vite 8 SPA").
- **Suggested fix:** Pin **TypeScript 6.0.x** (recommended: it is API-compatible with 5.9, tooling-compatible with `typescript-eslint`/`ts-node`/Vite plugin ecosystem, and is the documented upgrade bridge) or **7.0.x** if the console wants the native compiler (note: TS 7.0 ships **no stable JS API** — plugin/type-checker tooling must stay on 6.x via the `@typescript/typescript6` alias). Either way, drop `5.x` and correct the "verified current" wording. Vite 8's own `create-vite` templates scaffold on TS 6/7, so 5.x will also diverge from the starter shape.

## Medium

### M1 — Python 3.11.15 is one patch behind and 3.11 is in security-only mode

- **What:** The pin `3.11.15` (line 578) was current in March 2026; **3.11.16 shipped 2026-08-01**. More importantly, Python 3.11 is in the "security fixes only" phase — source-only releases, irregular cadence, no binary installers — until Oct 2027. The parenthetical "≥ 3.10 required" also sets the floor one month before 3.10's EOL (Oct 2026).
- **Where:** `ARCHITECTURE.md` § Stack, line 578.
- **Suggested fix:** Bump the build-host reference to **3.11.16**, or — for a greenfield prototype — consider **3.12/3.13** (still in full bugfix, EOL 2028/2029), which FastAPI 0.141 and Uvicorn both support. If the build host genuinely has 3.11.15, say so explicitly and note the security-only status; do not claim "current." Fix the "≥ 3.10 required" note to "≥ 3.11" or "3.11/3.12/3.13 supported."

### M2 — SQLite "bundled with Python 3.11" is not a real pin

- **What:** CPython's `sqlite3` stdlib dynamically links the host's `libsqlite3` (python.org builds bundle one; distro builds use the system library — versions vary widely). The architecture leans on SQLite features that are version-sensitive: an update/delete-denying trigger (AD-10), paging, retention rotation, and the determinism/fault-injection test suite. "Bundled with Python 3.11" implies a fixed engine that does not actually exist.
- **Where:** `ARCHITECTURE.md` § Stack, line 585; invariants AD-10 (line 524).
- **Suggested fix:** State the SQLite floor the code actually needs (e.g., "requires `sqlite_version ≥ 3.35`", asserted via `sqlite3.sqlite_version` at startup), or pin the container base image's SQLite in the build. Keep the "no ORM" stance; this is about engine version, not mapping layer.

## Low

### L1 — Uvicorn is left unpinned despite the seed's "verified current" claim
- **What/Where:** Line 580: "current stable (served by `fastapi[standard]`)." That is a policy, not a version. Today's current is 0.53.0 (2026-09-14).
- **Suggested fix:** Acceptable per the seed's own rule ("the code owns the exact pins once it exists") — but note the doc pins everything else and only this row defers. One line: `Uvicorn | 0.53.x (via fastapi[standard])` would be symmetric.

### L2 — React "19.x" is correct but loose
- **What/Where:** Line 581. Latest stable is **19.3.0** (2026-09-09).
- **Suggested fix:** Non-issue; optionally tighten to `19.3.x`. No action required.

### L3 — Stack has no cross-checkable source in the repo
- **What/Where:** The stack appears only in `ARCHITECTURE.md` and `.memlog.md` ("Stack (verified 2026-09)"). No PRD/UX stack section, no starter, no lockfile exists to anchor or refute the pins (`design-artifacts/E-Development/` is empty).
- **Suggested fix:** Low risk since 6 of 8 pins verified correct — but record the primary-source URLs (PyPI/GitHub release pages) next to each pin, or in the memlog, so the "verified current" claim is auditable and the next reviewer doesn't re-run this whole gate.

## Negative-decision check (deliberate non-pins — confirmed defensible)

- **No ORM — defensible, not missing.** Four small Module-12-owned stores (sessions, evidence, proposals, audit), single process, stdlib `sqlite3`. The audit store's append-only guarantee is *better* expressed as a native SQLite trigger (AD-10) than via an ORM layer; an ORM adds a dependency and a mapping abstraction with zero architectural benefit at this size. Plain SQL keeps the deterministic core I/O-free and the adapter ring thin. (When the stores grow or a real platform DB appears, the adapter ring is the replacement point — already designed.)
- **No agent framework — defensible, correct even.** The system's core invariant is evidence-level determinism (AD-2, FR-14: 3× identical runs). LangChain/crewAI/AgentKit-style frameworks would inject exactly the nondeterminism and control-flow opacity this architecture exists to prevent. The LLM is deliberately reduced to one non-factual prose call per answer behind a port. The Consistency Conventions' "no 'agent'/'skill' naming for pipeline stages" (line 568) is the right discipline. A framework here would be wrong-shaped.
- **No queue/broker/cache — defensible, not missing.** Single backend process, all contracts synchronous request/response HTTP, dry-run re-validation is pull-based re-query (line 219, AD-6), and nothing in the four scenarios + edge case requires push or async fan-out. A broker would be speculative infrastructure. The executor contract (`POST /executor/v1/proposals`) is the designated boundary if the real platform later needs async delivery — noted as a replacement point (OQ-3), not silently assumed.

## Bottom line for the gate

The stack's fast-moving pins (FastAPI 0.141.x, React 19.x, Vite 8.x, Ollama 0.34.x) are all **verified current**; the "boring" choices (Python 3.11, SQLite stdlib, no ORM/agent-framework/queue) are **defensible**. The single substantive error is **TypeScript 5.x (H1)** — two majors behind, contradicting the seed's verification claim — plus two medium documentation-accuracy issues (Python 3.11.15 patch staleness/security-only status, and the unpinned "bundled" SQLite). Nothing is critical; no decision is wrong-shaped or missing.