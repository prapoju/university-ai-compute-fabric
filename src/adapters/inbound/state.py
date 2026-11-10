"""State inspection routes (driving adapter): ``/api/v1/state/*`` as declared in openapi.yaml.

Thin by design, like ``evidence.py``. ``entity_type`` and the paging values are plain types so
the use case answers ``VALIDATION_BAD_ENTITY_TYPE`` / ``PAGINATION_INVALID`` with the contract
messages. The ``path`` converter keeps an id with an encoded ``/`` on this route, so it reaches
the id check and is a 400, never the framework 404. Read-only (AD-1); sync ``def`` routes (D-2.6).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from src.adapters.inbound.errors import failure_response
from src.domain.result import is_failure
from src.ports.inbound import StateUseCases

router = APIRouter(prefix="/api/v1", tags=["state"])


def get_state_use_cases(request: Request) -> StateUseCases:
    """The use cases registered in the composition root (overridable in tests)."""
    return request.app.state.container.port(StateUseCases)


UseCases = Annotated[StateUseCases, Depends(get_state_use_cases)]


@router.get("/state/{entity_type}/{id:path}", response_model=None)
def get_state_record(entity_type: str, id: str, use_cases: UseCases) -> JSONResponse:
    result = use_cases.get_state_record(entity_type, id)
    if is_failure(result):
        return failure_response(result)
    return JSONResponse(status_code=200, content=result.value.model_dump(mode="json"))


@router.get("/state/{entity_type}", response_model=None)
def browse_state(
    entity_type: str, use_cases: UseCases, q: str = "", page: int = 1, page_size: int = 20
) -> JSONResponse:
    result = use_cases.browse_state(entity_type, q, page, page_size)
    if is_failure(result):
        return failure_response(result)
    return JSONResponse(status_code=200, content=result.value.model_dump(mode="json"))
