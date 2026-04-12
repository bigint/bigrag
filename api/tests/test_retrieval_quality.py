"""Unit tests for retrieval-quality helpers: MMR, fusion strategies, facets."""

from __future__ import annotations

from bigrag.services.retrieval import (
    compute_facets,
    fuse_results,
    mmr_rerank,
)


class TestMMR:
    def test_lambda_1_is_pure_relevance(self):
        """lambda=1.0 must be identical to input order (no reranking)."""
        query = [1.0, 0.0]
        docs = [
            {"id": "a", "score": 0.9, "embedding": [1.0, 0.0]},
            {"id": "b", "score": 0.8, "embedding": [0.9, 0.1]},
            {"id": "c", "score": 0.7, "embedding": [0.0, 1.0]},
        ]
        picked = mmr_rerank(docs, query_embedding=query, lambda_=1.0, top_k=3)
        assert [d["id"] for d in picked] == ["a", "b", "c"]

    def test_low_lambda_picks_diverse(self):
        """With lambda=0.3, after picking 'a' the next pick should be
        'c' (orthogonal) not 'b' (near-duplicate of 'a')."""
        query = [1.0, 0.0]
        docs = [
            {"id": "a", "score": 0.9, "embedding": [1.0, 0.0]},
            {"id": "b", "score": 0.85, "embedding": [0.99, 0.01]},
            {"id": "c", "score": 0.5, "embedding": [0.0, 1.0]},
        ]
        picked = mmr_rerank(docs, query_embedding=query, lambda_=0.3, top_k=2)
        assert picked[0]["id"] == "a"
        assert picked[1]["id"] == "c", (
            f"expected 'c' (diverse) over 'b' (near-dup), got {picked[1]['id']}"
        )

    def test_missing_embedding_doesnt_crash(self):
        query = [1.0, 0.0]
        docs = [
            {"id": "a", "score": 0.9},  # no embedding
            {"id": "b", "score": 0.8, "embedding": [0.9, 0.1]},
        ]
        picked = mmr_rerank(docs, query_embedding=query, lambda_=0.5, top_k=2)
        assert len(picked) == 2

    def test_top_k_larger_than_pool(self):
        query = [1.0, 0.0]
        docs = [{"id": "a", "score": 0.9, "embedding": [1.0, 0.0]}]
        picked = mmr_rerank(docs, query_embedding=query, lambda_=0.5, top_k=5)
        assert len(picked) == 1


class TestFusion:
    def test_rrf_sums_reciprocal_ranks(self):
        a = [{"id": "x", "score": 10}, {"id": "y", "score": 9}]
        b = [{"id": "y", "score": 0.8}, {"id": "z", "score": 0.5}]
        out = fuse_results([a, b], strategy="rrf")
        # y appears in both lists → highest fused score
        assert out[0]["id"] == "y"

    def test_weighted_normalizes_before_combining(self):
        # Two lists on very different score scales. The item that
        # appears in both lists with mid-rank should still beat
        # singletons from either list.
        a = [
            {"id": "x", "score": 100},
            {"id": "y", "score": 60},
            {"id": "q", "score": 30},
        ]
        b = [
            {"id": "z", "score": 1.0},
            {"id": "y", "score": 0.6},
            {"id": "w", "score": 0.2},
        ]
        out = fuse_results([a, b], strategy="weighted")
        # y appears in both lists and should rank ahead of q (only in a, bottom)
        # and w (only in b, bottom).
        ids = [r["id"] for r in out]
        assert ids.index("y") < ids.index("q")
        assert ids.index("y") < ids.index("w")

    def test_normalized_rrf_still_a_valid_ranking(self):
        a = [{"id": "x", "score": 10}, {"id": "y", "score": 1}]
        b = [{"id": "y", "score": 1}, {"id": "z", "score": 0.1}]
        out = fuse_results([a, b], strategy="normalized")
        # y appears in both → top
        assert out[0]["id"] == "y"


class TestFacets:
    def test_counts_by_metadata_field(self):
        results = [
            {"metadata": {"source": "s3", "topic": "ml"}},
            {"metadata": {"source": "s3", "topic": "db"}},
            {"metadata": {"source": "local", "topic": "ml"}},
        ]
        out = compute_facets(results, ["source", "topic"])
        assert out["source"] == {"s3": 2, "local": 1}
        assert out["topic"] == {"ml": 2, "db": 1}

    def test_missing_field_skipped(self):
        results = [
            {"metadata": {"topic": "ml"}},
            {"metadata": {}},  # no topic
            {"metadata": {"topic": "db"}},
        ]
        out = compute_facets(results, ["topic"])
        assert out["topic"] == {"ml": 1, "db": 1}

    def test_empty_fields_returns_empty_dict_per_field(self):
        out = compute_facets([{"metadata": {}}], ["x", "y"])
        assert out == {"x": {}, "y": {}}

    def test_non_scalar_coerced_to_str(self):
        results = [{"metadata": {"tags": ["a", "b"]}}]
        out = compute_facets(results, ["tags"])
        # Coerced via str() — the exact key isn't important, but it
        # must be a single bucket, not a crash.
        assert len(out["tags"]) == 1
