from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document
from bigrag.db.session import get_session
from bigrag.middleware.auth import get_current_user
from bigrag.models.document import DocumentResponse
from bigrag.routers import get_collection_or_404
from bigrag.routers._documents import document_response
from bigrag.routers.documents_progress import document_progress
from bigrag.services.documents import get_document_with_collection
from bigrag.services.vector_store import vector_store

global_router = APIRouter(prefix="/v1/documents", tags=["documents"])


def _check_document_tenant(user: dict, doc: Document, collection: dict) -> None:
    tenant_field = collection.get("tenant_field")
    if not tenant_field:
        return
    user_tenant = user.get("tenant_id")
    if user_tenant is None and user.get("role") == "admin" and not user.get("collection"):
        return
    doc_tenant = (doc.meta or {}).get(tenant_field) if doc.meta else None
    if user_tenant is None or user_tenant != doc_tenant:
        raise HTTPException(status_code=404, detail="Document not found")


@global_router.get("/{document_id}", response_model=DocumentResponse)
async def get_document_global(
    document_id: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    doc, collection_name = await get_document_with_collection(
        session, document_id, pinned_collection=user.get("collection")
    )
    collection = await get_collection_or_404(collection_name)
    _check_document_tenant(user, doc, collection)
    return document_response(doc, progress=await document_progress(doc, collection_name))


@global_router.get("/{document_id}/chunks")
async def get_document_chunks_global(
    document_id: str,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    doc, collection_name = await get_document_with_collection(
        session, document_id, pinned_collection=user.get("collection")
    )
    collection = await get_collection_or_404(collection_name)
    _check_document_tenant(user, doc, collection)
    chunks, total = await vector_store.get_chunks(
        collection_name,
        document_id,
        limit=limit,
        offset=offset,
        provider=collection.get("vector_store_provider"),
    )
    return {"chunks": chunks, "total": total}
