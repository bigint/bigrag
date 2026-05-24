from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.models.connector import (
    ConnectorSourceListResponse,
    ConnectorSourceResponse,
    ConnectorSyncJobListResponse,
    ConnectorSyncJobResponse,
)
from bigrag.services.connector_registry import ConnectorRuntime, connector_runtime
from bigrag.services.connectors.sources import list_sync_jobs


def route_or_404(provider_slug: str) -> ConnectorRuntime:
    route = connector_runtime(provider_slug)
    if route is None:
        raise HTTPException(status_code=404, detail="Connector provider not found")
    return route


async def connector_sources_payload(
    session: AsyncSession,
    *,
    provider_slug: str,
    collection: str | None,
) -> ConnectorSourceListResponse:
    route = route_or_404(provider_slug)
    sources, total = await route.list_sources(session, collection_name=collection)
    return ConnectorSourceListResponse(
        sources=[ConnectorSourceResponse(**s) for s in sources],
        total=total,
    )


async def connector_sync_jobs_payload(
    session: AsyncSession,
    *,
    provider_slug: str,
    collection: str | None,
    source_id: str | None,
    limit: int,
) -> ConnectorSyncJobListResponse:
    route = route_or_404(provider_slug)
    if source_id:
        try:
            uuid.UUID(source_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid id") from exc
    jobs, total = await list_sync_jobs(
        session,
        provider=route.provider,
        collection_name=collection,
        source_id=source_id,
        limit=limit,
    )
    return ConnectorSyncJobListResponse(
        jobs=[ConnectorSyncJobResponse(**job) for job in jobs],
        total=total,
    )
