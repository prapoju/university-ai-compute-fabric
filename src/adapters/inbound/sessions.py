"""Session routes (driving adapter): ``/api/v1/sessions*`` exactly as declared in openapi.yaml.

Thin by design: validate the transport shape, call the session use cases through the inbound
port, and turn the typed ``Result`` into HTTP. No domain logic lives here. Canonical outcomes
(clarifications) are HTTP 200 with an ``ErrorBody`` (D58); every failure is the ``ErrorBody``
envelope, and 5xx bodies never carry internal detail.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from src.adapters.inbound.errors import error_body, failure_response
from src.domain.result import is_failure
from src.dto import CreateSessionRequest
from src.ports.inbound import CanonicalOutcome, SessionUseCases

router = APIRouter(prefix="/api/v1", tags=["sessions"])

# openapi.yaml components.schemas.SessionId
SessionIdPath = Annotated[str, Path(pattern=r"^sess-[0-9a-f]{16}$")]


class SubmitQueryBody(BaseModel):
    """``SubmitQueryRequest`` with a plain ``str``.

    The contract's ``QueryText`` would turn an empty or over-long query into a generic schema
    error, but contracts.md section 2 requires ``VALIDATION_EMPTY_QUERY`` /
    ``VALIDATION_QUERY_TOO_LONG`` with their own messages, so the domain validates the length.
    A body carrying ``session_id`` (or anything else) is rejected as malformed (A26, E48).
    """

    model_config = ConfigDict(extra="forbid")

    query_text: str


def get_session_use_cases(request: Request) -> SessionUseCases:
    """The use cases registered in the composition root (overridable in tests)."""
    return request.app.state.container.port(SessionUseCases)


UseCases = Annotated[SessionUseCases, Depends(get_session_use_cases)]


@router.post("/sessions", status_code=201, response_model=None)
def create_session(body: CreateSessionRequest, use_cases: UseCases) -> JSONResponse:
    result = use_cases.create_session(body.operator_role)
    if is_failure(result):
        return failure_response(result)
    return JSONResponse(status_code=201, content=result.value.model_dump(mode="json"))


@router.post("/sessions/{sid}/queries", response_model=None)
def submit_query(sid: SessionIdPath, body: SubmitQueryBody, use_cases: UseCases) -> JSONResponse:
    result = use_cases.submit_query(sid, body.query_text)
    if is_failure(result):
        return failure_response(result)
    outcome = result.value
    if isinstance(outcome, CanonicalOutcome):
        envelope = error_body(outcome.code, 200, outcome.message, retryable=False)
        return JSONResponse(status_code=200, content=envelope)
    return JSONResponse(status_code=200, content=outcome.model_dump(mode="json"))


@router.get("/sessions/{sid}", response_model=None)
def get_session(sid: SessionIdPath, use_cases: UseCases) -> JSONResponse:
    result = use_cases.get_session(sid)
    if is_failure(result):
        return failure_response(result)
    return JSONResponse(status_code=200, content=result.value.model_dump(mode="json"))


@router.delete("/sessions/{sid}", status_code=204, response_model=None)
def reset_session(sid: SessionIdPath, use_cases: UseCases) -> Response:
    result = use_cases.reset_session(sid)
    if is_failure(result):
        return failure_response(result)
    return Response(status_code=204)
