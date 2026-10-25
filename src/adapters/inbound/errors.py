"""Structured JSON error envelope (``ErrorBody``, contracts.md §4) and global handlers.

No unhandled exception ever reaches the client as a stack trace: validation problems are
the contract's 400, and anything unexpected degrades to the safe-failure literal (AD-12).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.domain.canonical_strings import S_PUA
from src.domain.error_catalog import render, spec_for
from src.domain.result import Failure
from src.dto import ErrorBody, ExplanationDTO

logger = logging.getLogger(__name__)


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


def failure_response(failure: Failure) -> JSONResponse:
    """Render a typed :class:`Failure` through the section 4 catalog (status, retry, message).

    Server-side failures (5xx) never expose their ``observed`` detail to the client; it goes to
    the log instead, so a driver error text cannot leak through the API.
    """
    spec = spec_for(failure.code)
    try:
        message = failure.message or render(failure.code)
    except ValueError:  # the template needs parameters this failure does not carry
        message = failure.code
    observed = list(failure.observed)
    if spec.status >= 500:
        logger.error("request failed: %s: %s", failure.code, "; ".join(observed))
        observed = []
    body = error_body(
        failure.code, spec.status, message, retryable=spec.retryable, observed=observed
    )
    return error_response(body)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        observed = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        message = "Request does not match the declared schema."
        body = error_body(
            "VALIDATION_MALFORMED_BODY", 400, message, retryable=False, observed=observed
        )
        return error_response(body)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # 404 / 405 from the router: same envelope as every other error, never {"detail": ...}
        if exc.status_code == 404:
            body = error_body("ENTITY_NOT_FOUND", 404, "Route not found.", retryable=False)
        else:
            message = str(exc.detail) or "Request not allowed."
            body = error_body(
                "VALIDATION_MALFORMED_BODY", exc.status_code, message, retryable=False
            )
        return error_response(body)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        # the client only sees the safe-failure literal; the cause stays in the server log
        logger.error("unhandled error", exc_info=exc)
        return error_response(error_body("PROVIDER_UNAVAILABLE", 503, S_PUA, retryable=True))
