from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from bigrag.services.maintenance import active_lock

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CONTROL_PATH_PREFIXES = ("/v1/admin/backups", "/v1/admin/vector-storage/migrations")


def _is_control_path(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in CONTROL_PATH_PREFIXES)


class MaintenanceWriteLockMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method.upper() not in SAFE_METHODS:
            if not _is_control_path(request.url.path):
                lock = await active_lock()
                if lock is not None:
                    return JSONResponse(
                        status_code=423,
                        content={"detail": f"Instance maintenance active: {lock.reason}"},
                    )
        return await call_next(request)
