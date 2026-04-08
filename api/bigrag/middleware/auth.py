from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, Request

from bigrag.config import settings
from bigrag.logging import get_logger

logger = get_logger("bigrag.auth")


async def get_current_user(request: Request) -> dict:
    if not settings.api_secret:
        return {"id": None, "role": "admin", "email": "anonymous", "display_name": "Anonymous"}

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        query_token = request.query_params.get("token")
        if query_token:
            auth_header = f"Bearer {query_token}"

    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = auth_header[7:]
    if not hmac.compare_digest(token, settings.api_secret):
        raise HTTPException(status_code=401, detail="Invalid API secret")

    return {"id": None, "role": "admin", "email": "api", "display_name": "API"}


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
