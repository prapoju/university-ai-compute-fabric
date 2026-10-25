"""FastAPI entrypoint (driving adapter). Task 1 exposes only the ops probes.

Run:  uvicorn src.adapters.inbound.app:create_app --factory
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src import dependency_check
from src.adapters.inbound.errors import S_PUA, error_body, error_response, install_error_handlers
from src.bootstrap import Container, build_container
from src.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    dependency_check.require()  # fatal runtime problems abort startup with a readable message
    container = build_container(settings or Settings.from_env())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        container.close()

    # The generated /docs, /redoc and /openapi.json are not in the contract, so they are off:
    # the app serves exactly the routes declared in openapi.yaml (AD-13, zero extra endpoints).
    app = FastAPI(
        title="Module 12 - AI Operations Copilot",
        version="2.2.0",  # the contract version (openapi.yaml info.version)
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.container = container
    install_error_handlers(app)

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        """Liveness: the process is up. Touches no dependency."""
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"], response_model=None)
    def readyz() -> dict[str, Any] | JSONResponse:
        """Readiness: every registered check passes."""
        return _readiness(container)

    return app


def _readiness(container: Container) -> dict[str, Any] | JSONResponse:
    results = {name: check() for name, check in container.readiness.items()}
    failed = {name: problem for name, problem in results.items() if problem}
    if failed:
        observed = [f"{name}: {problem}" for name, problem in failed.items()]
        return error_response(
            error_body("PROVIDER_UNAVAILABLE", 503, S_PUA, retryable=True, observed=observed)
        )
    return {"status": "ready", "checks": {name: "ok" for name in results}}
