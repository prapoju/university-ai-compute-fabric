"""Annex 12.1 inbound: ``POST /api/v1/copilot/query`` with ``{ "query": "..." }``.

A thin entry point over the same session use cases: it opens a session for the operator and
submits the query in it, so the answer, its evidence and its claims are stored and can be read
back through ``GET /api/v1/sessions/{sid}``. No domain logic lives here.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from src.adapters.inbound.errors import failure_response
from src.adapters.inbound.sessions import UseCases, query_response
from src.domain.result import is_failure

router = APIRouter(prefix="/api/v1", tags=["copilot"])

DEFAULT_OPERATOR_ROLE = "role-operations"  # Nadia, the helpdesk operator of the annex


class CopilotQueryBody(BaseModel):
    """``{ "query": "..." }``; length is validated by the domain (400 with its own code)."""

    model_config = ConfigDict(extra="forbid")

    query: str


@router.post("/copilot/query", response_model=None)
def copilot_query(body: CopilotQueryBody, use_cases: UseCases) -> JSONResponse:
    created = use_cases.create_session(DEFAULT_OPERATOR_ROLE)
    if is_failure(created):
        return failure_response(created)
    return query_response(use_cases.submit_query(created.value.session_id, body.query))
