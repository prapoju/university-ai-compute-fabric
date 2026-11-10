"""Annex 12.1 inbound: ``POST /api/v1/copilot/query`` with ``{ "query": "..." }``.

A thin entry point over the same session use cases: it opens a session for the operator and
submits the query in it, so the answer, its evidence and its claims are stored and can be read
back through ``GET /api/v1/sessions/{sid}``. No domain logic lives here.
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from src.adapters.inbound.destructive import canonical_response
from src.adapters.inbound.errors import failure_response
from src.adapters.inbound.sessions import UseCases, query_response
from src.domain.result import is_failure
from src.dto import ChatRefusalResponse, ErrorBody
from src.ports.inbound import CanonicalOutcome, ChatRefusal, ChatUseCases, SessionUseCases

router = APIRouter(prefix="/api/v1", tags=["copilot"])

DEFAULT_OPERATOR_ROLE = "role-operations"  # Nadia, the helpdesk operator of the annex


class CopilotQueryBody(BaseModel):
    """``{ "query": "..." }``; length is validated by the domain (400 with its own code)."""

    model_config = ConfigDict(extra="forbid")

    query: str


class CopilotChatBody(BaseModel):
    """``{ "query": "..." }``, the same shape as ``/copilot/query`` (story 2.1, D1)."""

    model_config = ConfigDict(extra="forbid")

    query: str


def _answer(use_cases: SessionUseCases, query: str) -> JSONResponse:
    created = use_cases.create_session(DEFAULT_OPERATOR_ROLE)
    if is_failure(created):
        return failure_response(created)
    return query_response(use_cases.submit_query(created.value.session_id, query))


@router.post("/copilot/query", response_model=None)
def copilot_query(body: CopilotQueryBody, use_cases: UseCases) -> JSONResponse:
    return _answer(use_cases, body.query)


def get_chat_use_cases(request: Request) -> ChatUseCases:
    return request.app.state.container.port(ChatUseCases)


Chat = Annotated[ChatUseCases, Depends(get_chat_use_cases)]


def _refusal_body(reply: ChatRefusal) -> dict:
    """The ``ChatRefusalResponse`` wire shape: the refusal first, then the dry-run (D1)."""
    refusal = canonical_response(reply.refusal)
    dry_run = reply.dry_run
    body = ChatRefusalResponse(
        refusal=ErrorBody.model_validate(json.loads(refusal.body)),
        impact_summary=dry_run.impact_summary,
        proposal=dry_run.proposal,
        token_expires_at=dry_run.token_expires_at,
        confirmation_enabled=dry_run.confirmation_enabled,
    )
    return body.model_dump(mode="json", exclude_none=False)


@router.post("/copilot/chat", response_model=None)
def copilot_chat(body: CopilotChatBody, chat: Chat) -> JSONResponse:
    """Annex 12.4 inbound: the refusal, and for a refused destructive request its dry-run (D1)."""
    result = chat.chat(DEFAULT_OPERATOR_ROLE, body.query)
    if is_failure(result):
        return failure_response(result)
    if isinstance(result.value, ChatRefusal):
        return JSONResponse(status_code=200, content=_refusal_body(result.value))
    if isinstance(result.value, CanonicalOutcome):
        return canonical_response(result.value)
    return JSONResponse(status_code=200, content=result.value.model_dump(mode="json"))
