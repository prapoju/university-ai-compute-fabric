"""Module 12 — inbound-port interface stub for the ATDD red phase.

This module encodes the **interface** that ``service/ports/in/`` (contracts.md §1 core
operations + §2 inbound routes) must satisfy. Every operation is a stub that raises
``NotImplementedError``: the implementation does not exist yet.

The ATDD suite (``module12_contracts.test.py``) calls these stubs and asserts the
contract (P / Q / I, canonical strings, typed errors, emitted events, and — for
rejections — that nothing happened). Until the implementation lands every test fails
with ``NotImplementedError``: that is the intended red phase, and it fails for the
right reason (the stub is called, not a typo/import error).

Design notes
------------
* ``CopilotInboundPort`` is the use-case seam. Tests construct it with recording
  doubles (``OperationalStore``, ``AuditLog``, ``RecordingExecutor``, ``Metrics``) so
  the suite can assert on *resulting state*, *emitted events* and *what did not
  happen*. Assertions are made on records the SUT is expected to drive — never on a
  value the test itself stubbed in.
* ``ContractError`` is the typed violation (contracts.md §4). ``CanonicalOutcome`` is
  an HTTP-200 canonical return (D58). Both are part of the interface the tests assert.
* Canonical strings are byte-exact per contracts.md §0 (S_ENF/S_CNC/S_PUA/S_ARF/
  S_RBX/S_CAP); their single owner is ``service/core/strings/canonical_strings.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Canonical strings (contracts.md §0) — emitted verbatim, never re-worded.
# ---------------------------------------------------------------------------
S_ENF = "Entity Not Found in State: {ref_list}."
S_CNC = "Cannot confirm (insufficient evidence): checked {checked_list}."
S_PUA = "Provider unavailable — cannot answer."
S_ARF = "Action refused."
S_RBX = "no runbook available for code {code}."
S_CAP = "This confirms a proposal for delegation. It does not grant or assert authorization."


def s_enf(unresolved: list[str]) -> str:
    """Render the ``S_ENF`` literal naming every unresolved ref in input order."""
    return S_ENF.format(ref_list=", ".join(unresolved))


def s_cnc(checked: list[str]) -> str:
    """Render the ``S_CNC`` literal naming every reference that was checked."""
    return S_CNC.format(checked_list=", ".join(checked))


def s_rbx(code: str | None) -> str:
    """Render the ``S_RBX`` literal for a code (``None`` renders the word ``null``)."""
    return S_RBX.format(code="null" if code is None else code)


# ---------------------------------------------------------------------------
# Typed error model (contracts.md §4)
# ---------------------------------------------------------------------------
#: canonical (HTTP-200) codes returned, not raised
CANONICAL_CODES = (
    "ENTITY_NOT_FOUND",
    "CANNOT_CONFIRM",
    "CLARIFICATION",
    "INTENT_NOT_SUPPORTED",
    "ACTION_REFUSED",
)


@dataclass(frozen=True)
class CanonicalOutcome:
    """An HTTP-200 canonical return (D58): an ``ErrorBody`` whose message is the literal."""

    code: str
    message: str
    status: int = 200

    def __post_init__(self) -> None:
        if self.code not in CANONICAL_CODES:
            raise ValueError(f"not a §4 canonical code: {self.code!r}")


class ContractError(Exception):
    """A typed violation (contracts.md §4). Raised by the interface, never returned."""

    def __init__(self, code: str, status: int, message: str, retryable: bool = False) -> None:
        super().__init__(f"{code} ({status}): {message}")
        self.code = code
        self.status = status
        self.message = message
        self.retryable = retryable

    def as_body(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "status": self.status,
            "message": self.message,
            "retryable": self.retryable,
        }


# ---------------------------------------------------------------------------
# Recording doubles (collaborators the SUT is expected to drive)
# ---------------------------------------------------------------------------
class OperationalStore:
    """Read-only operational state (AD-1). ``mutations`` must stay empty for Module 12."""

    def __init__(self, records: dict[str, dict[str, Any]] | None = None) -> None:
        self.records: dict[str, dict[str, Any]] = dict(records or {})
        self.mutations: list[tuple[str, Any]] = []
        self.reads: list[str] = []

    def read(self, key: str) -> dict[str, Any] | None:
        self.reads.append(key)
        return self.records.get(key)

    def apply(self, key: str, value: Any) -> None:
        # Only a real control-plane component would call this; the Copilot must not.
        self.mutations.append((key, value))
        self.records[key] = value


class AuditLog:
    """Append-only audit sink (AD-10). Records emitted tool-call/executor event names."""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.rows: list[dict[str, Any]] = []

    def emit(self, name: str, **fields: Any) -> None:
        self.events.append(name)
        self.rows.append({"name": name, **fields})


class RecordingExecutor:
    """Simulated executor (OP-15). Records dispatch calls; the SUT must drive it."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result: dict[str, Any] | None = None

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(request)
        return self.result or {}


class Metrics:
    """Injectable metrics sink (T-6/P0-G5) for ``m12.*`` counters."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def increment(self, name: str) -> None:
        self.counters[name] = self.counters.get(name, 0) + 1


# ---------------------------------------------------------------------------
# The inbound-port interface (all operations raise NotImplementedError)
# ---------------------------------------------------------------------------
class CopilotInboundPort:
    """Use-case seam: contracts.md §1 operations + §2 inbound routes.

    Every method is a stub. The ATDD suite calls these methods; the resulting
    ``NotImplementedError`` is the red phase.
    """

    def __init__(
        self,
        *,
        store: OperationalStore | None = None,
        audit: AuditLog | None = None,
        executor: RecordingExecutor | None = None,
        metrics: Metrics | None = None,
        providers: dict[str, Any] | None = None,
        sessions: dict[str, dict[str, Any]] | None = None,
        answers: dict[str, dict[str, Any]] | None = None,
        proposals: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        # operational state is read-only for Module 12 (AD-1): never mutated here
        self.store = store or OperationalStore()
        # Module-12-owned stores (contracts.md §2.2) — the copilot may write these
        self.sessions: dict[str, dict[str, Any]] = dict(sessions or {})
        self.answers: dict[str, dict[str, Any]] = dict(answers or {})
        self.proposals: dict[str, dict[str, Any]] = dict(proposals or {})
        self.audit = audit or AuditLog()
        self.executor = executor or RecordingExecutor()
        self.metrics = metrics or Metrics()
        self.providers = dict(providers or {})

    # -- §1 core-domain operations ----------------------------------------
    def answer_query(self, query_text: Any, session_id: Any, now: Any) -> Any:
        raise NotImplementedError("answer_query (contracts.md §1)")

    def resolve_entities(self, references: Any, session_id: Any) -> Any:
        raise NotImplementedError("resolve_entities (contracts.md §1)")

    def assemble_evidence(self, intent: Any, resolved: Any, now: Any) -> Any:
        raise NotImplementedError("assemble_evidence (contracts.md §1)")

    def diagnose_access_denial(self, user: Any, model: Any, evidence: Any) -> Any:
        raise NotImplementedError("diagnose_access_denial (contracts.md §1)")

    def diagnose_schedule_window(self, group: Any, job: Any, windows: Any, now: Any) -> Any:
        raise NotImplementedError("diagnose_schedule_window (contracts.md §1)")

    def diagnose_retrospective(self, query: Any, events: Any) -> Any:
        raise NotImplementedError("diagnose_retrospective (contracts.md §1)")

    def diagnose_node_triage(self, node: Any, error_code: Any, template: Any) -> Any:
        raise NotImplementedError("diagnose_node_triage (contracts.md §1)")

    def lookup_runbook(self, error_code: Any) -> Any:
        raise NotImplementedError("lookup_runbook (contracts.md §1)")

    def propose_destructive_action(
        self, query_text: Any, action: Any, target_refs: Any, session_id: Any, now: Any
    ) -> Any:
        raise NotImplementedError("propose_destructive_action (contracts.md §1)")

    def confirm_and_dispatch(self, proposal_id: Any, gate_token: Any) -> Any:
        raise NotImplementedError("confirm_and_dispatch (contracts.md §1)")

    # -- §2 inbound routes -------------------------------------------------
    def create_session(self, operator_role: Any) -> Any:
        raise NotImplementedError("create_session (contracts.md §2)")

    def submit_query(self, session_id: Any, query_text: Any) -> Any:
        raise NotImplementedError("submit_query (contracts.md §2)")

    def get_session(self, session_id: Any) -> Any:
        raise NotImplementedError("get_session (contracts.md §2)")

    def reset_session(self, session_id: Any) -> Any:
        raise NotImplementedError("reset_session (contracts.md §2)")

    def get_state_record(self, entity_type: Any, id: Any) -> Any:
        raise NotImplementedError("get_state_record (contracts.md §2)")

    def browse_state(self, entity_type: Any, q: Any, page: Any, page_size: Any) -> Any:
        raise NotImplementedError("browse_state (contracts.md §2)")

    def get_answer_evidence(self, answer_id: Any) -> Any:
        raise NotImplementedError("get_answer_evidence (contracts.md §2)")

    def get_citation(self, citation_id: Any) -> Any:
        raise NotImplementedError("get_citation (contracts.md §2)")

    def get_runbook(self, error_code: Any) -> Any:
        raise NotImplementedError("get_runbook (contracts.md §2)")

    def get_audit_page(self, session_id: Any, page: Any, page_size: Any) -> Any:
        raise NotImplementedError("get_audit_page (contracts.md §2)")

    def post_dry_run(
        self, query_text: Any, action: Any, target_refs: Any, session_id: Any
    ) -> Any:
        raise NotImplementedError("post_dry_run (contracts.md §2)")

    def post_confirm(self, proposal_id: Any, gate_token: Any) -> Any:
        raise NotImplementedError("post_confirm (contracts.md §2)")

    def get_proposal(self, proposal_id: Any) -> Any:
        raise NotImplementedError("get_proposal (contracts.md §2)")

    def post_re_dispatch(
        self, parent_proposal_id: Any, query_text: Any, action: Any, target_refs: Any
    ) -> Any:
        raise NotImplementedError("post_re_dispatch (contracts.md §2)")

    # -- §2 executor routes ------------------------------------------------
    def executor_post_proposal(self, body: Any) -> Any:
        raise NotImplementedError("executor_post_proposal (contracts.md §2)")

    def executor_get_proposal(self, proposal_id: Any) -> Any:
        raise NotImplementedError("executor_get_proposal (contracts.md §2)")
