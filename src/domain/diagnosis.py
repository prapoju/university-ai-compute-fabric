"""Pure access-denial diagnosis: evidence set, structured claims, class (contracts.md section 1).

Everything here is a deterministic function of its inputs (AD-2): the diagnosis class, the claims
and their citations, and the evidence order never depend on an LLM, a clock read inside this
module, or the order the records arrive in. The application ring does the provider reads and
feeds the records in; ids for the claims are minted by the caller (R2).

What "matching" means (story 1.3, decisions D2/D3):

* a ``not-in-allowlist`` clause applies iff the user's role is not in the model's ``allowed_roles``;
* a ``quota`` / ``window`` clause applies iff one of the user's denial events cites it;
* the clause is chosen by the fixed precedence ``not-in-allowlist > quota > window``;
* the denial must be backed by an ``access_denied`` event of the user that cites that clause -
  otherwise the answer is ``CannotConfirm`` (FR-04: "a referenced denial event must exist").
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from src.domain.instants import parse_instant
from src.dto import (
    AccessPolicyClauseDTO,
    ClockReadDTO,
    EvidenceDTO,
    ModelCatalogEntryDTO,
    OperationalEventDTO,
    UserRecordDTO,
)

SNIPPET_LIMIT = 500  # EvidenceDTO.snippet (contracts.md section 0.1 Snippet)

_PRECEDENCE = ("not-in-allowlist", "quota", "window")
_CLASS = {
    "not-in-allowlist": "access_denial_not_in_allowlist",
    "quota": "access_denial_quota",
    "window": "access_denial_window",
}


@dataclass(frozen=True)
class ClaimDraft:
    """A structured claim before its id is minted: text plus the citation ids it rests on."""

    text: str
    citations: tuple[str, ...]


@dataclass(frozen=True)
class AccessDenialDiagnosis:
    diagnosis_class: str
    clause: AccessPolicyClauseDTO
    event: OperationalEventDTO
    evidence: tuple[EvidenceDTO, ...]
    claims: tuple[ClaimDraft, ...]
    fact_tokens: frozenset[str]  # everything prose must not say (AD-8)


@dataclass(frozen=True)
class CannotConfirm:
    """The user and model exist but no clause/event confirms a denial (``S_CNC``)."""

    checked: tuple[str, ...]
    evidence: tuple[EvidenceDTO, ...]  # what was gathered, kept on the stored Answer for audit


Outcome = AccessDenialDiagnosis | CannotConfirm


def diagnose_access_denial(
    user: UserRecordDTO,
    model: ModelCatalogEntryDTO,
    clauses: Sequence[AccessPolicyClauseDTO],
    events: Sequence[OperationalEventDTO],
    clock: ClockReadDTO,
) -> Outcome:
    """Explain why ``user`` was denied ``model``, or say that it cannot be confirmed."""
    denials = [e for e in events if _is_denial_of(e, user)]
    checked = (
        user.id,
        model.id,
        f"policy clauses for {model.id}",
        f"access_denied events for {user.id}",
    )

    applicable = [c for c in clauses if _applies(c, user, model, denials)]
    if not applicable:
        return CannotConfirm(checked, _audit_evidence(user, model, clauses, denials, clock))

    clause = min(applicable, key=lambda c: (_PRECEDENCE.index(c.reason_class), c.clause_id))
    citing = [e for e in denials if _cites(e, clause)]
    if not citing:
        return CannotConfirm(checked, _audit_evidence(user, model, clauses, denials, clock))
    event = max(citing, key=lambda e: (parse_instant(e.timestamp), e.event_id))

    evidence = _number(
        [
            ("user", user.id, _user_snippet(user)),
            ("model", model.id, _model_snippet(model)),
            ("policy", clause.clause_id, _clause_snippet(clause)),
            ("event", event.event_id, _event_snippet(event)),
            _clock_entry(clock),
        ]
    )
    return AccessDenialDiagnosis(
        diagnosis_class=_CLASS[clause.reason_class],
        clause=clause,
        event=event,
        evidence=evidence,
        claims=_claims(user, model, clause, event),
        fact_tokens=_fact_tokens(user, model, clause, event, clock, _CLASS[clause.reason_class]),
    )


# -- matching ----------------------------------------------------------------------------------
def _is_denial_of(event: OperationalEventDTO, user: UserRecordDTO) -> bool:
    return event.type == "access_denied" and event.entity_ref.casefold() == user.id.casefold()


def _cites(event: OperationalEventDTO, clause: AccessPolicyClauseDTO) -> bool:
    return clause.clause_id.casefold() in event.recorded_reason.casefold()


def _applies(
    clause: AccessPolicyClauseDTO,
    user: UserRecordDTO,
    model: ModelCatalogEntryDTO,
    denials: Iterable[OperationalEventDTO],
) -> bool:
    if clause.model_id.casefold() != model.id.casefold():
        return False
    if clause.reason_class == "not-in-allowlist":
        return user.role not in model.allowed_roles
    return any(_cites(event, clause) for event in denials)


# -- evidence ----------------------------------------------------------------------------------
def _clip(text: str) -> str:
    return text if len(text) <= SNIPPET_LIMIT else text[: SNIPPET_LIMIT - 3] + "..."


def _user_snippet(user: UserRecordDTO) -> str:
    return _clip(f"{user.id}: {user.display_name}, role {user.role}")


def _model_snippet(model: ModelCatalogEntryDTO) -> str:
    return _clip(f"{model.id}: {model.name}, allowed roles {', '.join(model.allowed_roles)}")


def _clause_snippet(clause: AccessPolicyClauseDTO) -> str:
    return _clip(f"{clause.clause_id} ({clause.rule}) [{clause.reason_class}]: {clause.text}")


def _event_snippet(event: OperationalEventDTO) -> str:
    return _clip(
        f"{event.event_id}: {event.type} at {event.timestamp}, outcome {event.outcome}; "
        f"recorded reason: {event.recorded_reason}"
    )


def _clock_entry(clock: ClockReadDTO) -> tuple[str, str, str]:
    return "clock", f"clock#{clock.read_id}", f"clock read {clock.read_id} at {clock.instant}"


def _number(entries: Iterable[tuple[str, str, str]]) -> tuple[EvidenceDTO, ...]:
    """Assign ``position`` 0..n-1 at assembly time (AD-14); ids are unique by construction."""
    return tuple(
        EvidenceDTO(citation_id=cid, source_type=kind, snippet=snippet, position=position)
        for position, (kind, cid, snippet) in enumerate(entries)
    )


def _audit_evidence(
    user: UserRecordDTO,
    model: ModelCatalogEntryDTO,
    clauses: Sequence[AccessPolicyClauseDTO],
    denials: Sequence[OperationalEventDTO],
    clock: ClockReadDTO,
) -> tuple[EvidenceDTO, ...]:
    ordered_clauses = sorted(clauses, key=lambda c: c.clause_id)
    ordered_events = sorted(denials, key=lambda e: (parse_instant(e.timestamp), e.event_id))
    return _number(
        [
            ("user", user.id, _user_snippet(user)),
            ("model", model.id, _model_snippet(model)),
            *(("policy", c.clause_id, _clause_snippet(c)) for c in ordered_clauses),
            *(("event", e.event_id, _event_snippet(e)) for e in ordered_events),
            _clock_entry(clock),
        ]
    )


# -- claims ------------------------------------------------------------------------------------
def _claims(
    user: UserRecordDTO,
    model: ModelCatalogEntryDTO,
    clause: AccessPolicyClauseDTO,
    event: OperationalEventDTO,
) -> tuple[ClaimDraft, ...]:
    # contracts Q4: every claim cites the user, the clause and the denial event (plus the model)
    cites = (user.id, model.id, clause.clause_id, event.event_id)
    roles = ", ".join(model.allowed_roles)
    return (
        ClaimDraft(
            f"{user.display_name} ({user.id}) has role {user.role}; "
            f"{model.name} ({model.id}) allows the roles {roles}.",
            cites,
        ),
        ClaimDraft(
            f"Clause {clause.clause_id} ({clause.rule}) applies to {model.name}: {clause.text}",
            cites,
        ),
        ClaimDraft(
            f"The reason class is {clause.reason_class}, recorded by {event.event_id}: "
            f"{event.recorded_reason}.",
            cites,
        ),
    )


# -- the vocabulary the prose guard must keep out of prose -------------------------------------
def _bare(key: str) -> str:
    return key.partition("#")[2] or key


def _fact_tokens(
    user: UserRecordDTO,
    model: ModelCatalogEntryDTO,
    clause: AccessPolicyClauseDTO,
    event: OperationalEventDTO,
    clock: ClockReadDTO,
    diagnosis_class: str,
) -> frozenset[str]:
    tokens = {
        user.id, _bare(user.id), user.display_name, user.role,
        model.id, _bare(model.id), model.name, *model.allowed_roles,
        clause.clause_id, _bare(clause.clause_id), clause.rule, clause.reason_class,
        event.event_id, _bare(event.event_id), event.outcome, event.timestamp,
        event.timestamp[:10], event.timestamp[11:19],
        clock.read_id, clock.instant, clock.instant[:10], clock.instant[11:19],
        diagnosis_class,
    }  # fmt: skip
    tokens.update(word for word in user.display_name.split() if len(word) >= 3)
    return frozenset(t.casefold() for t in tokens if t)
