from __future__ import annotations

from urllib.parse import urlparse

from fastapi import WebSocket

from bigrag import config as _config
from bigrag.db.engine import session_factory
from bigrag.middleware import auth as auth_middleware
from bigrag.services import runtime_settings
from bigrag.services.collection_scope import assert_collection_matches_pin
from bigrag.services.realtime_tokens import validate_realtime_token
from bigrag.services.scopes import has_scope


async def connection_principal(websocket: WebSocket) -> dict | None:
    async with session_factory()() as session:
        principal = await auth_middleware._user_from_session(websocket, session)
        if principal is None:
            principal = await auth_middleware._user_from_api_key(websocket, session)
    if principal is not None:
        websocket.state.user = principal
    return principal


async def cookie_origin_allowed(websocket: WebSocket) -> bool:
    if _config.settings.session_cookie_name not in websocket.cookies:
        return True
    origin = websocket.headers.get("origin")
    if not origin:
        return False
    try:
        cors_origins = await runtime_settings.get_value("cors_origins")
        if not isinstance(cors_origins, list):
            cors_origins = []
    except Exception:
        cors_origins = websocket.app.state.settings.cors_origins
    if "*" in cors_origins or origin in cors_origins:
        return True
    parsed = urlparse(origin)
    if not parsed.scheme or not parsed.netloc:
        return False
    websocket_scheme = websocket.url.scheme
    expected_scheme = "https" if websocket_scheme == "wss" else "http"
    return parsed.scheme == expected_scheme and parsed.netloc == websocket.headers.get("host")


def is_admin_session(principal: dict | None) -> bool:
    return bool(
        principal and principal.get("auth_method") == "session" and principal.get("role") == "admin"
    )


async def authorize_admin(principal: dict | None) -> None:
    if not is_admin_session(principal):
        raise PermissionError("Admin session required")


async def authorize_collection_events(
    websocket: WebSocket,
    principal: dict | None,
    collection_name: str,
    token: str | None,
) -> None:
    pinned = principal.get("collection") if principal else None
    if pinned:
        assert_collection_matches_pin(pinned, collection_name)
    if token and await validate_realtime_token(token, collection_name, principal):
        return
    if principal is None:
        raise PermissionError("Authentication required")
    if principal.get("auth_method") == "api_key" and not has_scope(
        principal.get("scopes"), "collection:read"
    ):
        raise PermissionError("API key missing required scope: collection:read")
