"""Module 12 — AI Operations Copilot — Data Transfer Objects (Phase 2.2).

Primitive-typed Pydantic v2 models only. No FastAPI ``Request``/``Response`` or any other
framework object appears in a DTO or in a port signature (hard rule R4).

Names, enums, and field sets mirror ``planning/detailed-design/contracts.md``:
  - §0.1 scalar/value types, §0.2 entity enums, §0.3 records (extra fields are a contract
    violation — enforced here with ``extra="forbid"``), §0.4 answer composition,
    §0.5 safety/proposal types, §2 inbound operations (§2 request/response DTOs),
    §3 ports OP-1..OP-12, §4 error catalog.

Every DTO field is a primitive (``str``/``int``/``bool``/``float``/``None``) or a collection of
primitives, or another Module-12 DTO in this module.

NOTE on identifiers: ``Instant`` is a ``str`` (ISO-8601 UTC) per contracts.md §0.1, not
``datetime`` — keeps the DTO framework-free and the regex normative.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

__all__ = [
    # scalar / value types (§0.1)
    "QueryText", "SessionId", "OperatorRole", "Instant", "EntityKey", "CitationId",
    "RawRef", "Snippet", "PolicyContentText", "Page", "PageSize", "GateToken",
    "ActionVerb", "ReasonClass", "IdKind", "IdString", "ProseText",
    # entity enums (§0.2)
    "EntityType", "EntityTypeRoute", "EventType", "DiagnosisClass", "CanonicalCode",
    "AnswerStage", "ProposalState", "ExecutorStatus",
    # records (§0.3)
    "UserRecordDTO", "GroupRecordDTO", "ModelCatalogEntryDTO", "AccessPolicyClauseDTO",
    "JobRecordDTO", "NodeRecordDTO", "ReservationRecordDTO", "PolicyWindowDTO",
    "OperationalEventDTO", "RecordDTO",
    # answer composition (§0.4)
    "ClockReadDTO", "EvidenceDTO", "EvidenceSetDTO", "ClaimDTO", "AnswerDTO",
    "AnswerEnvelopeDTO", "RunbookTemplateDTO",
    # session / audit
    "SessionContextDTO", "SessionDTO", "ToolCallDTO", "AuditRecordDTO",
    # safety / proposal (§0.5)
    "SelectorDTO", "AffectedItemDTO", "DryRunSnapshotDTO", "ConfirmationDTO",
    "ExecutorResultDTO", "ProposalDTO", "ExecutorRequestDTO",
    # outbound generation/prose ports (OP-13, OP-14)
    "ProsePromptDTO", "IdGenRequest", "IdGenResponse",
    "ComposeProseRequest", "ComposeProseResponse",
    # errors / explanation (§4)
    "ErrorCode", "ErrorBody", "ExplanationDTO",
    # §2 request/response DTOs
    "CreateSessionRequest", "CreateSessionResponse",
    "SubmitQueryRequest", "SubmitQueryResponse",
    "GetSessionRequest", "GetSessionResponse",
    "ResetSessionRequest", "ResetSessionResponse",
    "GetStateRecordRequest", "GetStateRecordResponse",
    "BrowseStateRequest", "BrowseStateResponse",
    "GetAnswerEvidenceRequest", "GetAnswerEvidenceResponse",
    "GetCitationRequest", "GetCitationResponse",
    "GetRunbookRequest", "GetRunbookResponse",
    "GetAuditPageRequest", "GetAuditPageResponse",
    "PostDryRunRequest", "PostDryRunResponse",
    "PostConfirmRequest", "PostConfirmResponse",
    "GetProposalRequest", "GetProposalResponse",
    "PostReDispatchRequest", "PostReDispatchResponse",
    "ExecutorPostProposalRequest", "ExecutorPostProposalResponse",
    "ExecutorGetProposalRequest", "ExecutorGetProposalResponse",
]

_ISO = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z$"


class _DTO(BaseModel):
    """Base for every DTO. Extra fields are a contract violation (§0.3)."""

    model_config = ConfigDict(extra="forbid", frozen=False)


# ---------------------------------------------------------------------------
# §0.1 Scalar and value types
# ---------------------------------------------------------------------------
QueryText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
SessionId = Annotated[str, StringConstraints(pattern=r"^sess-[0-9a-f]{16}$")]
OperatorRole = Annotated[str, StringConstraints(pattern=r"^role-[a-z0-9_-]{1,32}$")]
Instant = Annotated[str, StringConstraints(pattern=_ISO)]
RawRef = Annotated[str, StringConstraints(min_length=1, max_length=200)]
Snippet = Annotated[str, StringConstraints(min_length=1, max_length=500)]
PolicyContentText = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
Page = Annotated[int, Field(ge=1)]
PageSize = Annotated[int, Field(ge=1, le=100)]
GateToken = Annotated[str, StringConstraints(pattern=r"^gt-[0-9a-f]{32}$")]

EntityKey = Annotated[
    str,
    StringConstraints(pattern=r"^(user|group|model|policy|node|job|reservation|window|event)#.+$"),
]
CitationId = Annotated[
    str,
    StringConstraints(pattern=r"^(user|group|model|policy|node|job|reservation|window|event|clock)#.+$"),
]

ActionVerb = Literal["delete_jobs", "cancel_jobs", "cordon_node", "drain_node"]
ReasonClass = Literal["not-in-allowlist", "quota", "window"]

# IdKind / IdString (§0.1; produced only via OP-13 idgen_port — R2)
IdKind = Literal[
    "session", "answer", "claim", "tool_call", "audit", "proposal", "gate_token", "event"
]
IdString = Annotated[
    str,
    StringConstraints(
        pattern=r"^(sess|ans|clm|tc|aud|prop|evt)-[0-9a-f]{16}$|^gt-[0-9a-f]{32}$"
    ),
]

# ---------------------------------------------------------------------------
# §0.2 Entity enums
# ---------------------------------------------------------------------------
EntityType = Literal["user", "group", "model", "policy", "node", "job", "reservation", "window", "event"]
EntityTypeRoute = Literal[
    "users", "catalog", "policy", "groups", "jobs", "nodes", "reservations", "windows", "events"
]
EventType = Literal["access_denied", "job_cancelled", "node_cordoned"]
DiagnosisClass = Literal[
    "access_denial_not_in_allowlist", "access_denial_quota", "access_denial_window",
    "schedule_window_restricted", "schedule_no_constraint",
    "event_denied", "event_cancelled", "event_cordoned",
    "node_triage_runbook", "no_runbook_available",
]
CanonicalCode = Literal[
    "ENTITY_NOT_FOUND", "CANNOT_CONFIRM", "CLARIFICATION",
    "INTENT_NOT_SUPPORTED", "ACTION_REFUSED",
]
AnswerStage = Literal["observation", "evidence", "diagnosis", "recommendation", "proposal", "execution"]
ProposalState = Literal[
    "refused", "dry_run", "confirmed", "dispatched", "executed", "failed", "superseded"
]
ExecutorStatus = Literal["applied", "partial", "failed"]

# ---------------------------------------------------------------------------
# §4 Typed Error Catalog
# ---------------------------------------------------------------------------
ErrorCode = Literal[
    "VALIDATION_EMPTY_QUERY", "VALIDATION_QUERY_TOO_LONG", "VALIDATION_MALFORMED_BODY",
    "VALIDATION_BAD_ENTITY_TYPE", "VALIDATION_BAD_ACTION", "VALIDATION_BAD_ID_KIND",
    "PAGINATION_INVALID",
    "SESSION_NOT_FOUND", "SESSION_EXPIRED", "ENTITY_NOT_FOUND", "CANNOT_CONFIRM",
    "CLARIFICATION_REQUIRED", "INTENT_NOT_SUPPORTED", "PROVIDER_UNAVAILABLE",
    "CLOCK_UNAVAILABLE", "LLM_UNAVAILABLE", "LLM_PROSE_REJECTED", "AUDIT_WRITE_FAILED",
    "ACTION_REFUSED", "PROPOSAL_NOT_FOUND", "PROPOSAL_STATE_INVALID", "GATE_TOKEN_INVALID",
    "CONFIRMATION_STALE", "DRY_RUN_EMPTY_SET", "CONFIRMATION_CONFLICT", "EXECUTOR_UNAVAILABLE",
    "EXECUTOR_PARTIAL_APPLY", "EXECUTOR_DUPLICATE_APPLY", "RUNBOOK_NOT_FOUND",
    "RUNBOOK_TEMPLATE_EMPTY", "RUNBOOK_TEMPLATE_UNSOURCED",
]


class ExplanationDTO(_DTO):
    """Structured explanation attached to an error/answer (Phase 2.2)."""

    rule_ids: list[str] = Field(default_factory=list)
    observed_values: list[str] = Field(default_factory=list)
    thresholds: list[str] = Field(default_factory=list)


class ErrorBody(_DTO):
    """Envelope for every §4 typed error."""

    code: ErrorCode
    status: int = Field(ge=100, le=599)
    message: str
    retryable: bool
    explanation: Optional[ExplanationDTO] = None


# ---------------------------------------------------------------------------
# §0.3 Records (returned by read ports OP-1..OP-9, OP-11)
# ---------------------------------------------------------------------------
class UserRecordDTO(_DTO):
    id: str
    display_name: str
    role: Literal["student", "staff", "faculty", "privileged"]


class GroupRecordDTO(_DTO):
    id: str
    name: str
    members: list[EntityKey]


class ModelCatalogEntryDTO(_DTO):
    id: str
    name: str
    allowed_roles: list[Literal["student", "staff", "faculty", "privileged"]]


class AccessPolicyClauseDTO(_DTO):
    clause_id: str
    model_id: str
    rule: str
    reason_class: ReasonClass
    text: str


class JobRecordDTO(_DTO):
    id: str
    group_id: str
    course: str
    status: Literal["pending", "running", "succeeded", "cancelled", "failed"]
    scheduling_constraint: Optional[str] = None
    created_at: Instant


class NodeRecordDTO(_DTO):
    id: str
    hostname: str
    gpu_memory_gb: int
    status: Literal["available", "reserved", "active", "fault"]
    cordoned: bool
    error_code: Optional[str] = None
    health: str


class ReservationRecordDTO(_DTO):
    id: str
    node_id: str
    start: Instant
    end: Instant
    purpose: str


class PolicyWindowDTO(_DTO):
    window_id: str
    applies_to: str
    start: Instant
    end: Instant
    timezone: str


class OperationalEventDTO(_DTO):
    event_id: str
    type: EventType
    entity_ref: EntityKey
    timestamp: Instant
    outcome: str
    recorded_reason: str


RecordDTO = Union[
    UserRecordDTO, GroupRecordDTO, ModelCatalogEntryDTO, AccessPolicyClauseDTO,
    JobRecordDTO, NodeRecordDTO, ReservationRecordDTO, PolicyWindowDTO, OperationalEventDTO,
]

# ---------------------------------------------------------------------------
# §0.4 Answer composition+ runbook template (§1 lookup_runbook)
# ---------------------------------------------------------------------------
class ClockReadDTO(_DTO):
    read_id: str
    instant: Instant
    source: Literal["clock"]


class EvidenceDTO(_DTO):
    """One cited source. Within an ``EvidenceSet`` positions are assigned at assembly time and
    form the contiguous sequence ``0..n-1`` with no gaps (E21; enforced by ``AnswerDTO``)."""

    citation_id: CitationId
    source_type: Literal[
        "user", "group", "model", "policy", "node", "job", "reservation", "window", "event", "clock"
    ]
    snippet: Snippet
    position: int = Field(ge=0)


EvidenceSetDTO = list[EvidenceDTO]

# ProseText / ProsePrompt (§0.4; consumed by OP-14 llm_prose_port)
ProseText = str


class ProsePromptDTO(_DTO):
    evidence_sections: list[str]
    instruction: str


class ClaimDTO(_DTO):
    claim_id: str
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    claim_citations: list[CitationId] = Field(min_length=1)


_ANSWER_STAGES = ["observation", "evidence", "diagnosis", "recommendation", "proposal", "execution"]


class AnswerDTO(_DTO):
    answer_id: str
    session_id: SessionId
    query: QueryText
    intent: str
    answer_chain: list[AnswerStage]
    diagnosis_class: Optional[DiagnosisClass] = None
    canonical: Optional[CanonicalCode] = None
    claims: list[ClaimDTO]
    evidence: EvidenceSetDTO
    recommendation: Optional[dict] = None
    proposal_ref: Optional[str] = None
    prose: str

    @model_validator(mode="after")
    def _validate_chain_and_positions(self) -> "AnswerDTO":
        # answer_chain is a contiguous prefix: never reordered, never skipped (E18).
        if list(self.answer_chain) != _ANSWER_STAGES[: len(self.answer_chain)]:
            raise ValueError(
                "answer_chain must be a contiguous prefix of "
                f"{_ANSWER_STAGES} (E18)"
            )
        # evidence positions are the contiguous sequence 0..n-1 (E21).
        positions = [e.position for e in self.evidence]
        if positions != list(range(len(positions))):
            raise ValueError("evidence positions must be 0..n-1 with no gaps (E21)")
        return self


class AnswerEnvelopeDTO(_DTO):
    answers: list[AnswerDTO] = Field(min_length=1)
    # Composition assertion only; excluded from serialization so the wire shape stays {answers}.
    compound: bool = Field(default=False, exclude=True)

    @model_validator(mode="after")
    def _validate_compound(self) -> "AnswerEnvelopeDTO":
        if self.compound and len(self.answers) < 2:
            raise ValueError("a compound answer envelope must carry >= 2 answers (E17)")
        return self


class RunbookTemplateDTO(_DTO):
    template_id: str
    error_code: str
    steps: list[str] = Field(min_length=1)
    required_tools: list[str]
    safety_warnings: list[str]
    physical_intervention: bool
    approved_source: Optional[str] = None
    version: str


# ---------------------------------------------------------------------------
# Session / audit (§2 get_session / get_audit_page; ARCH §2.2)
# ---------------------------------------------------------------------------
class SessionContextDTO(_DTO):
    resolved_entities: list[EntityKey]
    prior_intents: list[str]
    active_answer_ids: list[str]


class SessionDTO(_DTO):
    session_id: SessionId
    created_at: Instant
    operator_role: OperatorRole
    context: SessionContextDTO
    status: Literal["active", "reset", "expired"]


class ToolCallDTO(_DTO):
    tool_call_id: str
    session_id: SessionId
    tool_name: str
    params_summary: dict
    timestamp: Instant
    status: Literal["ok", "failure"]


class AuditRecordDTO(_DTO):
    audit_id: str
    tool_call_id: Optional[str] = None
    session_id: Optional[SessionId] = None
    operator_role: Optional[OperatorRole] = None
    timestamp: Instant
    result_summary: dict
    actor: Literal["copilot", "executor"]
    proposal_id: Optional[str] = None


# ---------------------------------------------------------------------------
# §0.5 Safety / proposal types
# ---------------------------------------------------------------------------
class SelectorDTO(_DTO):
    method: str
    params: dict


class AffectedItemDTO(_DTO):
    key: EntityKey
    actionable: bool
    actionable_field: str
    actionable_value: str


class DryRunSnapshotDTO(_DTO):
    selector: SelectorDTO
    affected_items: list[AffectedItemDTO]
    snapshot_timestamp: Instant


class ConfirmationDTO(_DTO):
    confirmed_at: Instant
    caption: str  # always the S_CAP literal (AD-5 amendment, A15)


class ExecutorResultDTO(_DTO):
    status: ExecutorStatus
    applied_records: list[EntityKey]
    applied_count: int = Field(ge=0)
    timestamp: Instant
    source: Literal["executor"]


class ProposalDTO(_DTO):
    proposal_id: str
    session_id: SessionId
    state: ProposalState
    action: ActionVerb
    supersedes_proposal_id: Optional[str] = None
    dry_run_snapshot: DryRunSnapshotDTO
    gate_token: GateToken
    confirmation: Optional[ConfirmationDTO] = None
    executor_result: Optional[ExecutorResultDTO] = None


class ExecutorRequestDTO(_DTO):
    """Frozen executor contract payload (AD-15)."""

    proposal_id: str
    action: ActionVerb
    selector: SelectorDTO
    gate_token: GateToken
    dry_run_ref: dict  # {proposal_id}

    @model_validator(mode="after")
    def _dry_run_ref_matches(self) -> "ExecutorRequestDTO":
        if self.dry_run_ref.get("proposal_id") != self.proposal_id:
            raise ValueError("dry_run_ref.proposal_id must equal proposal_id (E16)")
        return self


# ===========================================================================
# §2 Inbound operations — one Request DTO + one Response DTO per operation
# ===========================================================================

# --- create_session — POST /api/v1/sessions --------------------------------
class CreateSessionRequest(_DTO):
    operator_role: OperatorRole


class CreateSessionResponse(_DTO):
    session_id: SessionId
    created_at: Instant
    operator_role: OperatorRole
    context: SessionContextDTO
    status: Literal["active", "reset", "expired"]


# --- submit_query — POST /api/v1/sessions/{sid}/queries --------------------
class SubmitQueryRequest(_DTO):
    """Request body only. The path ``{sid}`` is supplied by the route; a body carrying a
    ``session_id`` (or a body ``session_id`` that differs from the path) is rejected as
    ``VALIDATION_MALFORMED_BODY`` (A26, E48)."""

    query_text: QueryText


class SubmitQueryResponse(_DTO):
    answers: list[AnswerDTO] = Field(min_length=1)


# --- get_session — GET /api/v1/sessions/{sid} ------------------------------
class GetSessionRequest(_DTO):
    session_id: SessionId          # path {sid}


class GetSessionResponse(_DTO):
    session_id: SessionId
    created_at: Instant
    operator_role: OperatorRole
    context: SessionContextDTO
    status: Literal["active", "reset", "expired"]
    turns: list[AnswerDTO] = Field(default_factory=list)


# --- reset_session — DELETE /api/v1/sessions/{sid} -------------------------
class ResetSessionRequest(_DTO):
    session_id: SessionId          # path {sid}


class ResetSessionResponse(_DTO):
    """HTTP 204 No Content — empty body."""


# --- get_state_record — GET /api/v1/state/{entity_type}/{id} ---------------
class GetStateRecordRequest(_DTO):
    """Path parameters only — no request body (A26)."""

    entity_type: EntityTypeRoute   # path param, not a body field
    id: str                        # path param, not a body field


class GetStateRecordResponse(_DTO):
    record: RecordDTO


# --- browse_state — GET /api/v1/state/{entity_type}?q=&page=&page_size= ----
class BrowseStateRequest(_DTO):
    """Path + query parameters only — no request body (A26)."""

    entity_type: EntityTypeRoute   # path param, not a body field
    q: str = ""
    page: Page = 1
    page_size: PageSize = 20


class BrowseStateResponse(_DTO):
    items: list[RecordDTO]
    page: Page
    page_size: PageSize
    total: int = Field(ge=0)


# --- get_answer_evidence — GET /api/v1/answers/{aid}/evidence --------------
class GetAnswerEvidenceRequest(_DTO):
    answer_id: str                 # path {aid}


class GetAnswerEvidenceResponse(_DTO):
    evidence: EvidenceSetDTO


# --- get_citation — GET /api/v1/citations/{cid} ----------------------------
class GetCitationRequest(_DTO):
    citation_id: CitationId        # path {cid}


class GetCitationResponse(_DTO):
    source_record: RecordDTO
    snippet: Snippet


# --- get_runbook — GET /api/v1/runbooks/{error_code} -----------------------
class GetRunbookRequest(_DTO):
    error_code: str                # path


class GetRunbookResponse(_DTO):
    steps: list[str] = Field(min_length=1)
    provenance: dict


# --- get_audit_page — GET /api/v1/sessions/{sid}/audit ---------------------
class GetAuditPageRequest(_DTO):
    session_id: SessionId          # path {sid}
    page: Page = 1
    page_size: PageSize = 20


class GetAuditPageResponse(_DTO):
    entries: list[AuditRecordDTO]
    page: Page
    page_size: PageSize
    total: int = Field(ge=0)       # retained-row count (clamped to the 10,000-row cap)
    has_more: bool                 # true when further retained pages exist (E36)


# --- post_dry_run — POST /api/v1/destructive/dry-runs ----------------------
class PostDryRunRequest(_DTO):
    query_text: QueryText
    action: ActionVerb
    target_refs: list[RawRef] = Field(min_length=1)
    session_id: SessionId


class PostDryRunResponse(_DTO):
    proposal_id: str
    session_id: SessionId
    state: ProposalState
    action: ActionVerb
    supersedes_proposal_id: Optional[str] = None
    dry_run_snapshot: DryRunSnapshotDTO
    gate_token: GateToken
    confirmation: Optional[ConfirmationDTO] = None
    executor_result: Optional[ExecutorResultDTO] = None


# --- post_confirm — POST /api/v1/destructive/proposals ---------------------
class PostConfirmRequest(_DTO):
    proposal_id: str
    gate_token: GateToken


class PostConfirmResponse(_DTO):
    proposal_id: str
    session_id: SessionId
    state: ProposalState
    action: ActionVerb
    supersedes_proposal_id: Optional[str] = None
    dry_run_snapshot: DryRunSnapshotDTO
    gate_token: GateToken
    confirmation: Optional[ConfirmationDTO] = None
    executor_result: Optional[ExecutorResultDTO] = None


# --- get_proposal — GET /api/v1/destructive/proposals/{pid} ----------------
class GetProposalRequest(_DTO):
    proposal_id: str               # path {pid}


class GetProposalResponse(_DTO):
    proposal_id: str
    session_id: SessionId
    state: ProposalState
    action: ActionVerb
    supersedes_proposal_id: Optional[str] = None
    dry_run_snapshot: DryRunSnapshotDTO
    gate_token: GateToken
    confirmation: Optional[ConfirmationDTO] = None
    executor_result: Optional[ExecutorResultDTO] = None


# --- post_re_dispatch — POST /api/v1/destructive/proposals/{pid}/re-dispatches
class PostReDispatchRequest(_DTO):
    parent_proposal_id: str        # path {pid}
    query_text: QueryText
    action: ActionVerb
    target_refs: list[RawRef] = Field(min_length=1)


class PostReDispatchResponse(_DTO):
    proposal_id: str
    session_id: SessionId
    state: ProposalState
    action: ActionVerb
    supersedes_proposal_id: Optional[str] = None
    dry_run_snapshot: DryRunSnapshotDTO
    gate_token: GateToken
    confirmation: Optional[ConfirmationDTO] = None
    executor_result: Optional[ExecutorResultDTO] = None


# --- executor_post_proposal — POST /executor/v1/proposals ------------------
class ExecutorPostProposalRequest(_DTO):
    proposal_id: str
    action: ActionVerb
    selector: SelectorDTO
    gate_token: GateToken
    dry_run_ref: dict              # {proposal_id}

    @model_validator(mode="after")
    def _dry_run_ref_matches(self) -> "ExecutorPostProposalRequest":
        if self.dry_run_ref.get("proposal_id") != self.proposal_id:
            raise ValueError("dry_run_ref.proposal_id must equal proposal_id (E16)")
        return self


class ExecutorPostProposalResponse(_DTO):
    status: ExecutorStatus
    applied_records: list[EntityKey]
    applied_count: int = Field(ge=0)
    timestamp: Instant
    source: Literal["executor"]


# --- executor_get_proposal — GET /executor/v1/proposals/{pid} --------------
class ExecutorGetProposalRequest(_DTO):
    proposal_id: str               # path {pid}


class ExecutorGetProposalResponse(_DTO):
    status: ExecutorStatus
    applied_records: list[EntityKey]
    applied_count: int = Field(ge=0)
    timestamp: Instant
    source: Literal["executor"]


# ===========================================================================
# §3 Outbound generation / prose ports (OP-13 idgen_port, OP-14 llm_prose_port)
# ===========================================================================
class IdGenRequest(_DTO):
    """OP-13 idgen_port.new_id(kind: IdKind)."""

    kind: IdKind


class IdGenResponse(_DTO):
    """OP-13 result: a fresh IdString in the per-kind format of §0.1."""

    id: IdString


class ComposeProseRequest(_DTO):
    """OP-14 llm_prose_port.compose(prompt: ProsePrompt)."""

    evidence_sections: list[str]
    instruction: str


class ComposeProseResponse(_DTO):
    """OP-14 result: connective prose with zero evidence-vocabulary tokens (AD-8)."""

    prose: ProseText
