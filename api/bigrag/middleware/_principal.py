from __future__ import annotations

from http.cookies import SimpleCookie

from starlette.datastructures import Headers
from starlette.types import Scope

from bigrag.config import settings
from bigrag.services.auth import API_KEY_PREFIX, hash_api_key, hash_session_token


def principal_id(scope: Scope, headers: Headers | None = None) -> str:
    if headers is None:
        headers = Headers(scope=scope)

    auth = headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        if token.startswith(API_KEY_PREFIX):
            return f"key:{hash_api_key(token)}"

    query_string = scope.get("query_string", b"")
    if query_string:
        from urllib.parse import parse_qs

        params = parse_qs(query_string.decode("latin-1"))
        token_vals = params.get("token") or []
        if token_vals and token_vals[0].startswith(API_KEY_PREFIX):
            return f"key:{hash_api_key(token_vals[0])}"

    cookie_header = headers.get("cookie")
    if cookie_header:
        jar = SimpleCookie()
        try:
            jar.load(cookie_header)
        except Exception:
            jar = SimpleCookie()
        morsel = jar.get(settings.session_cookie_name)
        if morsel and morsel.value:
            return f"sess:{hash_session_token(morsel.value)}"

    client = scope.get("client")
    if client:
        return f"ip:{client[0]}"
    return "ip:unknown"
