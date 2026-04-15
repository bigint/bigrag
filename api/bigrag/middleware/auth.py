"""Auth dependencies for FastAPI routes.

Resolves an authenticated principal from either:
  * a session cookie set by the login endpoint (browser / Studio UI), or
  * an ``Authorization: Bearer bigrag_sk_...`` API key (external clients).

Session cookies and API keys both ultimately resolve to a user row.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.config import settings
from bigrag.db.models import ApiKey, User
from bigrag.db.models import Session as DbSession
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.services.auth import API_KEY_PREFIX, hash_api_key, hash_session_token

logger = get_logger("bigrag.auth")


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
        # Sessions (browser / Studio) have no scope list — admin users keep
        # implicit full access. Scoped keys override this in
        # ``_user_from_api_key``.
        "scopes": None,
        "collection": None,
        "rate_limits": None,
    }


async def _user_from_session(request: Request, session: AsyncSession) -> dict | None:
    cookie = request.cookies.get(settings.session_cookie_name)
    if not cookie:
        return None

    token_hash = hash_session_token(cookie)
    user = await session.scalar(
        select(User)
        .join(DbSession, DbSession.user_id == User.id)
        .where(DbSession.token_hash == token_hash)
        .where(DbSession.expires_at > datetime.now(UTC))
    )
    if user is None:
        return None
    return _serialize(user, auth="session")


async def _user_from_api_key(request: Request, session: AsyncSession) -> dict | None:
    auth_header = request.headers.get("authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        query_token = request.query_params.get("token")
        if query_token:
            token = query_token

    if not token or not token.startswith(API_KEY_PREFIX):
        return None

    key_hash = hash_api_key(token)
    now = datetime.now(UTC)
    row = (
        await session.execute(
            select(ApiKey, User)
            .join(User, User.id == ApiKey.user_id)
            .where(ApiKey.key_hash == key_hash)
            .where(ApiKey.active.is_(True))
            .where((ApiKey.expires_at.is_(None)) | (ApiKey.expires_at > now))
        )
    ).first()
    if row is None:
        return None

    api_key, user = row
    await session.execute(update(ApiKey).where(ApiKey.id == api_key.id).values(last_used_at=now))
    await session.commit()

    permissions = api_key.permissions or {}
    scopes = permissions.get("scopes") if isinstance(permissions, dict) else None
    raw_collection = permissions.get("collection") if isinstance(permissions, dict) else None
    collection = raw_collection if isinstance(raw_collection, str) and raw_collection else None
    principal = _serialize(user, auth="api_key", api_key_id=str(api_key.id))
    principal["api_key_name"] = api_key.name
    principal["scopes"] = scopes if isinstance(scopes, list) else None
    principal["collection"] = collection
    principal["rate_limits"] = api_key.rate_limits or {}
    return principal


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    from bigrag.services.collection_scope import enforce_collection_scope
    from bigrag.services.scopes import has_scope, required_scope

    principal = await _user_from_session(request, session)
    if principal is None:
        principal = await _user_from_api_key(request, session)
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Enforce scoped-key permissions. Sessions (scopes=None) always pass.
    scope = required_scope(request.method, request.url.path)
    if scope and not has_scope(principal.get("scopes"), scope):
        raise HTTPException(
            status_code=403,
            detail=f"API key missing required scope: {scope}",
        )

    # Enforce collection-pinning on API keys that carry one.
    pinned = principal.get("collection")
    if pinned:
        await enforce_collection_scope(request, pinned)
    return principal


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_session(user: dict = Depends(get_current_user)) -> dict:
    """Require a logged-in admin (session cookie), not an API key.

    Used for account-management endpoints where a machine credential must
    not be able to escalate (e.g., change passwords, create users).
    """
    if user.get("auth_method") != "session":
        raise HTTPException(status_code=403, detail="Session authentication required")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def session_expiry() -> datetime:
    from datetime import timedelta

    return datetime.now(UTC) + timedelta(hours=settings.session_expiry_hours)
