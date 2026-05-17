from __future__ import annotations

import traceback

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse

from bigrag.exceptions import (
    ForbiddenError,
    NotFoundError,
    ServerError,
    UpstreamError,
    ValidationError,
)
from bigrag.logging import get_logger


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError) -> ORJSONResponse:
        return ORJSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_handler(_request: Request, exc: ValidationError) -> ORJSONResponse:
        return ORJSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(_request: Request, exc: ForbiddenError) -> ORJSONResponse:
        return ORJSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(UpstreamError)
    async def upstream_handler(request: Request, exc: UpstreamError) -> ORJSONResponse:
        get_logger("bigrag.upstream").warning(
            "upstream error",
            method=request.method,
            path=request.url.path,
            exc_type=type(exc).__name__,
            exc=str(exc),
        )
        return ORJSONResponse(
            status_code=502,
            content={"detail": exc.public_message, "code": exc.code},
        )

    @app.exception_handler(ServerError)
    async def server_handler(request: Request, exc: ServerError) -> ORJSONResponse:
        get_logger("bigrag.server_error").error(
            "server error",
            method=request.method,
            path=request.url.path,
            exc_type=type(exc).__name__,
            exc=str(exc),
        )
        return ORJSONResponse(
            status_code=500,
            content={"detail": exc.public_message, "code": exc.code},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> ORJSONResponse:
        logger = get_logger("bigrag.unhandled")
        logger.error(
            "unhandled exception",
            method=request.method,
            path=request.url.path,
            exc_type=type(exc).__name__,
            exc=str(exc),
            traceback=traceback.format_exc(),
        )
        return ORJSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "code": "internal_error"},
        )
