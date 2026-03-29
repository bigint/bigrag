from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from bigrag.config import settings
from bigrag.services import auth as auth_service


async def get_current_user(request: Request) -> dict:
    """Extract and validate auth from the request. Supports session tokens, API keys, master key."""
    auth_header = request.headers.get("authorization", "")

    if not auth_header.startswith("Bearer "):
        # Check if auth is disabled (no database, no keys, no master key)
        if not settings.master_key and not settings.api_keys:
            return {"id": None, "role": "admin", "email": "anonymous", "display_name": "Anonymous"}
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = auth_header[7:]

    # Master key check
    if settings.master_key and token == settings.master_key:
        return {"id": None, "role": "admin", "email": "master", "display_name": "Master Key"}

    # Static API key check
    if token in settings.api_keys:
        return {"id": None, "role": "admin", "email": "api-key", "display_name": "API Key"}

    # Session token check
    user = await auth_service.validate_session(token)
    if user:
        return user

    # Database API key check
    api_key = await auth_service.validate_api_key(token)
    if api_key:
        return {
            "id": api_key.get("user_id"),
            "role": api_key.get("user_role", "member"),
            "email": "api-key",
            "display_name": api_key["name"],
            "permissions": api_key.get("permissions", {}),
        }

    raise HTTPException(status_code=401, detail="Invalid or expired token")


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def optional_auth(request: Request) -> dict | None:
    """Returns user if authenticated, None otherwise. For endpoints that work with or without auth."""
    try:
        return await get_current_user(request)
    except HTTPException:
        return None
