"""Structured JSON error envelope (``ErrorBody``, contracts.md §4) and global handlers.

No unhandled exception ever reaches the client as a stack trace: validation problems are
the contract's 400, and anything unexpected degrades to the safe-failure literal (AD-12).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.dto import ErrorBody, ExplanationDTO

S_PUA = "Provider unavailable — cannot answer."


def error_body(
    code: str,
    status: int,
    message: str,
    *,
    retryable: bool,
    observed: list[str] | None = None,
) -> dict[str, Any]:
    """Build a contract ``ErrorBody``; a code outside the section 4 catalog fails validation."""
    body = ErrorBody(
        code=code,  # type: ignore[arg-type]
        status=status,
        message=message,
        retryable=retryable,
        explanation=ExplanationDTO(observed_values=observed or []),
    )
    return body.model_dump()


def error_response(body: dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=body["status"], content=body)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        observed = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        message = "Request does not match the declared schema."
        body = error_body(
            "VALIDATION_MALFORMED_BODY", 400, message, retryable=False, observed=observed
        )
        return error_response(body)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, __: Exception) -> JSONResponse:
        return error_response(error_body("PROVIDER_UNAVAILABLE", 503, S_PUA, retryable=True))
