"""Executor routes (driving adapter): ``/executor/v1/proposals`` (story 2.4, AD-15).

A thin facade over the executor port, the replacement point of the contract: ``POST`` hands a frozen
``ExecutorRequest`` to it and ``GET`` reads what it recorded. The simulated executor itself decides
whether a proposal may be applied (it accepts only a ``dispatched`` one with its token), so these
routes cannot be used to bypass the confirmation. No domain logic lives here.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.adapters.inbound.errors import failure_response
from src.domain.error_catalog import fail
from src.domain.result import is_failure
from src.dto import ExecutorRequestDTO
from src.ports.outbound import ExecutorPort

router = APIRouter(prefix="/executor/v1", tags=["executor"])


def get_executor(request: Request) -> ExecutorPort:
    return request.app.state.container.port(ExecutorPort)


Executor = Annotated[ExecutorPort, Depends(get_executor)]


@router.post("/proposals", response_model=None)
def executor_post_proposal(
    executor: Executor, body: Annotated[dict[str, Any], Body()]
) -> JSONResponse:
    try:
        request = ExecutorRequestDTO.model_validate(body)  # the frozen field set, E16
    except ValidationError:
        return failure_response(fail("VALIDATION_MALFORMED_BODY", schema_id="ExecutorRequest"))
    result = executor.dispatch(request)
    if is_failure(result):
        return failure_response(result)
    return JSONResponse(status_code=200, content=result.value.model_dump(mode="json"))


@router.get("/proposals/{pid}", response_model=None)
def executor_get_proposal(pid: str, executor: Executor) -> JSONResponse:
    result = executor.get(pid)
    if is_failure(result):
        return failure_response(result)
    if result.value is None:
        return failure_response(fail("PROPOSAL_NOT_FOUND", pid=pid))
    return JSONResponse(status_code=200, content=result.value.model_dump(mode="json"))
