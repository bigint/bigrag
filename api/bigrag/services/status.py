from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection, Document
from bigrag.models.status import CollectionsStatusResponse


async def collections_status_payload(session: AsyncSession) -> CollectionsStatusResponse:
    collections_total = await session.scalar(sa.select(sa.func.count()).select_from(Collection))
    documents = (
        await session.execute(
            sa.select(
                sa.func.count().label("total"),
                sa.func.coalesce(sa.func.sum(Document.chunk_count), 0).label("chunks"),
                sa.func.coalesce(sa.func.sum(Document.token_count), 0).label("tokens"),
                sa.func.coalesce(sa.func.sum(Document.file_size), 0).label("size_bytes"),
                sa.func.count().filter(Document.status == "ready").label("ready"),
                sa.func.count().filter(Document.status == "pending").label("pending"),
                sa.func.count().filter(Document.status == "processing").label("processing"),
                sa.func.count().filter(Document.status == "failed").label("failed"),
            )
        )
    ).one()

    return CollectionsStatusResponse(
        collections_total=collections_total or 0,
        documents_total=documents.total,
        documents_ready=documents.ready,
        documents_pending=documents.pending,
        documents_processing=documents.processing,
        documents_failed=documents.failed,
        total_chunks=int(documents.chunks),
        total_tokens=int(documents.tokens),
        total_size_bytes=int(documents.size_bytes),
    )
