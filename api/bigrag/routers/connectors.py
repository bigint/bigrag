from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import ConnectorAccount
from bigrag.db.session import get_session
from bigrag.middleware.auth import require_session
from bigrag.models import StatusResponse
from bigrag.models.connector import (
    ConnectorAccountResponse,
    ConnectorFileListResponse,
    ConnectorFileResponse,
    ConnectorSourceListResponse,
    ConnectorSourceResponse,
    ConnectorSyncJobListResponse,
    ConnectorSyncJobResponse,
    CreateConnectorSourceRequest,
    UpdateConnectorSourceRequest,
)
from bigrag.services import audit
from bigrag.services.connector_core import list_sync_jobs as list_connector_sync_jobs
from bigrag.services.connector_registry import ConnectorRuntime, connector_runtime
from bigrag.services.error_sanitize import safe_error_detail

router = APIRouter(prefix="/v1/connectors", tags=["connectors"])


def _route_or_404(provider_slug: str) -> ConnectorRuntime:
    route = connector_runtime(provider_slug)
    if route is None:
        raise HTTPException(status_code=404, detail="Connector provider not found")
    return route


@router.get("/{provider_slug}/account", response_model=ConnectorAccountResponse)
async def connector_account(
    provider_slug: str,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> ConnectorAccountResponse:
    route = _route_or_404(provider_slug)
    config = await route.get_config(session)
    account = await route.get_account(session, user["id"])
    return ConnectorAccountResponse(**route.account_public(config=config, account=account))


@router.get("/{provider_slug}/files", response_model=ConnectorFileListResponse)
async def connector_files(
    provider_slug: str,
    parent_id: str = Query(default="root", min_length=1, max_length=500),
    query: str | None = Query(default=None, max_length=200),
    page_token: str | None = Query(default=None, max_length=1000),
    page_size: int = Query(default=100, ge=1, le=100),
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> ConnectorFileListResponse:
    route = _route_or_404(provider_slug)
    try:
        data = await route.list_files(
            session,
            user_id=user["id"],
            parent_id=parent_id,
            query=query,
            page_token=page_token,
            page_size=page_size,
        )
        return ConnectorFileListResponse(
            provider=data["provider"],
            parent_id=data["parent_id"],
            query=data["query"],
            files=[ConnectorFileResponse(**item) for item in data["files"]],
            next_page_token=data["next_page_token"],
        )
    except route.config_error as exc:
        raise HTTPException(
            status_code=400, detail=safe_error_detail(exc, "Connector is not configured.")
        ) from exc
    except route.auth_error as exc:
        raise HTTPException(
            status_code=401, detail=safe_error_detail(exc, "Connector authentication failed.")
        ) from exc
    except route.service_error as exc:
        raise HTTPException(
            status_code=502, detail=safe_error_detail(exc, "Connector upstream error.")
        ) from exc


@router.post("/{provider_slug}/disconnect", response_model=StatusResponse)
async def connector_disconnect(
    provider_slug: str,
    request: Request,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    route = _route_or_404(provider_slug)
    await route.disconnect_account(session, user_id=user["id"])
    audit.record(
        request,
        user=user,
        action=f"connector.{route.slug}.disconnect",
        resource_type="connector",
        resource_id=route.provider,
        metadata={},
    )
    return StatusResponse(status="ok", message=f"{route.display_name} disconnected")


@router.get("/{provider_slug}/sources", response_model=ConnectorSourceListResponse)
async def connector_sources(
    provider_slug: str,
    collection: str | None = Query(default=None, max_length=120),
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> ConnectorSourceListResponse:
    route = _route_or_404(provider_slug)
    sources, total = await route.list_sources(
        session,
        user_id=user["id"],
        collection_name=collection,
    )
    return ConnectorSourceListResponse(
        sources=[ConnectorSourceResponse(**s) for s in sources],
        total=total,
    )


@router.post("/{provider_slug}/sources", response_model=ConnectorSourceResponse, status_code=201)
async def connector_source_create(
    provider_slug: str,
    body: CreateConnectorSourceRequest,
    request: Request,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> ConnectorSourceResponse:
    route = _route_or_404(provider_slug)
    try:
        source, job = await route.create_source(
            session,
            user_id=user["id"],
            collection_name=body.collection_name,
            root_id=body.root_id,
            root_name=body.root_name,
            root_mime_type=body.root_mime_type,
            source_type=body.source_type,
            metadata=body.metadata,
        )
    except route.config_error as exc:
        raise HTTPException(
            status_code=400, detail=safe_error_detail(exc, "Connector is not configured.")
        ) from exc
    except route.auth_error as exc:
        raise HTTPException(
            status_code=401, detail=safe_error_detail(exc, "Connector authentication failed.")
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail=safe_error_detail(exc, "Connector source not found.")
        ) from exc
    account = await session.get(ConnectorAccount, source.account_id)
    audit.record(
        request,
        user=user,
        action=f"connector.{route.slug}_source.create",
        resource_type="connector_source",
        resource_id=str(source.id),
        metadata={
            "collection": source.collection_name,
            "root_id": source.root_id,
            "source_type": source.source_type,
            "sync_job_id": str(job.id),
        },
    )
    return ConnectorSourceResponse(**route.source_public((source, account)))


@router.patch("/{provider_slug}/sources/{source_id}", response_model=ConnectorSourceResponse)
async def connector_source_update(
    provider_slug: str,
    source_id: str,
    body: UpdateConnectorSourceRequest,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> ConnectorSourceResponse:
    route = _route_or_404(provider_slug)
    try:
        source = await route.update_source(
            session,
            user_id=user["id"],
            source_id=source_id,
            schedule_enabled=body.schedule_enabled,
            sync_interval_hours=body.sync_interval_hours,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail=safe_error_detail(exc, "Connector source not found.")
        ) from exc
    account = await session.get(ConnectorAccount, source.account_id)
    return ConnectorSourceResponse(**route.source_public((source, account)))


@router.delete("/{provider_slug}/sources/{source_id}", response_model=StatusResponse)
async def connector_source_delete(
    provider_slug: str,
    source_id: str,
    request: Request,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    route = _route_or_404(provider_slug)
    try:
        await route.delete_source(session, user_id=user["id"], source_id=source_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail=safe_error_detail(exc, "Connector source not found.")
        ) from exc
    audit.record(
        request,
        user=user,
        action=f"connector.{route.slug}_source.delete",
        resource_type="connector_source",
        resource_id=source_id,
        metadata={},
    )
    return StatusResponse(status="ok", message=f"{route.display_name} source removed")


@router.post("/{provider_slug}/sources/{source_id}/sync", response_model=ConnectorSyncJobResponse)
async def connector_source_sync(
    provider_slug: str,
    source_id: str,
    request: Request,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> ConnectorSyncJobResponse:
    route = _route_or_404(provider_slug)
    try:
        job = await route.trigger_sync(
            session,
            user_id=user["id"],
            source_id=source_id,
            trigger="manual",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail=safe_error_detail(exc, "Connector source not found.")
        ) from exc
    audit.record(
        request,
        user=user,
        action=f"connector.{route.slug}_source.sync",
        resource_type="connector_sync_job",
        resource_id=str(job.id),
        metadata={"source_id": source_id},
    )
    return ConnectorSyncJobResponse(**route.sync_job_public(job))


@router.get("/{provider_slug}/sync-jobs", response_model=ConnectorSyncJobListResponse)
async def connector_sync_jobs(
    provider_slug: str,
    collection: str | None = Query(default=None, max_length=120),
    source_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> ConnectorSyncJobListResponse:
    route = _route_or_404(provider_slug)
    if source_id:
        try:
            uuid.UUID(source_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid id") from exc
    jobs, total = await list_connector_sync_jobs(
        session,
        provider=route.provider,
        user_id=user["id"],
        collection_name=collection,
        source_id=source_id,
        limit=limit,
    )
    return ConnectorSyncJobListResponse(
        jobs=[ConnectorSyncJobResponse(**job) for job in jobs],
        total=total,
    )
