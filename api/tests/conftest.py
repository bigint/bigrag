"""Shared fixtures for bigRAG E2E tests.

Uses FastAPI's TestClient (httpx AsyncClient + ASGITransport) with mocked
service singletons so tests run without Postgres, Milvus, or Redis.
"""

from __future__ import annotations

import contextlib
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from bigrag.services.auth import hash_api_key, hash_session_token

TEST_API_KEY = "bigrag_sk_test-external-key-aBcDeFgHiJkLmNoPq"
TEST_SESSION_TOKEN = "test-session-token-abc123"
TEST_USER_ID = str(uuid.uuid4())
TEST_API_KEY_ID = str(uuid.uuid4())
SAMPLE_COLLECTION_ID = str(uuid.uuid4())
SAMPLE_DOCUMENT_ID = str(uuid.uuid4())
SAMPLE_WEBHOOK_ID = str(uuid.uuid4())


def make_user_row(
    user_id: str | None = None,
    *,
    email: str = "admin@example.com",
    display_name: str = "Admin",
    role: str = "admin",
    password_hash: str = "$argon2id$dummy",
) -> dict:
    now = datetime.now(UTC)
    return {
        "id": uuid.UUID(user_id) if user_id else uuid.uuid4(),
        "email": email,
        "password_hash": password_hash,
        "display_name": display_name,
        "role": role,
        "last_login_at": now,
        "created_at": now,
        "updated_at": now,
    }


def make_api_key_row(
    key_id: str | None = None,
    user_id: str | None = None,
    *,
    name: str = "default",
    prefix: str = "bigrag_sk_test",
    key_hash: str = "",
    active: bool = True,
) -> dict:
    now = datetime.now(UTC)
    return {
        "id": uuid.UUID(key_id) if key_id else uuid.uuid4(),
        "user_id": uuid.UUID(user_id) if user_id else uuid.uuid4(),
        "name": name,
        "key_hash": key_hash,
        "prefix": prefix,
        "permissions": {},
        "active": active,
        "expires_at": None,
        "last_used_at": None,
        "created_at": now,
        "updated_at": now,
    }


def make_collection_row(
    name: str = "test_col",
    *,
    collection_id: str | None = None,
    description: str = "",
    embedding_provider: str = "openai",
    embedding_model: str = "text-embedding-3-small",
    dimension: int = 1536,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    chunk_strategy: str = "paragraph",
    document_count: int = 0,
    embedding_api_key: str | None = "sk-test",
    embedding_base_url: str | None = None,
    reranking_enabled: bool = False,
    reranking_model: str = "rerank-v3.5",
    reranking_api_key: str | None = None,
    default_top_k: int = 10,
    default_min_score: float | None = None,
    default_search_mode: str = "semantic",
    metadata: dict | None = None,
    metadata_schema: dict | None = None,
    redact_pii: bool = False,
    moderation_enabled: bool = False,
) -> dict:
    return {
        "id": uuid.UUID(collection_id) if collection_id else uuid.uuid4(),
        "name": name,
        "description": description,
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "dimension": dimension,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "chunk_strategy": chunk_strategy,
        "document_count": document_count,
        "embedding_api_key": embedding_api_key,
        "embedding_base_url": embedding_base_url,
        "reranking_enabled": reranking_enabled,
        "reranking_model": reranking_model,
        "reranking_api_key": reranking_api_key,
        "default_top_k": default_top_k,
        "default_min_score": default_min_score,
        "default_search_mode": default_search_mode,
        "metadata": metadata or {},
        "metadata_schema": metadata_schema,
        "redact_pii": redact_pii,
        "moderation_enabled": moderation_enabled,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }


def make_document_row(
    document_id: str | None = None,
    collection_id: str | None = None,
    *,
    filename: str = "test.pdf",
    file_type: str = "pdf",
    file_size: int = 1024,
    file_path: str = "test_col/test.pdf",
    chunk_count: int = 5,
    status: str = "ready",
    error_message: str | None = None,
    metadata: dict | None = None,
    content_hash: str | None = None,
) -> dict:
    return {
        "id": uuid.UUID(document_id) if document_id else uuid.uuid4(),
        "collection_id": uuid.UUID(collection_id) if collection_id else uuid.uuid4(),
        "filename": filename,
        "file_type": file_type,
        "file_size": file_size,
        "file_path": file_path,
        "chunk_count": chunk_count,
        "status": status,
        "error_message": error_message,
        "metadata": metadata or {},
        "content_hash": content_hash,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }


def make_webhook_row(
    webhook_id: str | None = None,
    *,
    url: str = "https://example.com/webhook",
    secret: str = "whsec_test123",
    events: list[str] | None = None,
    collections: list[str] | None = None,
    description: str = "test webhook",
    active: bool = True,
    created_by: str | None = None,
) -> dict:
    return {
        "id": uuid.UUID(webhook_id) if webhook_id else uuid.uuid4(),
        "url": url,
        "secret": secret,
        "events": events or ["document.ready"],
        "collections": collections,
        "description": description,
        "active": active,
        "created_by": uuid.UUID(created_by) if created_by else None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }


def make_delivery_row(
    delivery_id: str | None = None,
    webhook_id: str | None = None,
    *,
    event: str = "document.ready",
    payload: dict | None = None,
    status: str = "delivered",
    attempts: int = 1,
    last_status_code: int | None = 200,
    last_error: str | None = None,
) -> dict:
    return {
        "id": uuid.UUID(delivery_id) if delivery_id else uuid.uuid4(),
        "webhook_id": uuid.UUID(webhook_id) if webhook_id else uuid.uuid4(),
        "event": event,
        "payload": payload or {"event": "document.ready"},
        "status": status,
        "attempts": attempts,
        "last_status_code": last_status_code,
        "last_error": last_error,
        "created_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC) if status == "delivered" else None,
    }


def _install_auth_fetchrow(mock_db: AsyncMock) -> None:
    """Wrap mock_db.fetchrow so session + API key lookups return the test user.

    Safe to call repeatedly: downstream tests that reassign
    ``mock_db.fetchrow`` or its ``side_effect`` can re-install this
    wrapper afterwards (directly, or via :func:`install_fetchrow_router`)
    and auth will keep working.
    """
    import asyncio
    import inspect

    session_hash = hash_session_token(TEST_SESSION_TOKEN)
    api_key_hash = hash_api_key(TEST_API_KEY)

    test_user = make_user_row(user_id=TEST_USER_ID)
    session_row = dict(test_user)
    api_key_row = dict(test_user)
    api_key_row["api_key_id"] = uuid.UUID(TEST_API_KEY_ID)

    original = mock_db.fetchrow.side_effect

    async def fetchrow(query: str, *args):  # type: ignore[no-untyped-def]
        if "FROM sessions" in query and args and args[0] == session_hash:
            return session_row
        if "FROM api_keys" in query and "JOIN users" in query:
            if args and args[0] == api_key_hash:
                return api_key_row
            return None

        # If a router was installed, trust it — return whatever it said,
        # even None. The test explicitly wired the response.
        if callable(original):
            result = original(query, *args)
            if inspect.isawaitable(result) or asyncio.iscoroutine(result):
                result = await result
            return result
        if original is not None:
            return original

        # No router installed — honor an explicit return_value. If the
        # caller never set one (mock's default None), special-case the
        # narrow ``SELECT COUNT(*) as cnt`` pattern so endpoints that
        # need a count to build their response don't crash under the
        # default mock wiring. Any query with a differently-named
        # aggregate (``as query_count``, ``as total``) falls through
        # and the test must wire it up explicitly.
        rv = mock_db.fetchrow.return_value
        if rv is None and "COUNT(*) as cnt" in query:
            return {"cnt": 0}
        return rv


    mock_db.fetchrow.side_effect = fetchrow


def install_fetchrow_router(mock_db: AsyncMock, router) -> None:
    """Wire ``mock_db.fetchrow`` to ``router`` *and* keep auth working.

    Use this instead of ``mock_db.fetchrow.side_effect = router`` or
    ``mock_db.fetchrow = AsyncMock(side_effect=router)`` — those drop
    the auth wrapper installed by the ``mock_db`` fixture.

    ``router`` may be a sync or async callable taking ``(query, *args)``.
    """
    # Explicit return_value=None so when the router returns None, the mock
    # doesn't fall back to a sentinel MagicMock via ``return_value``.
    mock_db.fetchrow = AsyncMock(side_effect=router, return_value=None)
    _install_auth_fetchrow(mock_db)


@pytest.fixture()
def mock_db():
    """Mock the Database singleton."""
    m = AsyncMock()
    m.connect = AsyncMock()
    m.close = AsyncMock()
    m.migrate = AsyncMock()
    m.fetchrow = AsyncMock(return_value=None)
    m.fetch = AsyncMock(return_value=[])
    m.execute = AsyncMock(return_value="DELETE 0")
    _install_auth_fetchrow(m)
    return m


@pytest.fixture()
def mock_vector_store():
    """Mock the VectorStore singleton."""
    m = MagicMock()
    m.client = True  # Truthy → readiness check passes
    m.configure = MagicMock()
    m.connect = MagicMock()
    m.close = MagicMock()
    m.create_collection = AsyncMock()
    m.delete_collection = AsyncMock()
    m.insert = AsyncMock(return_value=5)
    m.search = AsyncMock(return_value=[])
    m.get_chunks = AsyncMock(return_value=[])
    m.delete_by_document = AsyncMock()
    m.delete_by_ids = AsyncMock()
    m.text_search = AsyncMock(return_value=[])
    m.upsert = AsyncMock(return_value=3)
    return m


@pytest.fixture()
def mock_queue():
    """Mock the IngestionQueue singleton."""
    m = AsyncMock()
    m._num_workers = 2
    m._redis = AsyncMock()
    m._redis.ping = AsyncMock()
    m.connect = AsyncMock()
    m.start = AsyncMock()
    m.stop = AsyncMock()
    m.enqueue = AsyncMock()
    m.stats = {
        "queued": 10,
        "completed": 5,
        "failed": 1,
        "pending": 2,
        "processing": 1,
    }
    return m


@pytest.fixture()
def mock_storage():
    """Mock the StorageBackend."""
    m = AsyncMock()
    m.put = AsyncMock()
    m.get = AsyncMock(return_value=b"file content here")
    m.delete = AsyncMock()
    m.delete_prefix = AsyncMock(return_value=3)
    m.exists = AsyncMock(return_value=True)
    m.close = AsyncMock()
    return m


@pytest.fixture()
def mock_webhook_dispatcher():
    """Mock the WebhookDispatcher."""
    m = AsyncMock()
    m.start = AsyncMock()
    m.stop = AsyncMock()
    m.invalidate_cache = AsyncMock()
    m.deliver_test = AsyncMock(
        return_value={"status": "delivered", "status_code": 200, "error": None}
    )
    return m


@pytest.fixture()
async def client(mock_db, mock_vector_store, mock_queue, mock_storage, mock_webhook_dispatcher):
    """Async HTTP client talking to the FastAPI app with all services mocked."""

    @asynccontextmanager
    async def _test_lifespan(app):
        yield

    with contextlib.ExitStack() as stack:
        # Bypass the real lifespan
        stack.enter_context(patch("bigrag.main.lifespan", _test_lifespan))

        # Patch module-level singletons still used by routers/services
        mock_settings = MagicMock()
        stack.enter_context(patch("bigrag.database.db", mock_db))
        stack.enter_context(patch("bigrag.middleware.auth.db", mock_db))
        stack.enter_context(patch("bigrag.routers.auth.db", mock_db))
        stack.enter_context(patch("bigrag.routers.admin_users.db", mock_db))
        stack.enter_context(patch("bigrag.routers.admin_api_keys.db", mock_db))
        stack.enter_context(patch("bigrag.routers.admin_audit.db", mock_db))
        stack.enter_context(patch("bigrag.services.audit.db", mock_db))
        stack.enter_context(patch("bigrag.routers.collections.db", mock_db))
        stack.enter_context(patch("bigrag.routers.documents.db", mock_db))
        stack.enter_context(patch("bigrag.routers.webhooks.db", mock_db))
        stack.enter_context(patch("bigrag.routers.usage.db", mock_db))
        stack.enter_context(patch("bigrag.services.collection_cache.db", mock_db))
        stack.enter_context(patch("bigrag.routers.collections.vector_store", mock_vector_store))
        stack.enter_context(patch("bigrag.routers.query.vector_store", mock_vector_store))
        stack.enter_context(patch("bigrag.services.retrieval.vector_store", mock_vector_store))
        stack.enter_context(patch("bigrag.routers.documents.ingestion_queue", mock_queue))
        stack.enter_context(patch("bigrag.services.storage._storage", mock_storage))
        stack.enter_context(
            patch("bigrag.routers.webhooks.webhook_dispatcher", mock_webhook_dispatcher)
        )
        stack.enter_context(
            patch("bigrag.routers.webhooks.generate_secret", return_value="whsec_test123")
        )
        stack.enter_context(patch("bigrag.services.collection_cache.settings", mock_settings))
        stack.enter_context(patch("bigrag.middleware.auth.settings", mock_settings))
        stack.enter_context(patch("bigrag.routers.auth.settings", mock_settings))
        stack.enter_context(patch("bigrag.routers.collections.settings", mock_settings))
        stack.enter_context(patch("bigrag.routers.documents.settings", mock_settings))

        mock_settings.cors_origins = ["*"]
        mock_settings.session_cookie_name = "bigrag_session"
        mock_settings.session_cookie_secure = False
        mock_settings.session_cookie_samesite = "lax"
        mock_settings.session_cookie_domain = None
        mock_settings.session_expiry_hours = 168
        mock_settings.embedding_provider = "openai"
        mock_settings.embedding_model = "text-embedding-3-small"
        mock_settings.embedding_dimension = 1536
        mock_settings.embedding_api_key = "sk-test"
        mock_settings.max_upload_size_mb = 100
        mock_settings.collection_cache_ttl = 0
        mock_settings.log_format = "text"
        mock_settings.log_level = "info"

        from bigrag.main import create_app

        app = create_app(settings_override=mock_settings)

        # Set services on app.state for DI-based endpoints (health, stats)
        app.state.db = mock_db
        app.state.vector_store = mock_vector_store
        app.state.queue = mock_queue
        app.state.storage = mock_storage
        app.state.webhook_dispatcher = mock_webhook_dispatcher

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.cookies.set("bigrag_session", TEST_SESSION_TOKEN)
            yield ac


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """Headers with a valid API key (Bearer)."""
    return {"Authorization": f"Bearer {TEST_API_KEY}"}


@pytest.fixture()
def no_auth_headers() -> dict[str, str]:
    """Headers with no auth."""
    return {}


@pytest.fixture()
def bad_auth_headers() -> dict[str, str]:
    """Headers with an invalid Bearer token."""
    return {"Authorization": "Bearer bigrag_sk_wrong-token-nope-nope-nope-nope"}


# Backwards-compat alias for existing tests referencing TEST_API_SECRET.
TEST_API_SECRET = TEST_API_KEY

_ = timedelta  # retained for callers that import timedelta from conftest
