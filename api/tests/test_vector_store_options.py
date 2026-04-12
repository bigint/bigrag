"""Tests for HNSW index option and partition-per-tenant."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bigrag.services.vector_store import VectorStore


@pytest.fixture
def store_with_mock_client():
    vs = VectorStore()
    client = MagicMock()
    client.has_collection.return_value = False
    client.has_partition.return_value = False
    schema = MagicMock()
    client.create_schema.return_value = schema

    class _IndexParams:
        def __init__(self):
            self.calls = []

        def add_index(self, **kwargs):
            self.calls.append(kwargs)

    client.prepare_index_params.side_effect = lambda: _IndexParams()
    vs.client = client
    return vs


@pytest.mark.asyncio
async def test_create_collection_defaults_to_ivf_flat(store_with_mock_client):
    captured = {}

    def capture_create(**kwargs):
        captured.update(kwargs)
        return None

    store_with_mock_client.client.create_collection.side_effect = capture_create

    await store_with_mock_client.create_collection("fresh", 384)
    idx_params = captured["index_params"]
    assert idx_params.calls[0]["index_type"] == "IVF_FLAT"
    assert idx_params.calls[0]["metric_type"] == "COSINE"


@pytest.mark.asyncio
async def test_create_collection_respects_hnsw(store_with_mock_client):
    captured = {}

    def capture_create(**kwargs):
        captured.update(kwargs)
        return None

    store_with_mock_client.client.create_collection.side_effect = capture_create

    await store_with_mock_client.create_collection("big", 1024, index_type="HNSW")
    idx_params = captured["index_params"]
    assert idx_params.calls[0]["index_type"] == "HNSW"
    assert idx_params.calls[0]["params"]["M"] == 16


@pytest.mark.asyncio
async def test_ensure_partition_creates_when_missing(store_with_mock_client):
    await store_with_mock_client.ensure_partition("coll", "tenant-42")
    store_with_mock_client.client.create_partition.assert_called_once()
    kwargs = store_with_mock_client.client.create_partition.call_args.kwargs
    assert kwargs["partition_name"] == "tenant_42"  # unsafe chars sanitised


@pytest.mark.asyncio
async def test_ensure_partition_skips_when_present(store_with_mock_client):
    store_with_mock_client.client.has_partition.return_value = True
    await store_with_mock_client.ensure_partition("coll", "abc")
    store_with_mock_client.client.create_partition.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_partition_empty_name_is_noop(store_with_mock_client):
    await store_with_mock_client.ensure_partition("coll", "")
    store_with_mock_client.client.create_partition.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_partition_tolerates_failure(store_with_mock_client):
    # Milvus blowing up on create_partition must not bubble up — the
    # worker should keep processing the batch, just without the
    # optimization.
    store_with_mock_client.client.has_partition.side_effect = RuntimeError(
        "milvus down"
    )
    await store_with_mock_client.ensure_partition("coll", "t1")  # no raise
