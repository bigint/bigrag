from __future__ import annotations

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.session import get_session
from bigrag.middleware.auth import get_current_user
from bigrag.models.document import DocumentListResponse
from bigrag.routers import enforce_collection_pin
from bigrag.routers.documents._router import router
from bigrag.services.documents import list_documents_payload


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    collection_name: str,
    q: str | None = Query(default=None, max_length=200),
    status: str | None = None,
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0, le=10000),
    cursor: str | None = Query(default=None),
    include_total: bool = Query(default=False),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, collection_name)
    return await list_documents_payload(
        session,
        collection_name=collection_name,
        q=q,
        status=status,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
        cursor=cursor,
        include_total=include_total,
    )
