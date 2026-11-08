"""Runbook route (driving adapter): ``GET /api/v1/runbooks/{error_code}`` as in openapi.yaml.

Thin, like ``state.py``: the use case owns the id check and the lookup. Read-only (AD-1); sync
``def`` route (D-2.6).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from src.adapters.inbound.errors import failure_response
from src.domain.result import is_failure
from src.ports.inbound import RunbookUseCases

router = APIRouter(prefix="/api/v1", tags=["runbooks"])


def get_runbook_use_cases(request: Request) -> RunbookUseCases:
    """The use case registered in the composition root (overridable in tests)."""
    return request.app.state.container.port(RunbookUseCases)


UseCases = Annotated[RunbookUseCases, Depends(get_runbook_use_cases)]


@router.get("/runbooks/{error_code}", response_model=None)
def get_runbook(error_code: str, use_cases: UseCases) -> JSONResponse:
    result = use_cases.get_runbook(error_code)
    if is_failure(result):
        return failure_response(result)
    return JSONResponse(status_code=200, content=result.value.model_dump(mode="json"))
