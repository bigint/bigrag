from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import HTTPException

from rag_computer.exceptions import ValidationError
from rag_computer.models.chat import ChatCreateRequest
from rag_computer.models.query import (
    BatchQueryItem,
    BatchQueryRequest,
    MultiQueryRequest,
    QueryRequest,
    VectorEntry,
    VectorUpsertRequest,
)
from rag_computer.routers import _documents
from rag_computer.routers import query as query_router
from rag_computer.services import chat as chat_service
from rag_computer.services.tenant_enforcement import require_tenant_filters, require_tenant_metadata


def tenant_collection() -> dict:
    return {
        "id": uuid.uuid4(),
        "name": "docs",
        "tenant_field": "tenant_id",
        "default_top_k": 10,
        "default_search_mode": "semantic",
        "default_min_score": None,
        "reranking_enabled": False,
    }


def test_tenant_metadata_is_required_for_uploads() -> None:
    with pytest.raises(ValidationError) as exc:
        require_tenant_metadata(tenant_collection(), {"source": "upload"})

    assert "metadata.tenant_id" in str(exc.value)


def test_tenant_metadata_accepts_present_value() -> None:
    require_tenant_metadata(tenant_collection(), {"tenant_id": "acme"})


def test_prepare_document_metadata_enforces_tenant_field() -> None:
    with pytest.raises(ValidationError):
        _documents.prepare_document_metadata(tenant_collection(), {})


def test_tenant_filter_is_required_for_queries() -> None:
    with pytest.raises(ValidationError) as exc:
        require_tenant_filters(tenant_collection(), {"source": "docs"})

    assert "filters.tenant_id" in str(exc.value)


def test_tenant_filter_accepts_eq_and_in() -> None:
    require_tenant_filters(tenant_collection(), {"tenant_id": {"$eq": "acme"}})
    require_tenant_filters(tenant_collection(), {"tenant_id": {"$in": ["acme"]}})


def test_query_route_rejects_missing_tenant_filter(monkeypatch) -> None:
    async def fake_get_collection_or_404(name: str) -> dict:
        return tenant_collection()

    monkeypatch.setattr(query_router, "get_collection_or_404", fake_get_collection_or_404)
    monkeypatch.setattr(query_router.access_log, "set_context", lambda *args, **kwargs: None)

    with pytest.raises(ValidationError):
        asyncio.run(
            query_router.query_collection(
                "docs",
                QueryRequest(query="find contracts"),
                object(),
                {},
            )
        )


def test_multi_query_route_rejects_missing_tenant_filter(monkeypatch) -> None:
    async def fake_get_collection_or_404(name: str) -> dict:
        return tenant_collection()

    monkeypatch.setattr(query_router, "get_collection_or_404", fake_get_collection_or_404)
    monkeypatch.setattr(query_router.access_log, "set_context", lambda *args, **kwargs: None)

    with pytest.raises(ValidationError):
        asyncio.run(
            query_router.multi_collection_query(
                MultiQueryRequest(query="find contracts", collections=["docs"]),
                object(),
                {},
            )
        )


def test_batch_query_route_rejects_missing_tenant_filter(monkeypatch) -> None:
    async def fake_get_collection_or_404(name: str) -> dict:
        return tenant_collection()

    monkeypatch.setattr(query_router, "get_collection_or_404", fake_get_collection_or_404)
    monkeypatch.setattr(query_router.access_log, "set_context", lambda *args, **kwargs: None)

    with pytest.raises(ValidationError):
        asyncio.run(
            query_router.batch_query(
                BatchQueryRequest(
                    queries=[BatchQueryItem(collection="docs", query="find contracts")]
                ),
                object(),
                {},
            )
        )


def test_vector_upsert_route_rejects_missing_tenant_metadata(monkeypatch) -> None:
    async def fake_get_collection_or_404(name: str) -> dict:
        return tenant_collection()

    async def fake_get_values(keys: list[str]) -> dict:
        return {
            "max_vector_upsert_count": 1000,
            "max_vector_text_chars": 100000,
            "max_vector_metadata_bytes": 65536,
        }

    monkeypatch.setattr(query_router, "get_collection_or_404", fake_get_collection_or_404)
    monkeypatch.setattr(query_router, "get_values", fake_get_values)
    monkeypatch.setattr(query_router.access_log, "set_context", lambda *args, **kwargs: None)

    with pytest.raises(ValidationError):
        asyncio.run(
            query_router.upsert_vectors(
                "docs",
                VectorUpsertRequest(
                    vectors=[VectorEntry(id="v1", embedding=[0.1, 0.2, 0.3], text="hello")]
                ),
                object(),
                {},
            )
        )


def test_vector_upsert_route_rejects_too_many_vectors(monkeypatch) -> None:
    async def fake_get_collection_or_404(name: str) -> dict:
        return tenant_collection()

    async def fake_get_values(keys: list[str]) -> dict:
        return {
            "max_vector_upsert_count": 1,
            "max_vector_text_chars": 100000,
            "max_vector_metadata_bytes": 65536,
        }

    monkeypatch.setattr(query_router, "get_collection_or_404", fake_get_collection_or_404)
    monkeypatch.setattr(query_router, "get_values", fake_get_values)
    monkeypatch.setattr(query_router.access_log, "set_context", lambda *args, **kwargs: None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            query_router.upsert_vectors(
                "docs",
                VectorUpsertRequest(
                    vectors=[
                        VectorEntry(
                            id="v1",
                            embedding=[0.1, 0.2, 0.3],
                            text="hello",
                            metadata={"tenant_id": "acme"},
                        ),
                        VectorEntry(
                            id="v2",
                            embedding=[0.1, 0.2, 0.3],
                            text="hello",
                            metadata={"tenant_id": "acme"},
                        ),
                    ]
                ),
                object(),
                {},
            )
        )

    assert exc.value.status_code == 413


def test_chat_turn_rejects_missing_tenant_filter(monkeypatch) -> None:
    async def fake_get_values(keys: list[str]) -> dict:
        return {
            "chat_provider": "openai",
            "chat_model": "gpt-4o-mini",
            "chat_base_url": None,
            "chat_temperature": 0.2,
            "chat_max_history_messages": 12,
            "chat_max_context_chars": 120000,
        }

    async def fake_get_collection_or_404(name: str) -> dict:
        return tenant_collection()

    class Session:
        def add(self, value: object) -> None:
            self.value = value

        async def flush(self) -> None:
            return None

    monkeypatch.setattr(chat_service, "get_values", fake_get_values)
    monkeypatch.setattr(chat_service, "get_collection_or_404", fake_get_collection_or_404)

    with pytest.raises(ValidationError):
        asyncio.run(
            chat_service._prepare_chat_turn(
                Session(),
                {"id": str(uuid.uuid4()), "collection": None},
                ChatCreateRequest(collection="docs", message="find contracts", stream=False),
            )
        )
