"""Evidence routes (driving adapter): the answer's evidence set and one citation's source.

Thin by design, like ``sessions.py``: call the evidence use cases through the inbound port and
turn the typed ``Result`` into HTTP. Both routes are read-only. ``cid`` is a plain string: the
use case decides that a malformed id is ``ENTITY_NOT_FOUND`` (story 1.4 D6), because openapi
declares only 404/503 here and a framework pattern would answer an undeclared 400. A ``cid``
contains ``#``, so clients send it percent-encoded (``user%23alex``). The ``path`` converter keeps
an id with an encoded ``/`` on this route, so it too is ``S_ENF`` and never the framework 404.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from src.adapters.inbound.errors import failure_response
from src.domain.result import is_failure
from src.ports.inbound import EvidenceUseCases

router = APIRouter(prefix="/api/v1", tags=["evidence"])


def get_evidence_use_cases(request: Request) -> EvidenceUseCases:
    """The use cases registered in the composition root (overridable in tests)."""
    return request.app.state.container.port(EvidenceUseCases)


UseCases = Annotated[EvidenceUseCases, Depends(get_evidence_use_cases)]


@router.get("/answers/{aid}/evidence", response_model=None)
def get_answer_evidence(aid: str, use_cases: UseCases) -> JSONResponse:
    result = use_cases.get_answer_evidence(aid)
    if is_failure(result):
        return failure_response(result)
    return JSONResponse(status_code=200, content=result.value.model_dump(mode="json"))


@router.get("/citations/{cid:path}", response_model=None)
def get_citation(cid: str, use_cases: UseCases) -> JSONResponse:
    result = use_cases.get_citation(cid)
    if is_failure(result):
        return failure_response(result)
    return JSONResponse(status_code=200, content=result.value.model_dump(mode="json"))
