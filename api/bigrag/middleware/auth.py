"""Auth dependencies for FastAPI routes.

Resolves an authenticated principal from either:
  * a session cookie set by the login endpoint (browser / Studio UI), or
  * an ``Authorization: Bearer bigrag_sk_...`` API key (external clients).

Session cookies and API keys both ultimately resolve to a user row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request

from bigrag.config import settings
from bigrag.database import db
from bigrag.logging import get_logger
from bigrag.services.auth import API_KEY_PREFIX, hash_api_key, hash_session_token

logger = get_logger("bigrag.auth")


def _serialize_user(row: dict, *, auth: str, api_key_id: str | None = None) -> dict:
    return {
        "id": str(row["id"]),
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
        "auth_method": auth,
        "api_key_id": api_key_id,
        # Sessions (browser / Studio) have no scope list — admin users
        # keep implicit full access. Scoped keys override this in
        # ``_user_from_api_key``.
        "scopes": None,
        "rate_limits": None,
    }


async def _user_from_session(request: Request) -> dict | None:
    cookie = request.cookies.get(settings.session_cookie_name)
    if not cookie:
        return None

    token_hash = hash_session_token(cookie)
    row = await db.fetchrow(
        """
        SELECT u.*
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = $1 AND s.expires_at > now()
        """,
        token_hash,
    )
    if not row:
        return None
    return _serialize_user(dict(row), auth="session")


async def _user_from_api_key(request: Request) -> dict | None:
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
    row = await db.fetchrow(
        """
        SELECT u.*,
               k.id AS api_key_id,
               k.permissions AS api_key_permissions,
               k.rate_limits AS api_key_rate_limits
        FROM api_keys k
        JOIN users u ON u.id = k.user_id
        WHERE k.key_hash = $1
          AND k.active = true
          AND (k.expires_at IS NULL OR k.expires_at > now())
        """,
        key_hash,
    )
    if not row:
        return None

    api_key_id = str(row["api_key_id"])
    await db.execute(
        "UPDATE api_keys SET last_used_at = now() WHERE id = $1",
        uuid.UUID(api_key_id),
    )
    permissions = row.get("api_key_permissions") or {}
    scopes = permissions.get("scopes") if isinstance(permissions, dict) else None
    user_row = {k: v for k, v in dict(row).items() if k not in {
        "api_key_id", "api_key_permissions", "api_key_rate_limits",
    }}
    principal = _serialize_user(user_row, auth="api_key", api_key_id=api_key_id)
    principal["scopes"] = scopes if isinstance(scopes, list) else None
    principal["rate_limits"] = row.get("api_key_rate_limits") or {}
    return principal


async def get_current_user(request: Request) -> dict:
    from bigrag.services.scopes import has_scope, required_scope

    principal: dict | None = None
    session_user = await _user_from_session(request)
    if session_user:
        principal = session_user
    else:
        api_key_user = await _user_from_api_key(request)
        if api_key_user:
            principal = api_key_user

    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Enforce scoped-key permissions. Sessions (scopes=None) always pass.
    scope = required_scope(request.method, request.url.path)
    if scope and not has_scope(principal.get("scopes"), scope):
        raise HTTPException(
            status_code=403,
            detail=f"API key missing required scope: {scope}",
        )
    return principal


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_session(user: dict = Depends(get_current_user)) -> dict:
    """Require a logged-in admin (session cookie), not an API key.

    Used for account-management endpoints where a machine credential
    must not be able to escalate (e.g., change passwords, create users).
    """
    if user.get("auth_method") != "session":
        raise HTTPException(status_code=403, detail="Session authentication required")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def session_expiry() -> datetime:
    from datetime import timedelta

    return datetime.now(UTC) + timedelta(hours=settings.session_expiry_hours)
