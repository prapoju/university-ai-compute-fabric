"""Pure access-denial diagnosis, evidence set and claims (contracts.md section 1, AD-2/8/14)."""

from __future__ import annotations

import pytest

from src.domain.diagnosis import (
    AccessDenialDiagnosis,
    CannotConfirm,
    diagnose_access_denial,
)
from src.dto import (
    AccessPolicyClauseDTO,
    ClockReadDTO,
    ModelCatalogEntryDTO,
    OperationalEventDTO,
    UserRecordDTO,
)
from src.ports.outbound import EventWindow

pytestmark = pytest.mark.unit

CLOCK = ClockReadDTO(
    read_id="clk-0000000000000001", instant="2026-10-16T15:00:00.000Z", source="clock"
)
WINDOW = EventWindow("2026-09-16T15:00:00.000Z", "2026-10-16T15:00:00.001Z")


def _value(result):
    return result.value


def _inputs(providers, user_key: str, model_key: str):
    user = _value(providers.users.get(user_key))
    model = _value(providers.catalog.get(model_key))
    clauses = _value(providers.policy.for_model(model_key))
    events = _value(providers.event_store.query(user_key, "access_denied", WINDOW))
    return user, model, clauses, events


def _diagnose(providers, user_key="user#alex", model_key="model#deepseek-coder"):
    user, model, clauses, events = _inputs(providers, user_key, model_key)
    return diagnose_access_denial(user, model, clauses, events, CLOCK)


# -- the S1 happy path -------------------------------------------------------------------------
def test_s1_is_diagnosed_as_not_in_allowlist_with_the_exact_clause_and_event(providers) -> None:
    result = _diagnose(providers)
    assert isinstance(result, AccessDenialDiagnosis)
    assert result.diagnosis_class == "access_denial_not_in_allowlist"
    assert result.clause.clause_id == "policy#catalog.4.2" and result.clause.rule == "RULE-CAT-04"
    assert result.event.event_id == "event#evt-4711"


def test_the_evidence_set_is_ordered_unique_and_contiguous(providers) -> None:
    evidence = _diagnose(providers).evidence
    assert [e.citation_id for e in evidence] == [
        "user#alex",
        "model#deepseek-coder",
        "policy#catalog.4.2",
        "event#evt-4711",
        "clock#clk-0000000000000001",
    ]
    assert [e.source_type for e in evidence] == ["user", "model", "policy", "event", "clock"]
    assert [e.position for e in evidence] == [0, 1, 2, 3, 4]
    assert all(1 <= len(e.snippet) <= 500 for e in evidence)


def test_every_snippet_states_the_record_it_cites(providers) -> None:
    by_id = {e.citation_id: e.snippet for e in _diagnose(providers).evidence}
    assert "role student" in by_id["user#alex"]
    assert "staff, faculty, privileged" in by_id["model#deepseek-coder"]
    assert "RULE-CAT-04" in by_id["policy#catalog.4.2"] and "CS-480" in by_id["policy#catalog.4.2"]
    assert "not-in-allowlist: policy#catalog.4.2" in by_id["event#evt-4711"]
    assert "2026-10-16T15:00:00.000Z" in by_id["clock#clk-0000000000000001"]


def test_three_claims_state_role_clause_and_reason_class(providers) -> None:
    claims = _diagnose(providers).claims
    assert len(claims) == 3
    role, clause, reason = (c.text for c in claims)
    assert "role student" in role
    assert "policy#catalog.4.2" in clause and "RULE-CAT-04" in clause and "CS-480" in clause
    assert "not-in-allowlist" in reason and "event#evt-4711" in reason


def test_every_claim_cites_the_user_the_clause_and_the_event_and_only_real_evidence(
    providers,
) -> None:
    result = _diagnose(providers)
    evidence_ids = {e.citation_id for e in result.evidence}
    for claim in result.claims:
        assert {"user#alex", "policy#catalog.4.2", "event#evt-4711"} <= set(claim.citations)
        assert set(claim.citations) <= evidence_ids  # a citation never points outside the set
        assert len(claim.citations) == len(set(claim.citations))


def test_the_fact_tokens_cover_everything_prose_must_not_say(providers) -> None:
    tokens = _diagnose(providers).fact_tokens
    for expected in (
        "user#alex", "alex", "alex rivera", "student", "model#deepseek-coder", "deepseek-coder",
        "staff", "faculty", "privileged", "policy#catalog.4.2", "catalog.4.2", "rule-cat-04",
        "not-in-allowlist", "event#evt-4711", "evt-4711", "denied", "2026-10-16", "15:00:00",
        "clk-0000000000000001", "13:42:10",
    ):  # fmt: skip
        assert expected in tokens, expected


def test_a_second_student_is_diagnosed_from_their_own_event(providers) -> None:
    result = _diagnose(providers, "user#mateo")
    assert isinstance(result, AccessDenialDiagnosis)
    assert result.event.event_id == "event#evt-4713"
    assert result.diagnosis_class == "access_denial_not_in_allowlist"
    assert "user#mateo" in result.claims[0].citations


# -- AD-2: pure and deterministic --------------------------------------------------------------
def test_the_same_inputs_give_identical_results_and_inputs_are_not_mutated(providers) -> None:
    user, model, clauses, events = _inputs(providers, "user#alex", "model#deepseek-coder")
    before = (
        user.model_dump(),
        [c.model_dump() for c in clauses],
        [e.model_dump() for e in events],
    )
    first = diagnose_access_denial(user, model, clauses, events, CLOCK)
    second = diagnose_access_denial(user, model, clauses, events, CLOCK)
    assert first == second
    assert before == (
        user.model_dump(),
        [c.model_dump() for c in clauses],
        [e.model_dump() for e in events],
    )


def test_input_order_does_not_change_the_result(providers) -> None:
    user, model, clauses, events = _inputs(providers, "user#alex", "model#deepseek-coder")
    assert diagnose_access_denial(user, model, clauses, events, CLOCK) == diagnose_access_denial(
        user, model, list(reversed(clauses)), list(reversed(events)), CLOCK
    )


# -- cannot confirm ----------------------------------------------------------------------------
def test_an_existing_student_without_a_recorded_denial_cannot_be_confirmed(providers) -> None:
    result = _diagnose(providers, "user#sofia")
    assert isinstance(result, CannotConfirm)
    assert result.checked == (
        "user#sofia",
        "model#deepseek-coder",
        "policy clauses for model#deepseek-coder",
        "access_denied events for user#sofia",
    )
    ids = [e.citation_id for e in result.evidence]
    assert ids[:3] == ["user#sofia", "model#deepseek-coder", "policy#catalog.4.2"]
    assert ids[-1] == "clock#clk-0000000000000001"  # what was gathered is kept for audit
    assert [e.position for e in result.evidence] == list(range(len(ids)))


def test_a_privileged_user_is_allowed_so_no_clause_explains_a_denial(providers) -> None:
    result = _diagnose(providers, "user#dr-vance")
    assert isinstance(result, CannotConfirm)


def test_a_clause_without_a_matching_event_cannot_be_confirmed(providers) -> None:
    user, model, clauses, _ = _inputs(providers, "user#sofia", "model#deepseek-coder")
    assert isinstance(diagnose_access_denial(user, model, clauses, [], CLOCK), CannotConfirm)


def test_an_event_that_cites_no_applicable_clause_does_not_confirm_a_denial(providers) -> None:
    user, model, clauses, _ = _inputs(providers, "user#alex", "model#deepseek-coder")
    stray = OperationalEventDTO(
        event_id="event#evt-9999", type="access_denied", entity_ref="user#alex",
        timestamp="2026-10-16T10:00:00.000Z", outcome="denied",
        recorded_reason="something unrelated",
    )  # fmt: skip
    assert isinstance(diagnose_access_denial(user, model, clauses, [stray], CLOCK), CannotConfirm)


# -- precedence and the other reason classes (contracts Q1) ------------------------------------
def _model(roles) -> ModelCatalogEntryDTO:
    return ModelCatalogEntryDTO(id="model#m", name="m", allowed_roles=roles)


def _clause(cid: str, reason: str) -> AccessPolicyClauseDTO:
    return AccessPolicyClauseDTO(
        clause_id=cid,
        model_id="model#m",
        rule=f"rule for {cid}",
        reason_class=reason,
        text=f"text of {cid}",
    )


def _event(eid: str, cites: str, when: str = "2026-10-16T10:00:00.000Z") -> OperationalEventDTO:
    return OperationalEventDTO(
        event_id=eid, type="access_denied", entity_ref="user#u", timestamp=when,
        outcome="denied", recorded_reason=f"cited: {cites}",
    )  # fmt: skip


USER = UserRecordDTO(id="user#u", display_name="U", role="student")


def test_the_fixed_precedence_is_allowlist_then_quota_then_window() -> None:
    clauses = [
        _clause("policy#w", "window"),
        _clause("policy#q", "quota"),
        _clause("policy#a", "not-in-allowlist"),
    ]
    events = [
        _event("event#e1", "policy#w"),
        _event("event#e2", "policy#q"),
        _event("event#e3", "policy#a"),
    ]
    result = diagnose_access_denial(USER, _model(["staff"]), clauses, events, CLOCK)
    assert (result.diagnosis_class, result.clause.clause_id) == (
        "access_denial_not_in_allowlist",
        "policy#a",
    )
    # allowed role: the allowlist clause does not apply, so quota wins over window
    result = diagnose_access_denial(USER, _model(["student"]), clauses, events, CLOCK)
    assert (result.diagnosis_class, result.clause.clause_id) == ("access_denial_quota", "policy#q")
    result = diagnose_access_denial(USER, _model(["student"]), [clauses[0]], [events[0]], CLOCK)
    assert (result.diagnosis_class, result.clause.clause_id) == ("access_denial_window", "policy#w")


def test_with_several_denial_events_the_latest_one_is_cited() -> None:
    clauses = [_clause("policy#a", "not-in-allowlist")]
    events = [
        _event("event#old", "policy#a", "2026-10-01T10:00:00.000Z"),
        _event("event#new", "policy#a", "2026-10-15T10:00:00.000Z"),
    ]
    result = diagnose_access_denial(USER, _model(["staff"]), clauses, events, CLOCK)
    assert result.event.event_id == "event#new"


def test_the_clause_cited_is_case_folded_so_formatting_does_not_hide_it() -> None:
    clauses = [_clause("policy#a", "not-in-allowlist")]
    events = [_event("event#e", "POLICY#A")]
    assert isinstance(
        diagnose_access_denial(USER, _model(["staff"]), clauses, events, CLOCK),
        AccessDenialDiagnosis,
    )


def test_a_very_long_clause_text_is_clipped_to_the_snippet_limit() -> None:
    long_clause = AccessPolicyClauseDTO(
        clause_id="policy#a",
        model_id="model#m",
        rule="r",
        reason_class="not-in-allowlist",
        text="x" * 1800,
    )
    result = diagnose_access_denial(
        USER, _model(["staff"]), [long_clause], [_event("event#e", "policy#a")], CLOCK
    )
    snippet = next(e.snippet for e in result.evidence if e.source_type == "policy")
    assert len(snippet) == 500 and snippet.endswith("...")


# -- review patches: a clause must be backed by an event that really cites it -----------------
def test_a_backed_lower_precedence_denial_is_not_hidden_by_an_unbacked_allowlist_clause() -> None:
    clauses = [_clause("policy#a", "not-in-allowlist"), _clause("policy#q", "quota")]
    events = [_event("event#e1", "policy#q")]  # nothing cites the allowlist clause
    result = diagnose_access_denial(USER, _model(["staff"]), clauses, events, CLOCK)
    assert isinstance(result, AccessDenialDiagnosis)
    assert (result.diagnosis_class, result.event.event_id) == ("access_denial_quota", "event#e1")


def test_an_allowlist_clause_nobody_cites_is_still_cannot_confirm() -> None:
    result = diagnose_access_denial(
        USER, _model(["staff"]), [_clause("policy#a", "not-in-allowlist")], [], CLOCK
    )
    assert isinstance(result, CannotConfirm)


@pytest.mark.parametrize(
    ("clause_id", "reason", "cited"),
    [
        ("policy#c.4.2", "not-in-allowlist: policy#c.4.20", False),  # longer id, same prefix
        ("policy#c.4.2", "not-in-allowlist: policy#c.4.2x", False),
        ("policy#c.4.2", "see policy#xpolicy#c.4.2", False),
        ("policy#c.4.2", "not-in-allowlist: policy#c.4.2", True),
        ("policy#c.4.2", "not-in-allowlist: POLICY#C.4.2.", True),  # case and a sentence dot
        ("policy#c.4.2", "(policy#c.4.2), quota", True),
        ("policy#c.4.2", "not-in-allowlist:policy#c.4.2", True),
    ],
)
def test_a_clause_is_cited_only_as_a_whole_token(clause_id: str, reason: str, cited: bool) -> None:
    event = _event("event#e", clause_id).model_copy(update={"recorded_reason": reason})
    result = diagnose_access_denial(
        USER, _model(["staff"]), [_clause(clause_id, "not-in-allowlist")], [event], CLOCK
    )
    assert isinstance(result, AccessDenialDiagnosis) is cited
