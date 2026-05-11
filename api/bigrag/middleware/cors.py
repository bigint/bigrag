from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from bigrag.services import runtime_settings


class RuntimeCorsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        if not origin:
            return await call_next(request)

        allowed = await _allowed_origin(origin, request)
        if request.method == "OPTIONS" and request.headers.get("access-control-request-method"):
            if not allowed:
                return Response(status_code=400)
            response = Response(status_code=204)
        else:
            response = await call_next(request)
            if not allowed:
                return response

        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "DELETE,GET,HEAD,OPTIONS,PATCH,POST,PUT"
        response.headers["Access-Control-Allow-Headers"] = request.headers.get(
            "access-control-request-headers",
            "authorization,content-type,idempotency-key",
        )
        response.headers["Access-Control-Max-Age"] = "600"
        response.headers.add_vary_header("Origin")
        return response


async def _allowed_origin(origin: str, request: Request) -> bool:
    try:
        cors_origins = await runtime_settings.get_value("cors_origins")
    except Exception:
        cors_origins = request.app.state.settings.cors_origins
    if origin in cors_origins or "*" in cors_origins:
        return True
    parsed = urlparse(origin)
    if not parsed.scheme or not parsed.netloc:
        return False
    return parsed.scheme == request.url.scheme and parsed.netloc == request.headers.get("host")
