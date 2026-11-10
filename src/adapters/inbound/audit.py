"""Audit route (driving adapter): ``GET /api/v1/sessions/{sid}/audit`` as declared in openapi.yaml.

Thin by design, like ``evidence.py``. ``page`` and ``page_size`` are plain integers so the use
case, not the framework, answers ``PAGINATION_INVALID`` with the contract message. Read-only: no
route edits or deletes an audit row (AD-10, AD-13). A sync ``def`` route, never ``async def``
(review D-2.6): the store call blocks, so it must run in the thread pool.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from src.adapters.inbound.errors import failure_response
from src.adapters.inbound.sessions import SessionIdPath
from src.domain.result import is_failure
from src.ports.inbound import AuditUseCases

router = APIRouter(prefix="/api/v1", tags=["audit"])


def get_audit_use_cases(request: Request) -> AuditUseCases:
    """The use cases registered in the composition root (overridable in tests)."""
    return request.app.state.container.port(AuditUseCases)


UseCases = Annotated[AuditUseCases, Depends(get_audit_use_cases)]


@router.get("/sessions/{sid}/audit", response_model=None)
def get_audit_page(
    sid: SessionIdPath, use_cases: UseCases, page: int = 1, page_size: int = 20
) -> JSONResponse:
    result = use_cases.get_audit_page(sid, page, page_size)
    if is_failure(result):
        return failure_response(result)
    return JSONResponse(status_code=200, content=result.value.model_dump(mode="json"))
