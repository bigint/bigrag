from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class SessionCsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = request.app.state.settings
        if request.method not in MUTATING_METHODS:
            return await call_next(request)
        if settings.session_cookie_name not in request.cookies:
            return await call_next(request)
        origin = request.headers.get("origin")
        if not origin:
            return JSONResponse(
                {"detail": "Missing Origin header on session-authenticated mutating request"},
                status_code=403,
            )
        if _allowed_origin(origin, request, settings.cors_origins):
            return await call_next(request)
        return JSONResponse({"detail": "Cross-origin request rejected"}, status_code=403)


def _allowed_origin(origin: str, request: Request, cors_origins: list[str]) -> bool:
    if origin in cors_origins:
        return True
    parsed = urlparse(origin)
    if not parsed.scheme or not parsed.netloc:
        return False
    return parsed.scheme == request.url.scheme and parsed.netloc == request.headers.get("host")
