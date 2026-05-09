from __future__ import annotations

import asyncio

from bigrag.services import queue


def test_delete_document_vectors_after_failure_swallows_cleanup_errors(monkeypatch) -> None:
    calls = []

    class FailingVectorStore:
        async def delete_by_document(self, collection_name, document_id):
            calls.append((collection_name, document_id))
            raise RuntimeError("cleanup failed")

    asyncio.run(
        queue._delete_document_vectors_after_failure(
            FailingVectorStore(),
            "docs",
            "doc",
            prefix="job",
            log_message="failed to clean up partial vectors",
        )
    )

    assert calls == [("docs", "doc")]
