"""AuditWriter: ids in call order, redaction at write time, typed write failure (I14, I15, D1)."""

from __future__ import annotations

import pytest

from src.adapters.outbound.sim.idgen_adapter import SimIdGen
from src.application.audit_writer import AuditWriter
from src.application.tool_audit import RecordedCall
from src.domain.redaction import REDACTED
from src.domain.result import Failure, Ok, Result, is_ok
from src.dto import ClockReadDTO, SessionContextDTO, SessionDTO
from src.ports.outbound import AuditEntry, AuditStorePort, IdGenPort

pytestmark = pytest.mark.unit

NOW = ClockReadDTO(
    read_id="clk-0000000000000001", instant="2026-10-16T15:00:00.000Z", source="clock"
)
SESSION = SessionDTO(
    session_id="sess-0000000000000001",
    created_at=NOW.instant,
    operator_role="role-operations",
    context=SessionContextDTO(resolved_entities=[], prior_intents=[], active_answer_ids=[]),
    status="active",
)
HEAD = RecordedCall(
    "toolcall.answer_query", {"answer_id": "ans-0000000000000001"}, "ok",
    result={"diagnosis_class": "access_denial_not_in_allowlist"},
)  # fmt: skip


class _MemoryAudit(AuditStorePort):
    def __init__(self, fail: bool = False) -> None:
        self.appended: list[AuditEntry] = []
        self._fail = fail

    def append(self, entries) -> Result[None]:
        if self._fail:
            return Failure("PROVIDER_UNAVAILABLE", observed=("disk full",))
        self.appended.extend(entries)
        return Ok(None)

    def page(self, session_id, offset, limit):
        return Ok(([], 0))

    def highest_counters(self):
        return Ok({})


class _RecordingIdGen(IdGenPort):
    """Delegates to SimIdGen, logs each kind drawn, and fails on the n-th draw."""

    def __init__(self, fail_on: int | None = None) -> None:
        self._inner = SimIdGen()
        self.drawn: list[str] = []
        self._fail_on = fail_on

    def new_id(self, kind: str) -> Result[str]:
        if self._fail_on is not None and len(self.drawn) + 1 == self._fail_on:
            return Failure("PROVIDER_UNAVAILABLE", observed=("idgen down",))
        self.drawn.append(kind)
        return self._inner.new_id(kind)


def test_ids_are_minted_in_call_order_with_the_head_first() -> None:
    idgen = _RecordingIdGen()
    calls = [
        RecordedCall("toolcall.users_port.get", {"id": "user#alex"}, "ok", result_count=1),
        RecordedCall("toolcall.catalog_port.get", {"model_id": "m"}, "failure",
                     error_code="PROVIDER_UNAVAILABLE"),
    ]  # fmt: skip
    entries = AuditWriter(_MemoryAudit(), idgen).entries_for(SESSION, NOW, HEAD, calls)
    assert is_ok(entries)
    assert idgen.drawn == ["tool_call", "audit"] * 3
    rows = entries.value
    assert [e.tool_call.tool_call_id for e in rows] == [f"tc-{n:016x}" for n in (1, 2, 3)]
    assert [e.record.audit_id for e in rows] == [f"aud-{n:016x}" for n in (1, 2, 3)]
    assert [e.record.tool_call_id for e in rows] == [e.tool_call.tool_call_id for e in rows]
    assert [e.record.result_summary for e in rows] == [
        {"tool_name": "toolcall.answer_query", "status": "ok",
         "diagnosis_class": "access_denial_not_in_allowlist"},
        {"tool_name": "toolcall.users_port.get", "status": "ok", "result_count": 1},
        {"tool_name": "toolcall.catalog_port.get", "status": "failure",
         "error_code": "PROVIDER_UNAVAILABLE"},
    ]  # fmt: skip
    for entry in rows:
        assert entry.record.actor == "copilot"
        assert entry.record.timestamp == entry.tool_call.timestamp == NOW.instant
        assert entry.record.session_id == entry.tool_call.session_id == SESSION.session_id
        assert entry.record.operator_role == "role-operations"
    assert [e.tool_call.status for e in rows] == ["ok", "ok", "failure"]


def test_both_summaries_are_redacted() -> None:
    call = RecordedCall(
        "toolcall.users_port.browse", {"q": "Authorization: Bearer sk-live-123", "token": "t"},
        "ok", result={"note": "api_key=abc123"},
    )  # fmt: skip
    entries = AuditWriter(_MemoryAudit(), SimIdGen()).entries_for(SESSION, NOW, call, []).value
    assert entries[0].tool_call.params_summary == {"q": f"Authorization: {REDACTED}",
                                                   "token": REDACTED}  # fmt: skip
    assert entries[0].record.result_summary["note"] == f"api_key={REDACTED}"
    assert call.params["token"] == "t"  # the recorded call itself is not mutated


@pytest.mark.parametrize("fail_on", [1, 2, 4])
def test_an_idgen_failure_is_returned_and_mints_no_further_id(fail_on: int) -> None:
    idgen = _RecordingIdGen(fail_on=fail_on)
    calls = [RecordedCall("toolcall.users_port.get", {"id": "user#alex"}, "ok", result_count=1)]
    result = AuditWriter(_MemoryAudit(), idgen).entries_for(SESSION, NOW, HEAD, calls)
    assert isinstance(result, Failure) and result.observed == ("idgen down",)
    assert len(idgen.drawn) == fail_on - 1


def test_write_appends_through_the_store() -> None:
    store = _MemoryAudit()
    writer = AuditWriter(store, SimIdGen())
    entries = writer.entries_for(SESSION, NOW, HEAD, []).value
    assert writer.write(entries) == Ok(None)
    assert store.appended == entries


def test_a_store_failure_maps_to_audit_write_failed_naming_the_first_tool_call() -> None:
    writer = AuditWriter(_MemoryAudit(fail=True), SimIdGen())
    entries = writer.entries_for(SESSION, NOW, HEAD, []).value
    result = writer.write(entries)
    assert isinstance(result, Failure) and result.code == "AUDIT_WRITE_FAILED"
    assert result.message == "Audit write failed for tool call tc-0000000000000001."
