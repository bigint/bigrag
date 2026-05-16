from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection, Document
from bigrag.db.session import get_session
from bigrag.middleware.auth import require_admin_session
from bigrag.services.vector_store import vector_store

router = APIRouter(prefix="/v1/admin/vector-storage", tags=["admin:vector-storage"])


@router.get("/overview", response_model=dict[str, object])
async def vector_storage_overview(
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    provider_health = await vector_store.provider_health()
    rows = (
        await session.execute(
            sa.select(
                Collection.name,
                Collection.vector_store_provider,
                sa.func.count(Document.id).label("documents"),
                sa.func.coalesce(sa.func.sum(Document.chunk_count), 0).label("chunks"),
                sa.func.coalesce(sa.func.sum(Document.file_size), 0).label("bytes"),
            )
            .outerjoin(Document, Document.collection_id == Collection.id)
            .group_by(Collection.id)
            .order_by(Collection.name.asc())
        )
    ).all()
    collections = [
        {
            "name": name,
            "provider": provider,
            "documents": int(documents or 0),
            "chunks": int(chunks or 0),
            "bytes": int(bytes_ or 0),
        }
        for name, provider, documents, chunks, bytes_ in rows
    ]
    totals = {
        "collections": len(collections),
        "documents": sum(item["documents"] for item in collections),
        "chunks": sum(item["chunks"] for item in collections),
        "bytes": sum(item["bytes"] for item in collections),
    }
    return {
        "fallback_provider": vector_store.provider,
        "configured_providers": list(vector_store.configured_providers),
        "provider_health": provider_health,
        "collections": collections,
        "totals": totals,
    }
