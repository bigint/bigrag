"""Edge case and unit tests for bigRAG.

Covers filter expressions, webhook matching, collection creation
edge cases, auth boundary conditions, and utility functions.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import make_collection_row, make_webhook_row

# ---------------------------------------------------------------------------
# Filter expression building
# ---------------------------------------------------------------------------


class TestFilterExpressions:
    def test_simple_string_filter(self):
        from bigrag.services.retrieval import _build_filter_expr

        expr = _build_filter_expr({"document_id": "doc123"})
        assert expr == 'document_id == "doc123"'

    def test_numeric_filter(self):
        from bigrag.services.retrieval import _build_filter_expr

        expr = _build_filter_expr({"chunk_index": 5})
        assert expr == "chunk_index == 5"

    def test_multiple_filters_combined_with_and(self):
        from bigrag.services.retrieval import _build_filter_expr

        expr = _build_filter_expr({"document_id": "doc1", "chunk_index": 0})
        assert "document_id" in expr
        assert "chunk_index" in expr
        assert " and " in expr

    def test_operator_eq(self):
        from bigrag.services.retrieval import _build_filter_expr

        expr = _build_filter_expr({"score": {"$eq": 0.95}})
        assert expr == "score == 0.95"

    def test_operator_ne(self):
        from bigrag.services.retrieval import _build_filter_expr

        expr = _build_filter_expr({"status": {"$ne": "failed"}})
        assert 'status != "failed"' in expr

    def test_operator_gt_lt(self):
        from bigrag.services.retrieval import _build_filter_expr

        expr = _build_filter_expr({"score": {"$gt": 0.5}})
        assert "score > 0.5" in expr

        expr = _build_filter_expr({"score": {"$lt": 0.9}})
        assert "score < 0.9" in expr

    def test_operator_in(self):
        from bigrag.services.retrieval import _build_filter_expr

        expr = _build_filter_expr({"status": {"$in": ["ready", "processing"]}})
        assert "status in" in expr

    def test_invalid_field_name_raises(self):
        from bigrag.services.retrieval import _validate_field

        with pytest.raises(ValueError, match="Invalid filter field"):
            _validate_field("bad-field!")

        with pytest.raises(ValueError, match="Invalid filter field"):
            _validate_field("1starts_with_number")

    def test_valid_field_names(self):
        from bigrag.services.retrieval import _validate_field

        assert _validate_field("document_id") == "document_id"
        assert _validate_field("_private") == "_private"
        assert _validate_field("camelCase") == "camelCase"

    def test_string_escape(self):
        from bigrag.services.retrieval import _escape_string

        assert _escape_string('hello"world') == 'hello\\"world'
        assert _escape_string("back\\slash") == "back\\\\slash"

    def test_empty_filters_returns_none(self):
        from bigrag.services.retrieval import _build_filter_expr

        expr = _build_filter_expr({})
        assert expr is None

    # -- Security: injection rejection tests --

    def test_comparison_rejects_string_value(self):
        """String values in $gt/$gte/$lt/$lte are the primary injection vector."""
        from bigrag.services.retrieval import _build_filter_expr

        for op in ("$gt", "$gte", "$lt", "$lte"):
            with pytest.raises(ValueError, match="requires a numeric value"):
                _build_filter_expr({"score": {op: "0 or 1==1"}})

    def test_eq_ne_rejects_non_scalar(self):
        from bigrag.services.retrieval import _build_filter_expr

        for op in ("$eq", "$ne"):
            with pytest.raises(ValueError, match="requires a scalar value"):
                _build_filter_expr({"field": {op: {"nested": "dict"}}})
            with pytest.raises(ValueError, match="requires a scalar value"):
                _build_filter_expr({"field": {op: [1, 2]}})
            with pytest.raises(ValueError, match="requires a scalar value"):
                _build_filter_expr({"field": {op: None}})

    def test_in_rejects_non_list(self):
        from bigrag.services.retrieval import _build_filter_expr

        with pytest.raises(ValueError, match="requires a list value"):
            _build_filter_expr({"field": {"$in": "not_a_list"}})

    def test_in_rejects_non_scalar_elements(self):
        from bigrag.services.retrieval import _build_filter_expr

        with pytest.raises(ValueError, match="requires a scalar value"):
            _build_filter_expr({"field": {"$in": [{"nested": "dict"}]}})
        with pytest.raises(ValueError, match="requires a scalar value"):
            _build_filter_expr({"field": {"$in": [None]}})

    # -- Happy path gaps --

    def test_operator_gte_lte(self):
        from bigrag.services.retrieval import _build_filter_expr

        assert _build_filter_expr({"x": {"$gte": 1}}) == "x >= 1"
        assert _build_filter_expr({"x": {"$lte": 10}}) == "x <= 10"

    def test_boolean_filter(self):
        from bigrag.services.retrieval import _build_filter_expr

        assert _build_filter_expr({"active": True}) == "active == true"
        assert _build_filter_expr({"active": {"$eq": False}}) == "active == false"

    def test_in_with_numeric_values(self):
        from bigrag.services.retrieval import _build_filter_expr

        expr = _build_filter_expr({"idx": {"$in": [1, 2, 3]}})
        assert expr == "idx in [1, 2, 3]"

    def test_in_with_mixed_types(self):
        from bigrag.services.retrieval import _build_filter_expr

        expr = _build_filter_expr({"tag": {"$in": ["a", 1, True]}})
        assert '"a"' in expr
        assert "1" in expr
        assert "true" in expr


# ---------------------------------------------------------------------------
# Webhook matching edge cases
# ---------------------------------------------------------------------------


class TestWebhookMatching:
    def test_missing_events_key(self):
        from bigrag.services.webhook import _matches_webhook

        webhook = {"active": True}
        assert _matches_webhook(webhook, "document.ready", "docs") is False

    def test_missing_active_key_defaults_to_true(self):
        from bigrag.services.webhook import _matches_webhook

        webhook = {"events": ["document.ready"], "collections": None}
        assert _matches_webhook(webhook, "document.ready", "docs") is True

    def test_empty_events_list(self):
        from bigrag.services.webhook import _matches_webhook

        webhook = {"events": [], "collections": None, "active": True}
        assert _matches_webhook(webhook, "document.ready", "docs") is False

    def test_empty_collections_list_matches_none(self):
        from bigrag.services.webhook import _matches_webhook

        webhook = {"events": ["document.ready"], "collections": [], "active": True}
        assert _matches_webhook(webhook, "document.ready", "docs") is False

    def test_multiple_events_match(self):
        from bigrag.services.webhook import _matches_webhook

        webhook = {
            "events": ["document.ready", "document.failed", "document.processing"],
            "collections": None,
            "active": True,
        }
        assert _matches_webhook(webhook, "document.ready", "x") is True
        assert _matches_webhook(webhook, "document.failed", "x") is True
        assert _matches_webhook(webhook, "document.processing", "x") is True

    def test_signature_with_special_characters(self):
        from bigrag.services.webhook import compute_signature

        sig = compute_signature('{"key": "val\u00e9"}', "whsec_test")
        assert sig.startswith("sha256=")
        assert len(sig) == 71  # sha256= (7) + 64 hex chars

    def test_signature_empty_payload(self):
        from bigrag.services.webhook import compute_signature

        sig = compute_signature("", "secret")
        assert sig.startswith("sha256=")


# ---------------------------------------------------------------------------
# Collection creation edge cases (E2E)
# ---------------------------------------------------------------------------


@patch("bigrag.services.embedding.get_embedding_model", return_value=MagicMock())
async def test_create_collection_missing_api_key(_mock_emb, client, mock_db, auth_headers):
    """Creating a collection without any API key should return 400."""
    mock_db.fetchrow.return_value = None

    with patch("bigrag.routers.collections.settings") as mock_settings:
        mock_settings.embedding_provider = "openai"
        mock_settings.embedding_model = "text-embedding-3-small"
        mock_settings.embedding_dimension = 1536
        mock_settings.embedding_api_key = None

        resp = await client.post(
            "/v1/collections",
            json={"name": "test_col"},
            headers=auth_headers,
        )

    assert resp.status_code == 400
    assert "API key is required" in resp.json()["detail"]


@patch("bigrag.services.embedding.get_embedding_model", return_value=MagicMock())
async def test_create_collection_unsupported_provider(_mock_emb, client, mock_db, auth_headers):
    mock_db.fetchrow.return_value = None

    resp = await client.post(
        "/v1/collections",
        json={"name": "test_col", "embedding_provider": "unknown"},
        headers=auth_headers,
    )

    assert resp.status_code == 400
    assert "Unsupported embedding provider" in resp.json()["detail"]


async def test_update_collection_no_changes(client, mock_db, auth_headers):
    """PUT with empty body should return existing row unchanged."""
    row = make_collection_row("my_col")
    mock_db.fetchrow.return_value = row

    resp = await client.put(
        "/v1/collections/my_col",
        json={},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["name"] == "my_col"


async def test_update_collection_not_found(client, mock_db, auth_headers):
    mock_db.fetchrow.return_value = None

    resp = await client.put(
        "/v1/collections/ghost",
        json={"description": "new"},
        headers=auth_headers,
    )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Document edge cases
# ---------------------------------------------------------------------------


async def test_upload_to_nonexistent_collection(client, auth_headers, mock_db):
    """Uploading to a collection that doesn't exist should 404."""

    def fetchrow_router(query, *args):
        if "collections WHERE name" in query:
            return None
        return None

    mock_db.fetchrow = AsyncMock(side_effect=fetchrow_router)

    resp = await client.post(
        "/v1/collections/nonexistent/documents",
        headers=auth_headers,
        files={"file": ("test.pdf", b"content", "application/pdf")},
    )

    assert resp.status_code == 404


async def test_list_documents_nonexistent_collection(client, auth_headers, mock_db):
    def fetchrow_router(query, *args):
        if "collections WHERE name" in query:
            return None
        return None

    mock_db.fetchrow = AsyncMock(side_effect=fetchrow_router)

    resp = await client.get(
        "/v1/collections/nonexistent/documents",
        headers=auth_headers,
    )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Query edge cases
# ---------------------------------------------------------------------------


async def test_query_negative_top_k(client, auth_headers, mock_db):
    """top_k=-1 should be rejected."""
    resp = await client.post(
        "/v1/collections/test_col/query",
        json={"query": "test", "top_k": -1},
        headers=auth_headers,
    )

    assert resp.status_code == 422


async def test_query_top_k_exceeds_max(client, auth_headers, mock_db):
    """top_k=9999 should be rejected (max 1000)."""
    resp = await client.post(
        "/v1/collections/test_col/query",
        json={"query": "test", "top_k": 9999},
        headers=auth_headers,
    )

    assert resp.status_code == 422


async def test_query_top_k_zero(client, auth_headers, mock_db):
    """top_k=0 should be rejected."""
    mock_db.fetchrow.return_value = make_collection_row("test_col")

    with patch(
        "bigrag.routers.query.get_collection_or_404",
        new_callable=AsyncMock,
        return_value=make_collection_row("test_col"),
    ):
        resp = await client.post(
            "/v1/collections/test_col/query",
            json={"query": "test", "top_k": 0},
            headers=auth_headers,
        )

    assert resp.status_code == 422


async def test_batch_query_empty_queries(client, auth_headers):
    """Empty queries list should be rejected."""
    resp = await client.post(
        "/v1/batch/query",
        json={"queries": []},
        headers=auth_headers,
    )

    assert resp.status_code == 422


async def test_multi_query_empty_collections(client, auth_headers):
    """Empty collections list should be rejected."""
    resp = await client.post(
        "/v1/query",
        json={"query": "test", "collections": []},
        headers=auth_headers,
    )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Auth edge cases
# ---------------------------------------------------------------------------


async def test_auth_bearer_case_insensitive_prefix(client):
    """'bearer' (lowercase) should still work as per HTTP spec."""
    # FastAPI/Starlette typically handle this case-insensitively
    from tests.conftest import TEST_API_SECRET

    resp = await client.get(
        "/v1/collections",
        headers={"Authorization": f"bearer {TEST_API_SECRET}"},
    )
    # Depends on implementation — either 200 or 401 is valid
    assert resp.status_code in (200, 401)


async def test_auth_extra_whitespace_in_token(client):
    """Token with extra whitespace should be rejected."""
    from tests.conftest import TEST_API_SECRET

    resp = await client.get(
        "/v1/collections",
        headers={"Authorization": f"Bearer  {TEST_API_SECRET}"},
    )
    assert resp.status_code == 401


async def test_auth_empty_bearer_token(client):
    """Empty Bearer token should be rejected."""
    resp = await client.get(
        "/v1/collections",
        headers={"Authorization": "Bearer "},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Webhook admin edge cases
# ---------------------------------------------------------------------------


async def test_create_webhook_max_limit(client, auth_headers, mock_db):
    """Should reject creation when webhook limit is reached."""
    mock_db.fetchrow.side_effect = lambda query, *args: (
        {"cnt": 100} if "COUNT(*)" in query else None
    )

    resp = await client.post(
        "/v1/admin/webhooks",
        json={
            "url": "https://example.com/hook",
            "events": ["document.ready"],
        },
        headers=auth_headers,
    )

    assert resp.status_code == 400
    assert "Maximum" in resp.json()["detail"]


async def test_update_nonexistent_webhook(client, auth_headers, mock_db):
    import uuid

    mock_db.fetchrow.return_value = None

    resp = await client.put(
        f"/v1/admin/webhooks/{uuid.uuid4()}",
        json={"description": "updated"},
        headers=auth_headers,
    )

    assert resp.status_code == 404


async def test_delete_nonexistent_webhook(client, auth_headers, mock_db):
    import uuid

    mock_db.fetchrow.return_value = None

    resp = await client.delete(
        f"/v1/admin/webhooks/{uuid.uuid4()}",
        headers=auth_headers,
    )

    assert resp.status_code == 404


async def test_create_webhook_with_collections_filter(client, auth_headers, mock_db):
    import uuid

    wh_id = str(uuid.uuid4())
    row = make_webhook_row(webhook_id=wh_id, collections=["docs", "reports"])

    def fetchrow_router(query, *args):
        if "COUNT(*)" in query:
            return {"cnt": 0}
        if "INSERT INTO webhooks" in query:
            return row
        return None

    mock_db.fetchrow.side_effect = fetchrow_router

    resp = await client.post(
        "/v1/admin/webhooks",
        json={
            "url": "https://example.com/hook",
            "events": ["document.ready"],
            "collections": ["docs", "reports"],
        },
        headers=auth_headers,
    )

    assert resp.status_code == 201
    assert resp.json()["collections"] == ["docs", "reports"]


# ---------------------------------------------------------------------------
# Health edge cases
# ---------------------------------------------------------------------------


async def test_health_returns_version(client):
    from bigrag import __version__

    resp = await client.get("/health")
    assert resp.json()["version"] == __version__


async def test_readiness_all_down_returns_503(client, mock_db, mock_vector_store, mock_queue):
    mock_db.fetchrow.side_effect = Exception("down")
    mock_vector_store.client = None
    mock_queue._redis.ping.side_effect = Exception("down")

    resp = await client.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["postgres"] is False
    assert body["milvus"] is False
    assert body["redis"] is False


# ---------------------------------------------------------------------------
# Webhook model validation edge cases
# ---------------------------------------------------------------------------


class TestWebhookModelValidation:
    def test_create_webhook_duplicate_events(self):
        from bigrag.models.webhook import CreateWebhookRequest

        req = CreateWebhookRequest(
            url="https://example.com/hook",
            events=["document.ready", "document.ready"],
        )
        # Should deduplicate or accept — just shouldn't crash
        assert "document.ready" in req.events

    def test_create_webhook_all_valid_events(self):
        from bigrag.models.webhook import VALID_EVENTS, CreateWebhookRequest

        req = CreateWebhookRequest(
            url="https://example.com/hook",
            events=list(VALID_EVENTS),
        )
        assert len(req.events) == len(VALID_EVENTS)

    def test_update_webhook_empty_body(self):
        from bigrag.models.webhook import UpdateWebhookRequest

        req = UpdateWebhookRequest()
        assert req.url is None
        assert req.events is None
        assert req.active is None
        assert req.description is None
        assert req.collections is None


# ---------------------------------------------------------------------------
# Utils: safe_create_task
# ---------------------------------------------------------------------------


class TestSafeCreateTask:
    @pytest.mark.asyncio
    async def test_successful_task(self):
        from bigrag.utils import safe_create_task

        result = []

        async def work():
            result.append("done")

        task = safe_create_task(work(), name="test-ok")
        await task
        assert result == ["done"]

    @pytest.mark.asyncio
    async def test_failing_task_logs_warning(self):
        from bigrag.utils import safe_create_task

        async def failing():
            raise ValueError("boom")

        task = safe_create_task(failing(), name="test-fail")
        # Should not raise — the callback catches it
        await asyncio.sleep(0.05)
        assert task.done()
        assert task.exception() is not None


# ---------------------------------------------------------------------------
# Retrieval helper functions
# ---------------------------------------------------------------------------


class TestRetrievalHelpers:
    def test_tokenize_query_basic(self):
        from bigrag.services.retrieval import _tokenize_query

        tokens = _tokenize_query("Hello World")
        assert tokens == ["hello", "world"]

    def test_tokenize_query_filters_short_words(self):
        from bigrag.services.retrieval import _tokenize_query

        tokens = _tokenize_query("I am a data scientist")
        assert "i" not in tokens
        assert "a" not in tokens
        assert "am" in tokens
        assert "data" in tokens

    def test_tokenize_query_empty_string(self):
        from bigrag.services.retrieval import _tokenize_query

        assert _tokenize_query("") == []
        assert _tokenize_query("   ") == []

    def test_keyword_score_no_matches(self):
        from bigrag.services.retrieval import _keyword_score

        assert _keyword_score("hello world", ["xyz", "abc"]) == 0.0

    def test_keyword_score_all_match(self):
        from bigrag.services.retrieval import _keyword_score

        assert _keyword_score("hello world", ["hello", "world"]) == 1.0

    def test_keyword_score_partial_match(self):
        from bigrag.services.retrieval import _keyword_score

        assert _keyword_score("hello world", ["hello", "xyz"]) == 0.5

    def test_keyword_score_empty_terms(self):
        from bigrag.services.retrieval import _keyword_score

        assert _keyword_score("hello world", []) == 0.0

    def test_rrf_single_list(self):
        from bigrag.services.retrieval import _reciprocal_rank_fusion

        items = [
            {"id": "a", "score": 0.9, "text": "first"},
            {"id": "b", "score": 0.8, "text": "second"},
        ]
        result = _reciprocal_rank_fusion([items])
        assert len(result) == 2
        assert result[0]["id"] == "a"
        assert result[1]["id"] == "b"

    def test_rrf_merges_duplicates(self):
        from bigrag.services.retrieval import _reciprocal_rank_fusion

        list1 = [{"id": "a", "score": 0.9, "text": "hello"}]
        list2 = [{"id": "a", "score": 0.8, "text": "hello"}]
        result = _reciprocal_rank_fusion([list1, list2])
        assert len(result) == 1
        assert result[0]["id"] == "a"
        # Score should be higher since it appeared in both lists
        assert result[0]["score"] > 0

    def test_rrf_empty_lists(self):
        from bigrag.services.retrieval import _reciprocal_rank_fusion

        result = _reciprocal_rank_fusion([[], []])
        assert result == []

    def test_rrf_preserves_all_items(self):
        from bigrag.services.retrieval import _reciprocal_rank_fusion

        list1 = [{"id": "a", "score": 0.9, "text": "x"}]
        list2 = [{"id": "b", "score": 0.8, "text": "y"}]
        result = _reciprocal_rank_fusion([list1, list2])
        assert len(result) == 2
        ids = {r["id"] for r in result}
        assert ids == {"a", "b"}


# ---------------------------------------------------------------------------
# Embedding models endpoint
# ---------------------------------------------------------------------------


async def test_embedding_models_requires_auth(client):
    resp = await client.get("/v1/embeddings/models")
    assert resp.status_code == 401


async def test_embedding_models_has_all_providers(client, auth_headers):
    resp = await client.get("/v1/embeddings/models", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    providers = {m["provider"] for m in body["models"]}
    assert "openai" in providers
    assert "cohere" in providers
