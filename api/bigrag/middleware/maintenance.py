from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from bigrag.services.maintenance import active_lock_state

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class MaintenanceWriteLockMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method.upper() not in SAFE_METHODS:
            lock = await active_lock_state()
            if lock is not None:
                return JSONResponse(
                    status_code=423,
                    content={"detail": f"Instance maintenance active: {lock['reason']}"},
                )
        return await call_next(request)
