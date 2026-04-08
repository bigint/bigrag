"""Shared fixtures for bigRAG E2E tests.

Uses FastAPI's TestClient (httpx AsyncClient + ASGITransport) with mocked
service singletons so tests run without Postgres, Milvus, or Redis.
"""

from __future__ import annotations

import contextlib
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

TEST_API_SECRET = "test-secret-key-12345"
SAMPLE_COLLECTION_ID = str(uuid.uuid4())
SAMPLE_DOCUMENT_ID = str(uuid.uuid4())
SAMPLE_WEBHOOK_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Row factories (mimic asyncpg.Record-like dicts)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Mock services
# ---------------------------------------------------------------------------


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
    m.invalidate_cache = MagicMock()
    m.deliver_test = AsyncMock(
        return_value={"status": "delivered", "status_code": 200, "error": None}
    )
    return m


# ---------------------------------------------------------------------------
# App + client fixture
# ---------------------------------------------------------------------------


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
        stack.enter_context(patch("bigrag.routers.collections.db", mock_db))
        stack.enter_context(patch("bigrag.routers.documents.db", mock_db))
        stack.enter_context(patch("bigrag.routers.webhooks.db", mock_db))
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
        stack.enter_context(patch("bigrag.routers.collections.settings", mock_settings))
        stack.enter_context(patch("bigrag.routers.documents.settings", mock_settings))

        mock_settings.api_secret = TEST_API_SECRET
        mock_settings.cors_origins = ["*"]
        mock_settings.embedding_provider = "openai"
        mock_settings.embedding_model = "text-embedding-3-small"
        mock_settings.embedding_dimension = 1536
        mock_settings.embedding_api_key = "sk-test"
        mock_settings.max_upload_size_mb = 100
        mock_settings.collection_cache_ttl = 0
        mock_settings.log_format = "text"
        mock_settings.log_level = "info"

        # Clear the collection cache between tests
        from bigrag.services.collection_cache import _cache

        _cache.clear()

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
            yield ac


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """Headers with a valid Bearer token."""
    return {"Authorization": f"Bearer {TEST_API_SECRET}"}


@pytest.fixture()
def no_auth_headers() -> dict[str, str]:
    """Headers with no auth."""
    return {}


@pytest.fixture()
def bad_auth_headers() -> dict[str, str]:
    """Headers with an invalid Bearer token."""
    return {"Authorization": "Bearer wrong-token"}
