"""Tests for chunk strategy, content-hash dedup, and the plumbing of
chunk offsets into citation metadata."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bigrag.services.ingestion import Chunk, chunk_document
from tests.conftest import (
    install_fetchrow_router,
    make_collection_row,
    make_document_row,
)


class TestChunkStrategies:
    def test_paragraph_keeps_paragraph_boundaries(self):
        text = "First para.\n\nSecond para.\n\nThird para."
        chunks = chunk_document(text, chunk_size=40, chunk_overlap=0)
        assert len(chunks) >= 1
        joined = "".join(c.text for c in chunks)
        assert "First" in joined and "Third" in joined

    def test_recursive_respects_size_ceiling(self):
        text = "aaaa " * 500  # 2500 chars
        chunks = chunk_document(text, chunk_size=200, chunk_overlap=0, strategy="recursive")
        assert all(len(c.text) <= 250 for c in chunks), (
            "recursive chunker must respect chunk_size with reasonable tolerance"
        )
        assert len(chunks) > 5

    def test_offsets_point_into_source(self):
        text = "Header section.\n\nBody paragraph goes here."
        chunks = chunk_document(text, chunk_size=80, chunk_overlap=0)
        for c in chunks:
            assert c.char_start >= 0
            assert c.char_end >= c.char_start
            # The sub-slice should contain the chunk's first word, so
            # citations point somewhere useful.
            slice_text = text[c.char_start : c.char_end]
            assert slice_text.split()[0] == c.text.split()[0]

    def test_empty_text_returns_no_chunks(self):
        assert chunk_document("", 100, 0) == []
        assert chunk_document("   \n\n  ", 100, 0) == []

    def test_recursive_splits_on_double_newline_first(self):
        # Paragraphs are each larger than chunk_size so the first
        # separator (\n\n) must split them.
        paragraph = "x" * 30
        text = f"{paragraph}\n\n{paragraph}\n\n{paragraph}"
        chunks = chunk_document(text, chunk_size=40, chunk_overlap=0, strategy="recursive")
        assert len(chunks) == 3


@patch("bigrag.services.embedding.get_embedding_model", return_value=MagicMock())
async def test_upload_dedup_returns_existing_doc(_mock_emb, client, mock_db, auth_headers):
    """Uploading the same bytes twice must return the existing doc
    without creating a second row or re-running ingestion."""
    content = b"%PDF-1.4\nhello identical file"
    content_hash = hashlib.sha256(content).hexdigest()
    col = make_collection_row("dedup_col")
    existing = make_document_row(
        collection_id=str(col["id"]),
        content_hash=content_hash,
    )

    def router(query, *args):
        if "FROM collections WHERE name" in query:
            return col
        if "FROM documents" in query and "content_hash" in query:
            return existing
        if "INSERT INTO documents" in query:
            # Sanity check: should not be reached when deduped
            pytest.fail("Upload path must not INSERT when a duplicate exists")
        return None

    install_fetchrow_router(mock_db, router)

    with patch("bigrag.routers.documents.get_embedding_model_for", return_value=MagicMock()):
        resp = await client.post(
            "/v1/collections/dedup_col/documents",
            headers=auth_headers,
            files={"file": ("doc.pdf", content, "application/pdf")},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["deduped"] is True
    assert body["filename"] == existing["filename"]


@patch("bigrag.services.embedding.get_embedding_model", return_value=MagicMock())
async def test_upload_new_bytes_still_ingests(
    _mock_emb, client, mock_db, mock_storage, mock_queue, auth_headers
):
    col = make_collection_row("fresh_col")
    new_doc = make_document_row(collection_id=str(col["id"]))

    def router(query, *args):
        if "FROM collections WHERE name" in query:
            return col
        if "FROM documents" in query and "content_hash" in query:
            return None  # no dupe
        if "INSERT INTO documents" in query:
            return new_doc
        return None

    install_fetchrow_router(mock_db, router)

    with patch("bigrag.routers.documents.get_embedding_model_for", return_value=MagicMock()):
        resp = await client.post(
            "/v1/collections/fresh_col/documents",
            headers=auth_headers,
            files={"file": ("doc.pdf", b"%PDF-1.4\nunique", "application/pdf")},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body.get("deduped") is not True
    mock_queue.enqueue.assert_awaited_once()


def test_ingestion_job_carries_chunk_strategy():
    from bigrag.services.ingestion_job import create_ingestion_job

    collection = make_collection_row(
        "strategic",
        chunk_strategy="recursive",
    )
    job = create_ingestion_job(
        document_id="d1",
        file_path="p.pdf",
        collection_name="strategic",
        collection=collection,
        fallback_api_key="sk-test",
    )
    assert job.chunk_strategy == "recursive"
    # Round-trip via serialize/deserialize preserves it.
    from bigrag.services.ingestion_job import IngestionJob

    restored = IngestionJob.deserialize(job.serialize())
    assert restored.chunk_strategy == "recursive"


def test_ingestion_job_deserialise_ignores_unknown_keys():
    """Old queue entries from before a new field was added must still
    deserialise cleanly — the unknown-key ignore is what makes rolling
    deploys safe."""
    import orjson

    from bigrag.services.ingestion_job import IngestionJob

    blob = orjson.dumps(
        {
            "document_id": "d1",
            "file_path": "p",
            "collection_name": "c",
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimension": 1536,
            "embedding_api_key": "sk-x",
            "chunk_size": 512,
            "chunk_overlap": 50,
            "legacy_field_we_dont_know": 123,
        }
    )
    job = IngestionJob.deserialize(blob)
    assert job.document_id == "d1"
    assert job.chunk_strategy == "paragraph"  # default
