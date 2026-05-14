from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from bigrag.middleware import _principal, auth, cors, idempotency
from bigrag.services.auth import API_KEY_PREFIX


class ExecuteRows:
    def __init__(self, row=None) -> None:
        self.row = row

    def first(self):
        return self.row


class FakeSession:
    def __init__(self, row=None) -> None:
        self.row = row
        self.executed = []
        self.commits = 0

    async def execute(self, stmt):
        self.executed.append(stmt)
        return ExecuteRows(self.row)

    async def commit(self):
        self.commits += 1


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}
        self.deleted = []
        self.patterns = []
        self.touches = []

    async def set(self, key, value, ex=None, nx=False):
        self.touches.append((key, value, ex, nx))
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True


def request_for(*, headers=None, cookies=None, method="GET", path="/v1/collections"):
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers or [],
        "query_string": b"",
        "client": ("203.0.113.5", 123),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope)
    if cookies is not None:
        request._cookies = cookies
    return request


def test_principal_id_prefers_api_key_query_cookie_and_ip(monkeypatch) -> None:
    monkeypatch.setattr(_principal, "hash_api_key", lambda token: f"h-{token[-4:]}")
    monkeypatch.setattr(_principal, "hash_session_token", lambda token: f"s-{token}")
    monkeypatch.setattr(_principal._config.settings, "session_cookie_name", "bigrag_session")

    assert (
        _principal.principal_id(
            {
                "type": "http",
                "headers": [(b"authorization", f"Bearer {API_KEY_PREFIX}abcd".encode())],
            }
        )
        == "key:h-abcd"
    )
    assert (
        _principal.principal_id(
            {"type": "http", "headers": [], "query_string": f"token={API_KEY_PREFIX}qwer".encode()}
        )
        == "key:h-qwer"
    )
    assert (
        _principal.principal_id(
            {"type": "http", "headers": [(b"cookie", b"bigrag_session=session-token")]}
        )
        == "sess:s-session-token"
    )
    ip_scope = {"type": "http", "headers": [], "client": ("198.51.100.7", 1)}
    assert _principal.principal_id(ip_scope) == "ip:198.51.100.7"
    assert _principal.principal_id({"type": "http", "headers": []}) == "ip:unknown"


def test_auth_helpers_cache_ttl_and_principal_serialization(monkeypatch) -> None:
    user = SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        email="admin@example.com",
        display_name="Admin",
        role="admin",
    )
    monkeypatch.setattr(auth._config.settings, "auth_principal_cache_ttl", 120)

    assert auth._session_cache_key("hash") == "auth:session:hash"
    assert auth._api_key_cache_key("hash") == "auth:api_key:hash"
    assert auth._ttl_until(None) == 120
    assert auth._ttl_until(datetime.now(UTC) + timedelta(seconds=5)) <= 5
    assert auth._ttl_until(datetime.now(UTC) - timedelta(seconds=1)) == 0
    assert auth._serialize(user, auth="session") == {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "admin@example.com",
        "display_name": "Admin",
        "role": "admin",
        "auth_method": "session",
        "api_key_id": None,
        "api_key_name": None,
        "scopes": None,
        "collection": None,
    }


def test_auth_loads_session_and_api_key_principals(monkeypatch) -> None:
    async def run() -> None:
        cache = {}
        deleted = []

        async def cache_get(key):
            return cache.get(key)

        async def cache_set(key, value, ttl):
            cache[key] = value

        async def cache_delete(key):
            deleted.append(key)

        async def cache_delete_pattern(pattern):
            deleted.append(pattern)
            return 1

        monkeypatch.setattr(auth.redis_cache, "get", cache_get)
        monkeypatch.setattr(auth.redis_cache, "set", cache_set)
        monkeypatch.setattr(auth.redis_cache, "delete", cache_delete)
        monkeypatch.setattr(auth.redis_cache, "delete_pattern", cache_delete_pattern)
        monkeypatch.setattr(auth.redis_cache, "get_redis", lambda: None)
        monkeypatch.setattr(auth, "hash_session_token", lambda token: f"s-{token}")
        monkeypatch.setattr(auth, "api_key_hashes_for_lookup", lambda token: [f"k-{token[-4:]}"])
        monkeypatch.setattr(auth._config.settings, "session_cookie_name", "bigrag_session")
        monkeypatch.setattr(auth._config.settings, "auth_principal_cache_ttl", 120)

        user = SimpleNamespace(
            id="11111111-1111-1111-1111-111111111111",
            email="admin@example.com",
            display_name="Admin",
            role="admin",
        )
        session_principal = await auth._user_from_session(
            request_for(cookies={"bigrag_session": "token"}),
            FakeSession((user, datetime.now(UTC) + timedelta(minutes=5))),
        )
        assert session_principal["auth_method"] == "session"
        assert await auth._user_from_session(request_for(cookies={}), FakeSession()) is None

        api_key = SimpleNamespace(
            id="22222222-2222-2222-2222-222222222222",
            name="SDK",
            permissions={"scopes": ["collections:read"], "collection": "docs"},
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            key_hash="k-abcd",
            last_used_at=None,
        )
        api_session = FakeSession((api_key, user))
        api_principal = await auth._user_from_api_key(
            request_for(headers=[(b"authorization", f"Bearer {API_KEY_PREFIX}abcd".encode())]),
            api_session,
        )
        assert api_principal["api_key_name"] == "SDK"
        assert api_principal["collection"] == "docs"
        assert api_session.commits == 1
        assert await auth._user_from_api_key(request_for(headers=[]), FakeSession()) is None

        await auth.invalidate_session_principal("s")
        await auth.invalidate_api_key_principal("k")
        await auth.invalidate_auth_principals()
        assert deleted == ["auth:session:s", "auth:api_key:k", "auth:*"]

    asyncio.run(run())


def test_auth_current_user_requirements_and_scope_enforcement(monkeypatch) -> None:
    async def run() -> None:
        calls = []

        async def no_session(request, session):
            return None

        async def api_user(request, session):
            return {
                "auth_method": "api_key",
                "role": "member",
                "scopes": ["collection:read"],
                "collection": "docs",
            }

        async def enforce(request, pinned):
            calls.append((request.url.path, pinned))

        monkeypatch.setattr(auth, "_user_from_session", no_session)
        monkeypatch.setattr(auth, "_user_from_api_key", api_user)
        monkeypatch.setattr("bigrag.services.collection_scope.enforce_collection_scope", enforce)

        principal = await auth.get_current_user(
            request_for(method="GET", path="/v1/collections/docs"),
            FakeSession(),
        )
        assert principal["auth_method"] == "api_key"
        assert calls == [("/v1/collections/docs", "docs")]

        with pytest.raises(HTTPException):
            await auth.require_session(principal)
        with pytest.raises(HTTPException):
            await auth.require_admin_session({"auth_method": "session", "role": "member"})
        assert await auth.require_admin_session({"auth_method": "session", "role": "admin"}) == {
            "auth_method": "session",
            "role": "admin",
        }

        monkeypatch.setattr(auth, "_user_from_api_key", no_session)
        with pytest.raises(HTTPException) as exc:
            await auth.get_current_user(request_for(), FakeSession())
        assert exc.value.status_code == 401

    asyncio.run(run())


def test_cors_and_idempotency_middleware(monkeypatch) -> None:
    async def run() -> None:
        async def get_value(key):
            if key == "cors_origins":
                return ["https://admin.example"]
            raise RuntimeError("unknown")

        monkeypatch.setattr(cors.runtime_settings, "get_value", get_value)

        async def call_next(request):
            return __import__("starlette.responses").responses.Response("ok")

        request = request_for(
            headers=[(b"origin", b"https://admin.example")],
            method="OPTIONS",
            path="/v1/collections",
        )
        request.scope["headers"].append((b"access-control-request-method", b"POST"))
        request.scope["app"] = SimpleNamespace(
            state=SimpleNamespace(settings=SimpleNamespace(cors_origins=[]))
        )
        response = await cors.RuntimeCorsMiddleware(lambda scope, receive, send: None).dispatch(
            request,
            call_next,
        )
        assert response.status_code == 204
        assert response.headers["Access-Control-Allow-Origin"] == "https://admin.example"

        cached = {}

        async def cache_get(key):
            return cached.get(key)

        async def cache_set(key, value, ttl):
            cached[key] = value

        monkeypatch.setattr(idempotency.redis_cache, "get", cache_get)
        monkeypatch.setattr(idempotency.redis_cache, "set", cache_set)
        monkeypatch.setattr(idempotency, "principal_id", lambda scope: "user")

        async def app(scope, receive, send):
            await send(
                {
                    "type": "http.response.start",
                    "status": 201,
                    "headers": [(b"x-test", b"1"), (b"set-cookie", b"session=abc")],
                }
            )
            await send({"type": "http.response.body", "body": b"created"})

        middleware = idempotency.IdempotencyMiddleware(app, ttl_seconds=30)
        messages = []
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/v1/items",
            "headers": [(b"idempotency-key", b"abc")],
        }

        async def receive():
            return {"type": "http.request", "body": b""}

        replay = []

        async def replay_send(message):
            replay.append(message)

        async def message_send(message):
            messages.append(message)

        await middleware(scope, receive, message_send)
        await middleware(scope, receive, replay_send)

        assert messages[0]["status"] == 201
        assert replay[0]["status"] == 201
        assert (b"idempotency-key-replayed", b"true") in replay[0]["headers"]
        assert not any(name == b"set-cookie" for name, _value in replay[0]["headers"])

        conflict = []

        async def conflict_receive():
            return {"type": "http.request", "body": b"different"}

        async def conflict_send(message):
            conflict.append(message)

        await middleware(scope, conflict_receive, conflict_send)
        assert conflict[0]["status"] == 409

    asyncio.run(run())
