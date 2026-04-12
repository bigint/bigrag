"""E2E tests for bigRAG query, vector, analytics, and embedding-model endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bigrag.services.retrieval import RetrievalOutcome
from tests.conftest import make_collection_row

SAMPLE_RESULTS = [
    {
        "id": "chunk_1",
        "text": "hello world",
        "score": 0.95,
        "document_id": "doc1",
        "chunk_index": 0,
    }
]


def _outcome(results):
    """Wrap a plain result list in a RetrievalOutcome for router tests."""
    return RetrievalOutcome(
        results=results,
        embed_ms=5.0,
        search_ms=12.0,
        total_ms=20.0,
    )

SAMPLE_MULTI_RESULTS = [
    {
        "id": "chunk_1",
        "text": "hello world",
        "score": 0.95,
        "document_id": "doc1",
        "chunk_index": 0,
        "collection": "col1",
    },
    {
        "id": "chunk_2",
        "text": "foo bar",
        "score": 0.88,
        "document_id": "doc2",
        "chunk_index": 1,
        "collection": "col2",
    },
]

ANALYTICS_PERIOD_ROW = {
    "query_count": 10,
    "avg_latency_ms": 50.0,
    "avg_score": 0.85,
    "avg_result_count": 5.0,
}




@pytest.mark.asyncio
async def test_query_response_surfaces_timings_and_facets(
    client, auth_headers, mock_db
):
    mock_db.fetchrow.return_value = make_collection_row("fc")

    facet_results = [
        {
            "id": "c1",
            "text": "a",
            "score": 0.9,
            "document_id": "d1",
            "chunk_index": 0,
            "metadata": {"source": "s3"},
        },
        {
            "id": "c2",
            "text": "b",
            "score": 0.8,
            "document_id": "d2",
            "chunk_index": 0,
            "metadata": {"source": "local"},
        },
    ]
    outcome = RetrievalOutcome(
        results=facet_results,
        embed_ms=2.1,
        search_ms=8.4,
        rerank_ms=0.0,
        total_ms=11.0,
        facets={"source": {"s3": 1, "local": 1}},
    )

    with (
        patch(
            "bigrag.routers.query.get_collection_or_404",
            new_callable=AsyncMock,
            return_value=make_collection_row("fc"),
        ),
        patch("bigrag.routers.query.get_embedding_model_for", return_value=MagicMock()),
        patch(
            "bigrag.routers.query.get_reranking_config",
            return_value={"enabled": False, "model": "rerank-v3.5", "api_key": None},
        ),
        patch(
            "bigrag.routers.query.retrieve",
            new_callable=AsyncMock,
            return_value=outcome,
        ),
    ):
        resp = await client.post(
            "/v1/collections/fc/query",
            json={"query": "test", "facets": ["source"]},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["timings"]["embed_ms"] == 2.1
    assert body["timings"]["search_ms"] == 8.4
    assert body["timings"]["total_ms"] == 11.0
    assert body["facets"] == {"source": {"s3": 1, "local": 1}}


@pytest.mark.asyncio
async def test_query_result_lifts_provenance_from_metadata(
    client, auth_headers, mock_db
):
    """page_no/char_start/char_end set in chunk metadata must surface as
    first-class QueryResult fields for inline citations."""
    mock_db.fetchrow.return_value = make_collection_row("prov")

    results = [
        {
            "id": "c1",
            "text": "cite me",
            "score": 0.9,
            "document_id": "d1",
            "chunk_index": 0,
            "metadata": {"page_no": 7, "char_start": 120, "char_end": 160},
        }
    ]
    with (
        patch(
            "bigrag.routers.query.get_collection_or_404",
            new_callable=AsyncMock,
            return_value=make_collection_row("prov"),
        ),
        patch("bigrag.routers.query.get_embedding_model_for", return_value=MagicMock()),
        patch(
            "bigrag.routers.query.get_reranking_config",
            return_value={"enabled": False, "model": "rerank-v3.5", "api_key": None},
        ),
        patch(
            "bigrag.routers.query.retrieve",
            new_callable=AsyncMock,
            return_value=_outcome(results),
        ),
    ):
        resp = await client.post(
            "/v1/collections/prov/query",
            json={"query": "test"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    row = resp.json()["results"][0]
    assert row["page_no"] == 7
    assert row["char_start"] == 120
    assert row["char_end"] == 160


@pytest.mark.asyncio
async def test_query_collection(client, auth_headers, mock_db):
    mock_db.fetchrow.return_value = make_collection_row("test_col")

    with (
        patch(
            "bigrag.routers.query.get_collection_or_404",
            new_callable=AsyncMock,
            return_value=make_collection_row("test_col"),
        ),
        patch(
            "bigrag.routers.query.get_embedding_model_for",
            return_value=MagicMock(),
        ),
        patch(
            "bigrag.routers.query.get_reranking_config",
            return_value={"enabled": False, "model": "rerank-v3.5", "api_key": None},
        ),
        patch(
            "bigrag.routers.query.retrieve",
            new_callable=AsyncMock,
            return_value=_outcome(SAMPLE_RESULTS),
        ),
    ):
        resp = await client.post(
            "/v1/collections/test_col/query",
            json={"query": "test", "top_k": 5},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["collection"] == "test_col"
    assert body["query"] == "test"
    assert body["total"] == 1
    assert body["results"][0]["id"] == "chunk_1"
    assert body["results"][0]["score"] == 0.95




@pytest.mark.asyncio
async def test_multi_collection_query(client, auth_headers, mock_db):
    mock_db.fetchrow.return_value = make_collection_row("col1")

    with (
        patch(
            "bigrag.routers.query.get_collection_or_404",
            new_callable=AsyncMock,
            return_value=make_collection_row("col1"),
        ),
        patch(
            "bigrag.routers.query.get_embedding_model_for",
            return_value=MagicMock(),
        ),
        patch(
            "bigrag.routers.query.get_reranking_config",
            return_value={"enabled": False, "model": "rerank-v3.5", "api_key": None},
        ),
        patch(
            "bigrag.routers.query.retrieve_multi",
            new_callable=AsyncMock,
            return_value=SAMPLE_MULTI_RESULTS,
        ),
    ):
        resp = await client.post(
            "/v1/query",
            json={"query": "test", "collections": ["col1", "col2"]},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "test"
    assert body["collections"] == ["col1", "col2"]
    assert body["total"] == 2
    assert body["results"][0]["collection"] == "col1"




@pytest.mark.asyncio
async def test_batch_query(client, auth_headers, mock_db):
    mock_db.fetchrow.return_value = make_collection_row("test_col")

    with (
        patch(
            "bigrag.routers.query.get_collection_or_404",
            new_callable=AsyncMock,
            return_value=make_collection_row("test_col"),
        ),
        patch(
            "bigrag.routers.query.get_embedding_model_for",
            return_value=MagicMock(),
        ),
        patch(
            "bigrag.routers.query.get_reranking_config",
            return_value={"enabled": False, "model": "rerank-v3.5", "api_key": None},
        ),
        patch(
            "bigrag.routers.query.retrieve",
            new_callable=AsyncMock,
            return_value=_outcome(SAMPLE_RESULTS),
        ),
    ):
        resp = await client.post(
            "/v1/batch/query",
            json={"queries": [{"collection": "test_col", "query": "test"}]},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["collection"] == "test_col"
    assert body["results"][0]["total"] == 1
    assert body["results"][0]["results"][0]["id"] == "chunk_1"




@pytest.mark.asyncio
async def test_vector_upsert(client, auth_headers, mock_db, mock_vector_store):
    mock_db.fetchrow.return_value = make_collection_row("test_col")
    mock_vector_store.upsert.return_value = 1

    with patch(
        "bigrag.routers.query.get_collection_or_404",
        new_callable=AsyncMock,
        return_value=make_collection_row("test_col"),
    ):
        resp = await client.post(
            "/v1/collections/test_col/vectors/upsert",
            json={
                "vectors": [
                    {"id": "v1", "embedding": [0.1] * 1536, "text": "hello"},
                ]
            },
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["upserted"] == 1




@pytest.mark.asyncio
async def test_vector_delete(client, auth_headers, mock_db, mock_vector_store):
    mock_db.fetchrow.return_value = make_collection_row("test_col")

    with patch(
        "bigrag.routers.query.get_collection_or_404",
        new_callable=AsyncMock,
        return_value=make_collection_row("test_col"),
    ):
        resp = await client.post(
            "/v1/collections/test_col/vectors/delete",
            json={"ids": ["v1", "v2"]},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["deleted"] == 2




@pytest.mark.asyncio
async def test_analytics(client, auth_headers, mock_db):
    mock_db.fetchrow.return_value = ANALYTICS_PERIOD_ROW
    mock_db.fetch.return_value = [
        {"query": "what is RAG", "count": 42},
        {"query": "hello world", "count": 7},
    ]

    with patch(
        "bigrag.routers.query.get_collection_or_404",
        new_callable=AsyncMock,
        return_value=make_collection_row("test_col"),
    ):
        resp = await client.get(
            "/v1/collections/test_col/analytics",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["collection"] == "test_col"
    assert body["period_24h"]["query_count"] == 10
    assert body["period_7d"]["avg_latency_ms"] == 50.0
    assert body["period_30d"]["avg_score"] == 0.85
    assert len(body["top_queries"]) == 2
    assert body["top_queries"][0]["query"] == "what is RAG"




@pytest.mark.asyncio
async def test_list_embedding_models(client, auth_headers):
    resp = await client.get("/v1/embeddings/models", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert "models" in body
    assert len(body["models"]) > 0
    assert "provider" in body["models"][0]
    assert "model" in body["models"][0]
    assert "dimension" in body["models"][0]




@pytest.mark.asyncio
async def test_query_collection_not_found(client, auth_headers, mock_db):
    mock_db.fetchrow.return_value = None

    with patch(
        "bigrag.routers.query.get_collection_or_404",
        new_callable=AsyncMock,
        side_effect=__import__("fastapi").HTTPException(
            status_code=404, detail="Collection not found"
        ),
    ):
        resp = await client.post(
            "/v1/collections/nonexistent/query",
            json={"query": "test", "top_k": 5},
            headers=auth_headers,
        )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Collection not found"
