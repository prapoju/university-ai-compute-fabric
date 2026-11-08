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
from pydantic import BaseModel, ConfigDict, Field

from src.adapters.inbound.errors import error_body, failure_response
from src.domain.result import is_failure
from src.ports.inbound import CanonicalOutcome, ConfirmUseCases, DestructiveUseCases

router = APIRouter(prefix="/api/v1", tags=["destructive"])


class PostDryRunBody(BaseModel):
    """``PostDryRunRequest`` with plain strings; the application validates them (see module)."""

    model_config = ConfigDict(extra="forbid")

    query_text: str
    action: str
    target_refs: list[str]
    session_id: str


class PostConfirmBody(BaseModel):
    """``PostConfirmRequest``: exactly ``{proposal_id, gate_token}`` and nothing about who confirms.

    Any other field (a role, a user, a session) is rejected as malformed (AD-5). ``proposal_id`` is
    a plain string, so an unknown or malformed id is ``PROPOSAL_NOT_FOUND``; the token must match
    the ``GateToken`` pattern.
    """

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    gate_token: str = Field(pattern=r"^gt-[0-9a-f]{32}$")


def get_destructive_use_cases(request: Request) -> DestructiveUseCases:
    return request.app.state.container.port(DestructiveUseCases)


Destructive = Annotated[DestructiveUseCases, Depends(get_destructive_use_cases)]


def get_confirm_use_cases(request: Request) -> ConfirmUseCases:
    return request.app.state.container.port(ConfirmUseCases)


Confirm = Annotated[ConfirmUseCases, Depends(get_confirm_use_cases)]


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


@router.post("/destructive/proposals", response_model=None)
def post_confirm(body: PostConfirmBody, use_cases: Confirm) -> JSONResponse:
    """The distinct confirmation request: ``{proposal_id, gate_token}`` and nothing else (AD-5)."""
    result = use_cases.post_confirm(body.proposal_id, body.gate_token)
    if is_failure(result):
        return failure_response(result)
    proposal = result.value
    # a result the executor reported but that did not complete the scope: HTTP 502
    # EXECUTOR_PARTIAL_APPLY whose body is the Proposal itself (contracts A16, story 2.4 D5)
    partial = proposal.state == "failed" and proposal.executor_result is not None
    return JSONResponse(
        status_code=502 if partial else 200, content=proposal.model_dump(mode="json")
    )
