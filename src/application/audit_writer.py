"""Turns a turn's recorded tool calls into audit rows and writes them (AD-10, FR-11, I14, I15).

``entries_for`` mints every id before the turn's transaction opens, in call order with the
``toolcall.answer_query`` head first (story 1.5 D1, review D-2.3), and redacts both summaries at
write time (NFR-11). Tool metadata goes in ``result_summary``, because the wire ``AuditRecord`` has
no tool-name field (D5). The query text is never stored.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.application.tool_audit import RecordedCall
from src.domain.error_catalog import fail
from src.domain.redaction import redact
from src.domain.result import Ok, Result, is_failure
from src.dto import AuditRecordDTO, ClockReadDTO, SessionDTO, ToolCallDTO
from src.ports.outbound import AuditEntry, AuditStorePort, IdGenPort


def _summary(call: RecordedCall) -> dict[str, object]:
    summary: dict[str, object] = {"tool_name": call.tool_name, "status": call.status}
    if call.error_code is not None:
        summary["error_code"] = call.error_code
    if call.result_count is not None:
        summary["result_count"] = call.result_count
    summary.update(call.result)
    return summary


class AuditWriter:
    def __init__(self, store: AuditStorePort, idgen: IdGenPort) -> None:
        self._store = store
        self._idgen = idgen

    def entries_for(
        self,
        session: SessionDTO,
        now: ClockReadDTO,
        head: RecordedCall,
        calls: Sequence[RecordedCall],
    ) -> Result[list[AuditEntry]]:
        entries: list[AuditEntry] = []
        for call in (head, *calls):
            tool_call_id = self._idgen.new_id("tool_call")
            if is_failure(tool_call_id):
                return tool_call_id
            audit_id = self._idgen.new_id("audit")
            if is_failure(audit_id):
                return audit_id
            entries.append(
                AuditEntry(
                    tool_call=ToolCallDTO(
                        tool_call_id=tool_call_id.value,
                        session_id=session.session_id,
                        tool_name=call.tool_name,
                        params_summary=redact(dict(call.params)),
                        timestamp=now.instant,
                        status=call.status,
                    ),
                    record=AuditRecordDTO(
                        audit_id=audit_id.value,
                        tool_call_id=tool_call_id.value,
                        session_id=session.session_id,
                        operator_role=session.operator_role,
                        timestamp=now.instant,
                        result_summary=redact(_summary(call)),
                        actor="copilot",
                    ),
                )
            )
        return Ok(entries)

    def write(self, entries: Sequence[AuditEntry]) -> Result[None]:
        written = self._store.append(entries)
        if is_failure(written):
            first = entries[0].record.tool_call_id if entries else None
            return fail("AUDIT_WRITE_FAILED", tool_call_id=first or "unknown")
        return written
