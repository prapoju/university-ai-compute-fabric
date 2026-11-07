"""``get_audit_page`` (contracts.md section 2, D50, E14, E47): a session's audit rows, paged.

Checks the pagination first, then that the session exists, then reads the page. It writes
nothing, reads no clock and is not itself audited (Q3). The page depth is bounded by the
retention cap: ``(page - 1) * page_size < cap``, so no request can ask for rows that cannot exist.
"""

from __future__ import annotations

from src.domain.error_catalog import fail
from src.domain.result import Ok, Result, is_failure
from src.dto import GetAuditPageResponse
from src.ports.inbound import AuditUseCases
from src.ports.outbound import AuditStorePort, SessionStorePort

MAX_PAGE_SIZE = 100


class AuditService(AuditUseCases):
    def __init__(
        self, *, sessions: SessionStorePort, audit: AuditStorePort, retention_cap: int
    ) -> None:
        self._sessions = sessions
        self._audit = audit
        self._cap = retention_cap

    def get_audit_page(
        self, session_id: str, page: int, page_size: int
    ) -> Result[GetAuditPageResponse]:
        if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE or (page - 1) * page_size >= self._cap:
            observed = (
                f"page={page}, page_size={page_size}; page>=1, 1<=page_size<=100 and"
                f" (page-1)*page_size < {self._cap} (retention cap)",
            )
            return fail("PAGINATION_INVALID", observed=observed, v=page_size)
        found = self._sessions.get(session_id)
        if is_failure(found):
            return found
        if found.value is None:
            return fail("SESSION_NOT_FOUND", sid=session_id)
        read = self._audit.page(session_id, (page - 1) * page_size, page_size)
        if is_failure(read):
            return read
        entries, total = read.value
        return Ok(
            GetAuditPageResponse(
                entries=entries,
                page=page,
                page_size=page_size,
                total=total,
                has_more=page * page_size < total,
            )
        )
