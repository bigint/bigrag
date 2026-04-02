from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request

from bigrag.config import settings
from bigrag.services import auth as auth_service

logger = logging.getLogger("bigrag.auth")


async def get_current_user(request: Request) -> dict:
    """Extract and validate auth from the request. Supports session tokens, API keys, master key."""
    auth_header = request.headers.get("authorization", "")
    path = request.url.path

    # EventSource can't send headers — accept token as query param
    if not auth_header.startswith("Bearer "):
        query_token = request.query_params.get("token")
        if query_token:
            auth_header = f"Bearer {query_token}"

    if not auth_header.startswith("Bearer "):
        if not settings.master_key and not settings.api_keys:
            if await auth_service.needs_setup():
                logger.info(f"auth: anonymous access (no setup) path={path}")
                return {"id": None, "role": "admin", "email": "anonymous", "display_name": "Anonymous"}
        logger.warning(f"auth: missing authorization header path={path}")
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = auth_header[7:]

    # Master key check
    if settings.master_key and token == settings.master_key:
        logger.info(f"auth: master key path={path}")
        return {"id": None, "role": "admin", "email": "master", "display_name": "Master Key"}

    # Static API key check
    if token in settings.api_keys:
        logger.info(f"auth: static api key path={path}")
        return {"id": None, "role": "admin", "email": "api-key", "display_name": "API Key"}

    # Session token check
    user = await auth_service.validate_session(token)
    if user:
        logger.info(f"auth: session user={user.get('email')} role={user.get('role')} path={path}")
        return user

    # Database API key check
    api_key = await auth_service.validate_api_key(token)
    if api_key:
        logger.info(f"auth: db api key name={api_key['name']} path={path}")
        return {
            "id": api_key.get("user_id"),
            "role": api_key.get("user_role", "member"),
            "email": "api-key",
            "display_name": api_key["name"],
            "permissions": api_key.get("permissions", {}),
        }

    logger.warning(f"auth: invalid/expired token path={path}")
    raise HTTPException(status_code=401, detail="Invalid or expired token")


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        logger.warning(f"auth: admin required but role={user.get('role')} user={user.get('email')}")
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
