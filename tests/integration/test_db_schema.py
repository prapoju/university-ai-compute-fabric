"""`db` — the migrated Module 12 schema enforces its declared invariants (AD-3/4/8/10/15)."""

from __future__ import annotations

import sqlite3

import pytest

from support.db import MIN_SQLITE_VERSION, OWNED_TABLES, require_sqlite_version

pytestmark = pytest.mark.integration


def _seed_session_and_answer(db, sample):
    session = sample.session_row()
    db.insert("sessions", session)
    answer = sample.answer_row(session_id=session["session_id"])
    db.insert("answers", answer)
    return session, answer


def test_engine_supports_returning_and_json1() -> None:
    assert require_sqlite_version() >= MIN_SQLITE_VERSION


def test_all_owned_tables_and_key_triggers_exist(db) -> None:
    tables = set(db.tables())
    assert set(OWNED_TABLES) <= tables

    triggers = set(db.triggers())
    assert {
        "trg_audit_records_no_update",
        "trg_audit_records_no_delete",
        "trg_audit_events_no_update",
        "trg_audit_events_no_delete",
        "trg_claim_citations_guard_delete",
        "trg_proposals_state_machine",
    } <= triggers

    indexes = set(db.indexes())
    assert {"ux_audit_tool_call", "ux_audit_executor_apply"} <= indexes


def test_audit_records_are_append_only(db, sample) -> None:
    session, _ = _seed_session_and_answer(db, sample)
    row = sample.audit_row(session_id=session["session_id"])
    db.insert("audit_records", row)

    with pytest.raises(sqlite3.IntegrityError):        # AD-10: no UPDATE, ever
        db.execute("UPDATE audit_records SET result_summary = '{}' WHERE audit_id = ?",
                   (row["audit_id"],))

    with pytest.raises(sqlite3.IntegrityError):        # D42: delete denied while gate closed
        db.execute("DELETE FROM audit_records WHERE audit_id = ?", (row["audit_id"],))

    db.open_rotation_gate()                            # D42/C9: rotation writer only
    db.execute("DELETE FROM audit_records WHERE audit_id = ?", (row["audit_id"],))
    assert db.count("audit_records") == 0


def test_proposal_state_machine_blocks_illegal_jump(db, sample) -> None:
    session, _ = _seed_session_and_answer(db, sample)
    proposal = sample.proposal_row(session_id=session["session_id"], state="dry_run")
    db.insert("proposals", proposal)

    with pytest.raises(sqlite3.IntegrityError):        # AD-4: dry_run -> executed illegal
        db.execute(
            "UPDATE proposals SET state='executed', confirmed_at=?, executor_status='applied', "
            "applied_records='[\"node#ws-gpu-11\"]', applied_count=1, executor_timestamp=?, "
            "executor_source='executor' WHERE proposal_id=?",
            (sample.now, sample.now, proposal["proposal_id"]),
        )

    db.execute("UPDATE proposals SET state='confirmed', confirmed_at=? WHERE proposal_id=?",
               (sample.now, proposal["proposal_id"]))
    assert db.fetchone("SELECT state FROM proposals WHERE proposal_id=?",
                       (proposal["proposal_id"],))["state"] == "confirmed"


def test_partial_executor_result_must_fail(db, sample) -> None:
    session, _ = _seed_session_and_answer(db, sample)
    ok = sample.proposal_row(session_id=session["session_id"], state="failed",
                             executor_status="partial", applied_records=["node#ws-gpu-11"],
                             executor_timestamp=sample.now)
    db.insert("proposals", ok)                          # D33: partial => failed

    with pytest.raises(sqlite3.IntegrityError):         # D33: partial may not be executed
        bad = sample.proposal_row(session_id=session["session_id"], state="executed",
                                  executor_status="partial", applied_records=["node#ws-gpu-11"],
                                  executor_timestamp=sample.now)
        db.insert("proposals", bad)


def test_evidence_keyed_by_answer_and_citation(db, sample) -> None:
    _, answer = _seed_session_and_answer(db, sample)
    row = sample.evidence_row(answer_id=answer["answer_id"], citation_id="node#ws-gpu-11", position=0)
    db.insert("evidence", row)

    with pytest.raises(sqlite3.IntegrityError):         # AD-14: (answer_id, citation_id) UNIQUE
        db.insert("evidence", dict(row))

    with pytest.raises(sqlite3.IntegrityError):         # AD-14: position unique per answer
        db.insert("evidence", sample.evidence_row(
            answer_id=answer["answer_id"], citation_id="clock#clk-0000000000000001", position=0))


def test_claim_must_retain_a_citation(db, sample) -> None:
    _, answer = _seed_session_and_answer(db, sample)
    db.insert("evidence", sample.evidence_row(
        answer_id=answer["answer_id"], citation_id="node#ws-gpu-11", position=0))
    db.insert("evidence", sample.evidence_row(
        answer_id=answer["answer_id"], citation_id="clock#clk-0000000000000001",
        source_type="clock", position=1))

    claim = sample.claim_row(answer_id=answer["answer_id"])
    db.insert("claims", claim)
    db.insert("claim_citations", sample.claim_citation_row(
        claim_id=claim["claim_id"], answer_id=answer["answer_id"], citation_id="node#ws-gpu-11"))
    db.insert("claim_citations", sample.claim_citation_row(
        claim_id=claim["claim_id"], answer_id=answer["answer_id"], citation_id="clock#clk-0000000000000001"))

    db.execute("DELETE FROM claim_citations WHERE claim_id=? AND citation_id=?",
               (claim["claim_id"], "clock#clk-0000000000000001"))

    with pytest.raises(sqlite3.IntegrityError):         # AD-8: >= 1 citation per claim
        db.execute("DELETE FROM claim_citations WHERE claim_id=? AND citation_id=?",
                   (claim["claim_id"], "node#ws-gpu-11"))


def test_context_arrays_reject_non_strings(db, sample) -> None:
    row = sample.session_row()
    row["context_resolved_entities"] = "[{}, 1]"
    with pytest.raises(sqlite3.IntegrityError):         # E38
        db.insert("sessions", row)
