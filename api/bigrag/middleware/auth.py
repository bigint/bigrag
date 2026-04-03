from __future__ import annotations

import logging
import time

from fastapi import Depends, HTTPException, Request

from bigrag.config import settings
from bigrag.services import auth as auth_service

logger = logging.getLogger("bigrag.auth")

_AUTH_CACHE_TTL = 60
_session_cache: dict[str, tuple[dict, float]] = {}
_api_key_cache: dict[str, tuple[dict | None, float]] = {}


def _cache_get(cache: dict, key: str) -> dict | None:
    entry = cache.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.monotonic() > expires_at:
        cache.pop(key, None)
        return None
    return value


def _cache_set(cache: dict, key: str, value) -> None:
    cache[key] = (value, time.monotonic() + _AUTH_CACHE_TTL)


def invalidate_auth_cache(token_hash: str | None = None) -> None:
    if token_hash:
        _session_cache.pop(token_hash, None)
        _api_key_cache.pop(token_hash, None)
    else:
        _session_cache.clear()
        _api_key_cache.clear()


async def get_current_user(request: Request) -> dict:
    if not settings.auth_required:
        return {"id": None, "role": "admin", "email": "anonymous", "display_name": "Anonymous"}

    auth_header = request.headers.get("authorization", "")
    path = request.url.path

    if not auth_header.startswith("Bearer "):
        query_token = request.query_params.get("token")
        if query_token:
            auth_header = f"Bearer {query_token}"

    if not auth_header.startswith("Bearer "):
        if await auth_service.needs_setup():
            return {"id": None, "role": "admin", "email": "anonymous", "display_name": "Anonymous"}
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = auth_header[7:]
    token_hash = auth_service.hash_token(token)
    cached_user = _cache_get(_session_cache, token_hash)
    if cached_user:
        return cached_user

    user = await auth_service.validate_session(token)
    if user:
        _cache_set(_session_cache, token_hash, user)
        return user

    cached_key = _cache_get(_api_key_cache, token_hash)
    if cached_key:
        return cached_key

    api_key = await auth_service.validate_api_key(token)
    if api_key:
        result = {
            "id": api_key.get("user_id"),
            "role": api_key.get("user_role", "member"),
            "email": "api-key",
            "display_name": api_key["name"],
            "permissions": api_key.get("permissions", {}),
        }
        _cache_set(_api_key_cache, token_hash, result)
        return result

    logger.warning(f"auth: invalid/expired token path={path}")
    raise HTTPException(status_code=401, detail="Invalid or expired token")


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
