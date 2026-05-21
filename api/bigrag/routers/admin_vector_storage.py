from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection, Document
from bigrag.db.session import get_session
from bigrag.middleware.auth import require_admin_session
from bigrag.services.health import categorize_dependency_error
from bigrag.services.vector_store import vector_store

router = APIRouter(prefix="/v1/admin/vector-storage", tags=["admin:vector-storage"])


@router.get("/overview", response_model=dict[str, object])
async def vector_storage_overview(
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    health: dict[str, object] = {"status": "ok", "error": None}
    try:
        await vector_store.health_check()
    except Exception as exc:
        health = {"status": "error", "error": categorize_dependency_error(exc)}
    rows = (
        await session.execute(
            sa.select(
                Collection.name,
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
            "documents": int(documents or 0),
            "chunks": int(chunks or 0),
            "bytes": int(bytes_ or 0),
        }
        for name, documents, chunks, bytes_ in rows
    ]
    totals = {
        "collections": len(collections),
        "documents": sum(item["documents"] for item in collections),
        "chunks": sum(item["chunks"] for item in collections),
        "bytes": sum(item["bytes"] for item in collections),
    }
    return {
        "provider": "turbopuffer",
        "health": health,
        "collections": collections,
        "totals": totals,
    }
