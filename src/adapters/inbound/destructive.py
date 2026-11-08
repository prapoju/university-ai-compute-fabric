"""Destructive routes (driving adapter): ``POST /api/v1/destructive/dry-runs`` (story 2.2).

Thin by design: validate the transport shape, call the use case through the inbound port and turn
the typed ``Result`` into HTTP. The action and the session id stay plain strings here so that an
unknown action is the contract's ``VALIDATION_MALFORMED_BODY`` and an unknown session its 404, both
decided by the application ring. No domain logic lives here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from src.adapters.inbound.errors import error_body, failure_response
from src.domain.result import is_failure
from src.ports.inbound import CanonicalOutcome, DestructiveUseCases

router = APIRouter(prefix="/api/v1", tags=["destructive"])


class PostDryRunBody(BaseModel):
    """``PostDryRunRequest`` with plain strings; the application validates them (see module)."""

    model_config = ConfigDict(extra="forbid")

    query_text: str
    action: str
    target_refs: list[str]
    session_id: str


def get_destructive_use_cases(request: Request) -> DestructiveUseCases:
    return request.app.state.container.port(DestructiveUseCases)


Destructive = Annotated[DestructiveUseCases, Depends(get_destructive_use_cases)]


def canonical_response(outcome: CanonicalOutcome) -> JSONResponse:
    """A canonical outcome (D58): HTTP 200 whose body is an ``ErrorBody`` with the literal."""
    envelope = error_body(outcome.code, 200, outcome.message, retryable=False)
    return JSONResponse(status_code=200, content=envelope)


@router.post("/destructive/dry-runs", response_model=None)
def post_dry_run(body: PostDryRunBody, use_cases: Destructive) -> JSONResponse:
    result = use_cases.post_dry_run(body.query_text, body.action, body.target_refs, body.session_id)
    if is_failure(result):
        return failure_response(result)
    if isinstance(result.value, CanonicalOutcome):
        return canonical_response(result.value)
    return JSONResponse(status_code=200, content=result.value.proposal.model_dump(mode="json"))
