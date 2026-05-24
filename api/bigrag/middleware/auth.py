from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag import config as _config
from bigrag.db.engine import session_factory
from bigrag.db.models import ApiKey, User, UserSession
from bigrag.logging import get_logger
from bigrag.middleware.auth_cache import (
    REDIS_AUTH_TIMEOUT_SECONDS,
    api_key_cache_key,
    auth_cache_delete,
    auth_cache_delete_pattern,
    auth_cache_get,
    auth_cache_set,
    session_cache_key,
)
from bigrag.services import redis_cache
from bigrag.services.auth import API_KEY_PREFIX, api_key_hashes_for_lookup, hash_session_token

logger = get_logger("bigrag.auth")


def _ttl_until(expires_at: datetime | None) -> int:
    ttl = _config.settings.auth_principal_cache_ttl
    if ttl <= 0:
        return 0
    if expires_at is None:
        return ttl
    seconds_left = int((expires_at - datetime.now(UTC)).total_seconds())
    return max(0, min(ttl, seconds_left))


def _user_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
    }


def _serialize(user: User, *, auth: str, api_key_id: str | None = None) -> dict:
    return {
        **_user_dict(user),
        "auth_method": auth,
        "api_key_id": api_key_id,
        "api_key_name": None,
        "scopes": None,
        "collection": None,
        "tenant_id": None,
        "active": True,
        "expires_at": None,
    }


def _is_api_key_principal(principal: dict) -> bool:
    return principal.get("auth_method") == "api_key"


def _principal_revoked(principal: dict) -> bool:
    if not _is_api_key_principal(principal):
        return False
    if principal.get("active") is False:
        return True
    expires_at = _parse_iso(principal.get("expires_at"))
    return expires_at is not None and expires_at <= datetime.now(UTC)


async def _user_from_session(request: Request, session: AsyncSession) -> dict | None:
    cookie = request.cookies.get(_config.settings.session_cookie_name)
    if not cookie:
        return None

    token_hash = hash_session_token(cookie)
    row = (
        await session.execute(
            select(User, UserSession.expires_at)
            .join(UserSession, UserSession.user_id == User.id)
            .where(UserSession.token_hash == token_hash)
            .where(UserSession.expires_at > datetime.now(UTC))
        )
    ).first()
    if row is None:
        return None
    user, expires_at = row
    if user is None:
        return None
    principal = _serialize(user, auth="session")
    ttl = _ttl_until(expires_at)
    if ttl > 0:
        await auth_cache_set(session_cache_key(token_hash), principal, ttl=ttl)
    return principal


async def _user_from_api_key(request: Request, session: AsyncSession) -> dict | None:
    auth_header = request.headers.get("authorization", "")
    token: str | None = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    if not token or not token.startswith(API_KEY_PREFIX):
        return None

    key_hashes = api_key_hashes_for_lookup(token)
    now = datetime.now(UTC)
    row = (
        await session.execute(
            select(ApiKey, User)
            .join(User, User.id == ApiKey.user_id)
            .where(ApiKey.key_hash.in_(key_hashes))
            .where(ApiKey.active.is_(True))
            .where((ApiKey.expires_at.is_(None)) | (ApiKey.expires_at > now))
        )
    ).first()
    if row is None:
        return None

    api_key, user = row
    await _touch_api_key_last_used(str(api_key.id), last_used_at=api_key.last_used_at)

    permissions = api_key.permissions or {}
    scopes = permissions.get("scopes") if isinstance(permissions, dict) else None
    raw_collection = permissions.get("collection") if isinstance(permissions, dict) else None
    collection = raw_collection if isinstance(raw_collection, str) and raw_collection else None
    raw_tenant = permissions.get("tenant") if isinstance(permissions, dict) else None
    tenant_id = raw_tenant if isinstance(raw_tenant, str) and raw_tenant else None
    principal = _serialize(user, auth="api_key", api_key_id=str(api_key.id))
    principal["api_key_name"] = api_key.name
    principal["scopes"] = scopes if isinstance(scopes, list) else None
    principal["collection"] = collection
    principal["tenant_id"] = tenant_id
    principal["active"] = bool(api_key.active)
    principal["expires_at"] = api_key.expires_at.isoformat() if api_key.expires_at else None
    principal["last_used_at"] = api_key.last_used_at.isoformat() if api_key.last_used_at else None
    ttl = _ttl_until(api_key.expires_at)
    if ttl > 0:
        for key_hash in key_hashes:
            await auth_cache_set(api_key_cache_key(key_hash), principal, ttl=ttl)
    return principal


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


async def _touch_api_key_last_used(
    api_key_id: str | None,
    *,
    last_used_at: datetime | None = None,
) -> None:
    if api_key_id is None:
        return

    now = datetime.now(UTC)
    if last_used_at is not None and (now - last_used_at).total_seconds() <= 60:
        return

    redis = redis_cache.get_redis()
    if redis is not None:
        throttle_key = f"bigrag:auth:api_key_touch:{api_key_id}"
        try:
            should_touch = await asyncio.wait_for(
                redis.set(throttle_key, b"1", ex=60, nx=True),
                timeout=REDIS_AUTH_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            should_touch = True
        if not should_touch:
            return

    try:
        target_id = uuid.UUID(api_key_id)
    except ValueError:
        return
    async with session_factory()() as session:
        await session.execute(update(ApiKey).where(ApiKey.id == target_id).values(last_used_at=now))
        await session.commit()


async def invalidate_session_principal(token_hash: str) -> None:
    await auth_cache_delete(session_cache_key(token_hash))


async def invalidate_api_key_principal(key_hash: str) -> None:
    await auth_cache_delete(api_key_cache_key(key_hash))
    try:
        await auth_cache_delete_pattern("auth:api_key:*")
    except Exception as exc:
        logger.debug("auth api-key cache pattern invalidation unavailable", error=str(exc))


async def invalidate_auth_principals() -> None:
    try:
        await auth_cache_delete_pattern("auth:*")
    except Exception as exc:
        logger.debug("auth principal cache invalidation unavailable", error=str(exc))


async def _principal_from_cache(request: Request) -> dict | None:
    cookie = request.cookies.get(_config.settings.session_cookie_name)
    if cookie:
        cached = await auth_cache_get(session_cache_key(hash_session_token(cookie)))
        if isinstance(cached, dict):
            return cached

    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if token.startswith(API_KEY_PREFIX):
            for key_hash in api_key_hashes_for_lookup(token):
                cached = await auth_cache_get(api_key_cache_key(key_hash))
                if isinstance(cached, dict):
                    if _principal_revoked(cached):
                        await auth_cache_delete(api_key_cache_key(key_hash))
                        return None
                    await _touch_api_key_last_used(
                        cached.get("api_key_id"),
                        last_used_at=_parse_iso(cached.get("last_used_at")),
                    )
                    return cached
    return None


async def get_current_user(
    request: Request,
) -> dict:
    from bigrag.services.collection_scope import enforce_collection_scope
    from bigrag.services.scopes import has_scope, required_scope

    principal = await _principal_from_cache(request)
    if principal is None:
        async with session_factory()() as session:
            principal = await _user_from_session(request, session)
            if principal is None:
                principal = await _user_from_api_key(request, session)
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    request.state.user = principal

    if _is_api_key_principal(principal):
        scope = required_scope(request.method, request.url.path)
        if scope and not has_scope(principal.get("scopes"), scope):
            raise HTTPException(
                status_code=403,
                detail=f"API key missing required scope: {scope}",
            )

    pinned = principal.get("collection")
    if pinned:
        await enforce_collection_scope(request, pinned)
    return principal


async def require_session(user: dict = Depends(get_current_user)) -> dict:

    if user.get("auth_method") != "session":
        raise HTTPException(status_code=403, detail="Session authentication required")
    return user


async def require_admin_session(user: dict = Depends(require_session)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def session_expiry() -> datetime:
    from datetime import timedelta

    return datetime.now(UTC) + timedelta(hours=_config.settings.session_expiry_hours)
