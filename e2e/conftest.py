"""Shared pytest fixtures for every Python suite under ``e2e/tests``.

Conventions other agents rely on
--------------------------------

* All async tests use ``pytest-asyncio`` in ``auto`` mode.
* HTTP clients are ``httpx.AsyncClient`` and are function-scoped so
  cookies / auth never leak between tests.
* Collections are uniquely named (``e2e_<8 hex>``) and torn down by the
  ``collection`` factory.
* Admin auth uses Origin-header-based CSRF — bigRAG does **not** issue a
  CSRF token cookie. The session middleware allows a mutating request
  when the Origin header matches an allowed CORS origin or the request
  host. ``_admin_session_request`` and the ``admin_client.request``
  override both set ``Origin: <api_base_url>`` automatically.
* API-key auth uses ``Authorization: Bearer bigrag_sk_...``; no cookies.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import httpx
import pytest
import pytest_asyncio

from tests._helpers import (
    DOCUMENTS_DIR,
    assert_envelope,
    fixture_path,
    poll_until,
    read_fixture,
    unique_name,
)

API_BASE = os.environ.get("BIGRAG_E2E_API_BASE", "http://localhost:4000")
APP_BASE = os.environ.get("BIGRAG_E2E_APP_BASE", "http://localhost:3000")
FAKE_OPENAI_BASE = os.environ.get("BIGRAG_E2E_FAKE_OPENAI", "http://localhost:9001")
FAKE_GDRIVE_BASE = os.environ.get("BIGRAG_E2E_FAKE_GDRIVE", "http://localhost:9002")
WEBHOOK_SINK_BASE = os.environ.get("BIGRAG_E2E_WEBHOOK_SINK", "http://localhost:9003")

FAKE_OPENAI_INTERNAL_BASE = os.environ.get(
    "BIGRAG_E2E_FAKE_OPENAI_INTERNAL", "http://fake-openai:9001"
)
FAKE_GDRIVE_INTERNAL_BASE = os.environ.get(
    "BIGRAG_E2E_FAKE_GDRIVE_INTERNAL", "http://fake-gdrive:9002"
)
WEBHOOK_SINK_INTERNAL_BASE = os.environ.get(
    "BIGRAG_E2E_WEBHOOK_SINK_INTERNAL", "http://webhook-sink:9003"
)

ADMIN_EMAIL = "e2e-admin@example.com"
ADMIN_PASSWORD = "e2e-admin-password-123!"
ADMIN_DISPLAY_NAME = "E2E Admin"

DEFAULT_TIMEOUT = 30.0
DOCUMENT_READY_TIMEOUT = 60.0

__all__ = [
    "API_BASE",
    "APP_BASE",
    "FAKE_OPENAI_BASE",
    "FAKE_GDRIVE_BASE",
    "WEBHOOK_SINK_BASE",
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "ADMIN_DISPLAY_NAME",
    "DOCUMENTS_DIR",
    "assert_envelope",
    "fixture_path",
    "poll_until",
    "read_fixture",
    "unique_name",
]


# ---------------------------------------------------------------------------
# Base URLs
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return API_BASE


@pytest.fixture(scope="session")
def app_base_url() -> str:
    return APP_BASE


@pytest.fixture(scope="session")
def fake_openai_base() -> str:
    """URL bigRAG (running in Docker) uses to reach fake-openai.

    Despite the local-sounding name, this returns the *internal* (Docker
    network) hostname by default — that is the URL tests should pass *into*
    bigRAG, because bigRAG dials it from inside the container network.
    For tests that hit fake-openai *directly* from the host runner, use
    ``fake_openai_host_base`` instead.
    """
    return FAKE_OPENAI_INTERNAL_BASE


@pytest.fixture(scope="session")
def fake_openai_host_base() -> str:
    """URL the test runner (running on the host) uses to reach fake-openai."""
    return FAKE_OPENAI_BASE


@pytest.fixture(scope="session")
def fake_gdrive_base() -> str:
    """Internal (Docker) URL of fake-gdrive — pass this *into* bigRAG."""
    return FAKE_GDRIVE_INTERNAL_BASE


@pytest.fixture(scope="session")
def fake_gdrive_host_base() -> str:
    """Host URL of fake-gdrive for direct calls from the test runner."""
    return FAKE_GDRIVE_BASE


@pytest.fixture(scope="session")
def webhook_sink_base() -> str:
    """Internal (Docker) URL of webhook-sink — pass this *into* bigRAG."""
    return WEBHOOK_SINK_INTERNAL_BASE


@pytest.fixture(scope="session")
def webhook_sink_host_base() -> str:
    """Host URL of webhook-sink for direct GET /received polling from tests."""
    return WEBHOOK_SINK_BASE


# ---------------------------------------------------------------------------
# Unauthenticated client (function-scoped)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def unauth_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        base_url=API_BASE,
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Admin setup-or-login (session-scoped)
# ---------------------------------------------------------------------------


def _origin_headers(url: str = API_BASE) -> dict[str, str]:
    return {"Origin": url}


@pytest_asyncio.fixture(scope="session")
async def admin_setup() -> dict[str, str]:
    """Ensure an admin exists on the running bigRAG instance.

    Returns ``{"email": ..., "password": ..., "display_name": ...}``.

    Safe to call against a fresh database (creates the admin) or against
    a database that already has one (no-op).
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=DEFAULT_TIMEOUT) as client:
        status = await client.get("/v1/auth/setup-status")
        status.raise_for_status()
        if status.json().get("needs_setup"):
            payload = {
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "display_name": ADMIN_DISPLAY_NAME,
            }
            resp = await client.post(
                "/v1/auth/setup",
                json=payload,
                headers=_origin_headers(),
            )
            if resp.status_code not in (200, 201):
                raise RuntimeError(
                    f"failed to setup admin: {resp.status_code} {resp.text}"
                )

    # bigRAG keeps url-safety flags in the DB-backed runtime_settings
    # (env vars only seed *some* of them). Apply the e2e-specific
    # overrides every time so that fake-openai/webhook-sink/fake-gdrive
    # (private Docker hostnames) are reachable.
    await _bootstrap_e2e_runtime_settings()

    return {
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
        "display_name": ADMIN_DISPLAY_NAME,
    }


async def _bootstrap_e2e_runtime_settings() -> None:
    cookies = await _login_and_cache(ADMIN_EMAIL, ADMIN_PASSWORD)
    async with _OriginAwareClient(
        base_url=API_BASE,
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        origin=API_BASE,
    ) as client:
        for k, v in cookies.items():
            client.cookies.set(k, v)
        resp = await client.put(
            "/v1/admin/settings",
            json={
                "values": {
                    "allow_private_embedding_base_urls": True,
                    "allow_private_chat_base_urls": True,
                    "allow_local_webhooks": True,
                }
            },
        )
        if resp.status_code not in (200, 204):
            # If the keys don't exist on this bigRAG build, fall through
            # — individual tests will still surface a clearer failure.
            return


# ---------------------------------------------------------------------------
# Admin client (function-scoped, fresh cookies per test)
# ---------------------------------------------------------------------------


class _OriginAwareClient(httpx.AsyncClient):
    """httpx.AsyncClient that injects an Origin header on mutating requests.

    bigRAG's CSRF middleware (api/bigrag/middleware/csrf.py) rejects
    session-authenticated POST/PUT/PATCH/DELETE without a matching
    Origin header. Per-collection Origin overrides via ``headers=...``
    on the call site still win.
    """

    _origin: str

    def __init__(self, *args: Any, origin: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._origin = origin

    async def request(self, method: str, url: Any, **kwargs: Any) -> httpx.Response:
        mutating = method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
        if mutating:
            headers = dict(kwargs.get("headers") or {})
            headers.setdefault("Origin", self._origin)
            kwargs["headers"] = headers
        return await super().request(method, url, **kwargs)


_ADMIN_COOKIE_CACHE: dict[str, str] = {}


async def _login_and_cache(email: str, password: str) -> dict[str, str]:
    async with httpx.AsyncClient(base_url=API_BASE, timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.post(
            "/v1/auth/login",
            json={"email": email, "password": password},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"admin login failed: {resp.status_code} {resp.text}")
        return dict(client.cookies)


@pytest_asyncio.fixture
async def admin_client(
    admin_setup: dict[str, str],
) -> AsyncIterator[httpx.AsyncClient]:
    """Authenticated admin client with a session cookie + Origin header.

    The session cookie is cached across tests so we don't trip bigRAG's
    10-login-per-IP-per-minute rate limit on /v1/auth/login. Tests that
    deliberately invalidate the session (logout-all, password change) cause
    the cache to be invalidated transparently — the next test re-logs in.
    """
    if not _ADMIN_COOKIE_CACHE:
        _ADMIN_COOKIE_CACHE.update(
            await _login_and_cache(admin_setup["email"], admin_setup["password"])
        )

    async with _OriginAwareClient(
        base_url=API_BASE,
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        origin=API_BASE,
    ) as client:
        for k, v in _ADMIN_COOKIE_CACHE.items():
            client.cookies.set(k, v)
        resp = await client.get("/v1/auth/me")
        if resp.status_code != 200:
            client.cookies.clear()
            _ADMIN_COOKIE_CACHE.clear()
            _ADMIN_COOKIE_CACHE.update(
                await _login_and_cache(admin_setup["email"], admin_setup["password"])
            )
            for k, v in _ADMIN_COOKIE_CACHE.items():
                client.cookies.set(k, v)
        yield client


# ---------------------------------------------------------------------------
# API key factory + bearer-auth client factory
# ---------------------------------------------------------------------------

ApiKeyFactory = Callable[..., Awaitable[dict[str, Any]]]
ApiKeyClientFactory = Callable[..., Awaitable[httpx.AsyncClient]]


@pytest_asyncio.fixture
async def api_key(
    admin_client: httpx.AsyncClient,
) -> AsyncIterator[ApiKeyFactory]:
    """Factory that mints API keys and revokes them on teardown.

    Usage::

        key = await api_key(name="docs-rw", scopes=["document:upload"])
        assert key["key"].startswith("bigrag_sk_")
    """
    created_ids: list[str] = []

    async def _mint(
        name: str | None = None,
        *,
        scopes: list[str] | None = None,
        collection: str | None = None,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name or unique_name("key")}
        if scopes is not None:
            payload["scopes"] = scopes
        if collection is not None:
            payload["collection"] = collection
        if expires_at is not None:
            payload["expires_at"] = expires_at
        resp = await admin_client.post("/v1/admin/api-keys", json=payload)
        data = assert_envelope(resp, 201)
        created_ids.append(data["id"])
        return data

    yield _mint

    for key_id in created_ids:
        try:
            await admin_client.delete(f"/v1/admin/api-keys/{key_id}")
        except Exception:
            pass


@pytest_asyncio.fixture
async def api_key_client(
    api_key: ApiKeyFactory,
) -> AsyncIterator[ApiKeyClientFactory]:
    """Factory that returns an httpx client with ``Authorization: Bearer``.

    Pass ``key=<dict-from-api_key>`` to reuse a previously-minted key, or
    call without arguments to mint a fresh full-access key.
    """
    clients: list[httpx.AsyncClient] = []

    async def _build(
        key: dict[str, Any] | None = None,
        *,
        scopes: list[str] | None = None,
        collection: str | None = None,
    ) -> httpx.AsyncClient:
        secret = key
        if secret is None:
            secret = await api_key(scopes=scopes, collection=collection)
        token = secret["key"]
        client = httpx.AsyncClient(
            base_url=API_BASE,
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers={"Authorization": f"Bearer {token}"},
        )
        clients.append(client)
        return client

    yield _build

    for client in clients:
        await client.aclose()


# ---------------------------------------------------------------------------
# Collection factory
# ---------------------------------------------------------------------------

CollectionFactory = Callable[..., Awaitable[dict[str, Any]]]


@pytest_asyncio.fixture
async def collection(
    admin_client: httpx.AsyncClient,
) -> AsyncIterator[CollectionFactory]:
    """Factory creating uniquely-named collections; deletes them on teardown.

    The instance is configured with embedding credentials at deploy time
    (``BIGRAG_EMBEDDING_*`` env vars point at fake-openai), so we only
    need to supply the bare minimum here. To override, pass any
    ``CreateCollectionRequest`` field as a kwarg::

        coll = await collection(dimension=384, vector_store_provider="qdrant")
    """
    created_names: list[str] = []

    async def _create(
        *,
        name: str | None = None,
        description: str = "e2e fixture collection",
        dimension: int | None = 1536,
        vector_store_provider: str = "qdrant",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        chunk_strategy: str = "paragraph",
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_api_key: str | None = None,
        embedding_base_url: str | None = None,
        embedding_preset_id: str | None = None,
        tenant_field: str | None = None,
        metadata: dict | None = None,
        metadata_schema: dict | None = None,
        reranking_enabled: bool = False,
        reranking_model: str | None = None,
        reranking_api_key: str | None = None,
        default_top_k: int = 10,
        default_min_score: float | None = None,
        default_search_mode: str = "semantic",
        **extras: Any,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name or unique_name("e2e"),
            "description": description,
            "vector_store_provider": vector_store_provider,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "chunk_strategy": chunk_strategy,
            "reranking_enabled": reranking_enabled,
            "default_top_k": default_top_k,
            "default_search_mode": default_search_mode,
        }
        if dimension is not None:
            body["dimension"] = dimension
        if embedding_provider is not None:
            body["embedding_provider"] = embedding_provider
        if embedding_model is not None:
            body["embedding_model"] = embedding_model
        if embedding_api_key is not None:
            body["embedding_api_key"] = embedding_api_key
        if embedding_base_url is not None:
            body["embedding_base_url"] = embedding_base_url
        if embedding_preset_id is not None:
            body["embedding_preset_id"] = embedding_preset_id
        if tenant_field is not None:
            body["tenant_field"] = tenant_field
        if metadata is not None:
            body["metadata"] = metadata
        if metadata_schema is not None:
            body["metadata_schema"] = metadata_schema
        if reranking_model is not None:
            body["reranking_model"] = reranking_model
        if reranking_api_key is not None:
            body["reranking_api_key"] = reranking_api_key
        if default_min_score is not None:
            body["default_min_score"] = default_min_score
        body.update(extras)

        resp = await admin_client.post("/v1/collections", json=body)
        data = assert_envelope(resp, 201)
        created_names.append(data["name"])
        return data

    yield _create

    for name in created_names:
        try:
            await admin_client.delete(f"/v1/collections/{name}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Document factory
# ---------------------------------------------------------------------------

DocumentFactory = Callable[..., Awaitable[dict[str, Any]]]


@pytest_asyncio.fixture
async def document(
    admin_client: httpx.AsyncClient,
) -> AsyncIterator[DocumentFactory]:
    """Factory that uploads a fixture into a collection and polls until ready.

    Usage::

        coll = await collection()
        doc = await document(coll["name"], fixture="sample.txt")
        assert doc["status"] == "ready"

    Pass ``wait=False`` to skip polling. Pass ``terminal_statuses`` to
    short-circuit on a custom set (default: ``{"ready", "failed"}``).
    """

    async def _upload(
        collection_name: str,
        *,
        fixture: str = "sample.txt",
        content: bytes | None = None,
        filename: str | None = None,
        metadata: dict | None = None,
        wait: bool = True,
        timeout: float = DOCUMENT_READY_TIMEOUT,
        terminal_statuses: set[str] | None = None,
    ) -> dict[str, Any]:
        if content is None:
            content = read_fixture(fixture)
        upload_name = filename or fixture
        files = {"file": (upload_name, content, "application/octet-stream")}
        data = {}
        if metadata is not None:
            import json

            data["metadata"] = json.dumps(metadata)

        resp = await admin_client.post(
            f"/v1/collections/{collection_name}/documents",
            files=files,
            data=data or None,
        )
        body = assert_envelope(resp, 201)
        doc_id = body["id"]

        if not wait:
            return body

        terminal = terminal_statuses or {"ready", "failed"}

        async def _fetch() -> dict[str, Any]:
            r = await admin_client.get(
                f"/v1/collections/{collection_name}/documents/{doc_id}"
            )
            r.raise_for_status()
            return r.json()

        doc = await poll_until(
            _fetch,
            predicate=lambda d: d.get("status") in terminal,
            timeout=timeout,
            interval=0.5,
            description=f"document {doc_id} terminal status",
        )
        if doc.get("status") == "failed" and "failed" not in (terminal_statuses or set()):
            err = doc.get("error") or doc.get("error_message") or doc.get("status_message")
            if err:
                raise AssertionError(
                    f"document {doc_id} ({upload_name}) ingestion failed: {err}"
                )
        return doc

    yield _upload


# ---------------------------------------------------------------------------
# Webhook-sink helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def webhook_sink_url() -> Callable[[str], str]:
    """Returns webhook URLs *bigRAG* should call — internal Docker hostname."""
    def _build(label: str) -> str:
        return f"{WEBHOOK_SINK_INTERNAL_BASE}/webhook/{label}"

    return _build


@pytest_asyncio.fixture
async def webhook_sink() -> AsyncIterator[dict[str, Any]]:
    """Reset the webhook sink before and after each test that uses it.

    The ``url(label)`` helper returns the *internal* Docker URL bigRAG dials,
    while polling helpers (``wait``, ``received``) hit the sink directly from
    the host runner.
    """
    async with httpx.AsyncClient(base_url=WEBHOOK_SINK_BASE, timeout=DEFAULT_TIMEOUT) as client:
        await client.post("/reset")

        async def received(label: str | None = None) -> list[dict[str, Any]]:
            params: dict[str, Any] = {}
            if label is not None:
                params["label"] = label
            r = await client.get("/received", params=params)
            r.raise_for_status()
            return r.json().get("deliveries", [])

        async def wait(label: str, count: int = 1, timeout: float = 10.0) -> list[dict[str, Any]]:
            return await poll_until(
                lambda: received(label),
                predicate=lambda items: len(items) >= count,
                timeout=timeout,
                interval=0.2,
                description=f"{count} webhook(s) for label={label!r}",
            )

        async def fail_next(label: str, count: int = 1) -> None:
            r = await client.post(f"/fail/{label}", params={"count": count})
            r.raise_for_status()

        def url(label: str) -> str:
            return f"{WEBHOOK_SINK_INTERNAL_BASE}/webhook/{label}"

        try:
            yield {
                "url": url,
                "received": received,
                "wait": wait,
                "fail_next": fail_next,
            }
        finally:
            try:
                await client.post("/reset")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Fake Google Drive OAuth helper
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def gdrive_oauth_helper() -> AsyncIterator[dict[str, Any]]:
    """Helper that drives the fake-gdrive OAuth code-grant flow.

    Returns a bundle::

        helper["consent_url"](client_id, redirect_uri, state, scope)
        await helper["exchange_code"](client_id, client_secret, code, redirect_uri)
    """
    async with httpx.AsyncClient(base_url=FAKE_GDRIVE_BASE, timeout=DEFAULT_TIMEOUT) as client:

        def consent_url(
            client_id: str,
            redirect_uri: str,
            state: str,
            scope: str = "https://www.googleapis.com/auth/drive.readonly",
        ) -> str:
            from urllib.parse import urlencode

            qs = urlencode(
                {
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "state": state,
                    "scope": scope,
                    "response_type": "code",
                }
            )
            return f"{FAKE_GDRIVE_BASE}/o/oauth2/auth?{qs}"

        async def exchange_code(
            client_id: str,
            client_secret: str,
            code: str,
            redirect_uri: str,
        ) -> dict[str, Any]:
            r = await client.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                },
            )
            r.raise_for_status()
            return r.json()

        yield {
            "consent_url": consent_url,
            "exchange_code": exchange_code,
            "client": client,
        }


# ---------------------------------------------------------------------------
# SSE event helper
# ---------------------------------------------------------------------------


def sse_events(client: httpx.AsyncClient, path: str, **kwargs: Any):
    """Return an async iterator of ``httpx_sse.ServerSentEvent``.

    Use as::

        async with sse_events(admin_client, f"/v1/collections/{name}/events") as events:
            async for event in events:
                ...
    """
    from httpx_sse import aconnect_sse

    return aconnect_sse(client, "GET", path, **kwargs)
