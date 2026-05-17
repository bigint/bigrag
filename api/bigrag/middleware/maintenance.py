from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from bigrag.services.maintenance import active_lock

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
SAFE_PATH_PREFIXES = ("/v1/admin/backups",)


class MaintenanceWriteLockMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method.upper() not in SAFE_METHODS:
            if not request.url.path.startswith(SAFE_PATH_PREFIXES):
                lock = await active_lock()
                if lock is not None:
                    return JSONResponse(
                        status_code=423,
                        content={"detail": f"Instance maintenance active: {lock.reason}"},
                    )
        return await call_next(request)
