"""Tests for BYO endpoint, persistent cache, token truncation, and
/v1/usage."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bigrag.services import embedding_cache
from bigrag.services.embedding import (
    OpenAIEmbedding,
    count_tokens,
    get_embedding_model,
    truncate_to_tokens,
)
from tests.conftest import install_fetchrow_router


class TestTokenTruncation:
    def test_short_text_not_truncated(self):
        out, warn = truncate_to_tokens(["hello world"], model="text-embedding-3-small")
        assert out == ["hello world"]
        assert warn == [False]

    def test_long_text_is_truncated(self):
        very_long = "word " * 20000  # ~20k tokens
        out, warn = truncate_to_tokens([very_long], model="text-embedding-3-small")
        assert warn == [True]
        assert len(out[0]) < len(very_long)

    def test_mixed_inputs_get_per_item_warnings(self):
        long_ = "x" * 200_000
        texts = ["ok", long_, "also ok"]
        out, warn = truncate_to_tokens(texts, model="text-embedding-3-small")
        assert warn[0] is False
        assert warn[1] is True
        assert warn[2] is False

    def test_count_tokens_returns_sane_estimate(self):
        # Char-based fallback guarantees ≥1 and roughly len/4.
        assert count_tokens("") >= 1
        assert count_tokens("a" * 400) >= 50


class TestBYOEndpoint:
    def test_openai_compatible_provider_accepted(self):
        with patch("openai.AsyncOpenAI") as mock_client:
            model = get_embedding_model(
                provider="openai_compatible",
                model_name="bge-small",
                dimension=384,
                api_key=None,
                base_url="http://localhost:11434/v1",
            )
            assert isinstance(model, OpenAIEmbedding)
            assert model.dimension == 384
            assert model.name == "bge-small"
            # Client constructed with the base_url
            assert mock_client.called
            args, kwargs = mock_client.call_args
            assert kwargs.get("base_url") == "http://localhost:11434/v1"

    def test_different_base_urls_cache_distinctly(self):
        # The in-process model cache must scope by (provider, model, key, base_url)
        # so a local Ollama and a hosted OpenAI pointing at the same model don't share
        # a client.
        with patch("openai.AsyncOpenAI"):
            a = get_embedding_model(
                provider="openai_compatible",
                model_name="same",
                dimension=384,
                api_key="k",
                base_url="http://a/v1",
            )
            b = get_embedding_model(
                provider="openai_compatible",
                model_name="same",
                dimension=384,
                api_key="k",
                base_url="http://b/v1",
            )
            assert a is not b


class TestEmbeddingCache:
    @pytest.mark.asyncio
    async def test_get_many_returns_hit_indices(self):
        # Mock db.fetch to return 1 of 2 hits.
        import struct

        vec = [0.1, 0.2, 0.3]
        blob = struct.pack("<3f", *vec)
        import hashlib

        hashes = [hashlib.sha256(t.encode()).hexdigest() for t in ["hit", "miss"]]

        async def fake_fetch(sql, *args):
            return [{"content_hash": hashes[0], "vector": blob}]

        async def fake_execute(*args, **kwargs):
            return "UPDATE 1"

        with (
            patch("bigrag.services.embedding_cache.db.fetch", side_effect=fake_fetch),
            patch("bigrag.services.embedding_cache.db.execute", side_effect=fake_execute),
        ):
            out = await embedding_cache.get_many(
                ["hit", "miss"], "openai", "text-embedding-3-small", 3
            )
        assert 0 in out
        assert 1 not in out
        # Close enough (float32 round-trip).
        assert [round(x, 5) for x in out[0]] == [round(x, 5) for x in vec]

    @pytest.mark.asyncio
    async def test_put_many_upserts_on_conflict(self):
        calls = []

        async def fake_executemany(sql, rows):
            calls.append((sql, rows))

        with patch(
            "bigrag.services.embedding_cache.db.executemany",
            side_effect=fake_executemany,
        ):
            await embedding_cache.put_many(
                ["a", "b"],
                [[0.1, 0.2], [0.3, 0.4]],
                "openai",
                "text-embedding-3-small",
                2,
            )
        assert len(calls) == 1
        sql, rows = calls[0]
        assert "ON CONFLICT" in sql
        assert len(rows) == 2


class TestUsageEndpoint:
    @pytest.mark.asyncio
    async def test_usage_aggregates_per_collection(self, client, mock_db, auth_headers):
        # Two collections with different embedding volumes.
        per_collection = [
            {
                "collection_id": "c1",
                "collection": "col_a",
                "embedding_model": "text-embedding-3-small",
                "storage_bytes": 10_000,
                "chunks": 20,
                "documents": 2,
                "embedding_tokens": 1_000_000,  # 1M tokens → $0.02
            },
            {
                "collection_id": "c2",
                "collection": "col_b",
                "embedding_model": "embed-english-v3.0",
                "storage_bytes": 5_000,
                "chunks": 10,
                "documents": 1,
                "embedding_tokens": 500_000,  # 0.5M → $0.05
            },
        ]
        query_counts = [
            {"collection_name": "col_a", "cnt": 12, "avg_latency": 42.0},
        ]

        async def fake_fetch(sql, *args):
            if "FROM collections c" in sql:
                return per_collection
            if "FROM query_log" in sql:
                return query_counts
            return []

        mock_db.fetch = AsyncMock(side_effect=fake_fetch)
        install_fetchrow_router(mock_db, lambda q, *a: None)

        resp = await client.get("/v1/usage", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["queries_total"] == 12
        assert body["documents_total"] == 3
        assert body["chunks_total"] == 30
        assert body["storage_bytes_total"] == 15_000
        # 1M * 0.02 + 0.5M * 0.10 = 0.02 + 0.05 = 0.07
        assert body["embedding_cost_usd_estimate"] == pytest.approx(0.07, rel=0.01)
        assert len(body["by_collection"]) == 2
