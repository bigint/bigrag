from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.session import get_session
from bigrag.middleware.auth import require_admin_session
from bigrag.models import StatusResponse
from bigrag.models.connector import (
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


@router.get("/{provider_slug}/sources", response_model=ConnectorSourceListResponse)
async def connector_sources(
    provider_slug: str,
    collection: str | None = Query(default=None, max_length=120),
    user: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> ConnectorSourceListResponse:
    _ = user
    route = _route_or_404(provider_slug)
    sources, total = await route.list_sources(
        session,
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
    user: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> ConnectorSourceResponse:
    route = _route_or_404(provider_slug)
    try:
        source, job = await route.create_source(
            session,
            user_id=user["id"],
            collection_name=body.collection_name,
            bucket=body.bucket,
            prefix=body.prefix,
            region=body.region,
            endpoint_url=body.endpoint_url,
            force_path_style=body.force_path_style,
            access_key_id=body.access_key_id,
            secret_access_key=body.secret_access_key,
            session_token=body.session_token,
            schedule_enabled=body.schedule_enabled,
            sync_interval_hours=body.sync_interval_hours,
            metadata=body.metadata,
        )
    except route.service_error as exc:
        raise HTTPException(
            status_code=400, detail=safe_error_detail(exc, "Connector source could not be created.")
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=safe_error_detail(exc, "Connector source could not be created.")
        ) from exc
    audit.record(
        request,
        user=user,
        action=f"connector.{route.slug}_source.create",
        resource_type="connector_source",
        resource_id=str(source.id),
        metadata={
            "collection": source.collection_name,
            "root_id": source.root_id,
            "sync_job_id": str(job.id),
        },
    )
    return ConnectorSourceResponse(**route.source_public(source))


@router.patch("/{provider_slug}/sources/{source_id}", response_model=ConnectorSourceResponse)
async def connector_source_update(
    provider_slug: str,
    source_id: str,
    body: UpdateConnectorSourceRequest,
    user: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> ConnectorSourceResponse:
    route = _route_or_404(provider_slug)
    try:
        source = await route.update_source(
            session,
            source_id=source_id,
            bucket=body.bucket,
            prefix=body.prefix,
            region=body.region,
            endpoint_url=body.endpoint_url,
            endpoint_url_set="endpoint_url" in body.model_fields_set,
            force_path_style=body.force_path_style,
            access_key_id=body.access_key_id,
            secret_access_key=body.secret_access_key,
            session_token=body.session_token,
            session_token_set="session_token" in body.model_fields_set,
            schedule_enabled=body.schedule_enabled,
            sync_interval_hours=body.sync_interval_hours,
            metadata=body.metadata,
        )
    except route.service_error as exc:
        raise HTTPException(
            status_code=400, detail=safe_error_detail(exc, "Connector source could not be updated.")
        ) from exc
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(
            status_code=status_code, detail=safe_error_detail(exc, "Connector source not found.")
        ) from exc
    _ = user
    return ConnectorSourceResponse(**route.source_public(source))


@router.delete("/{provider_slug}/sources/{source_id}", response_model=StatusResponse)
async def connector_source_delete(
    provider_slug: str,
    source_id: str,
    request: Request,
    user: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    route = _route_or_404(provider_slug)
    try:
        await route.delete_source(session, source_id=source_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(
            status_code=status_code, detail=safe_error_detail(exc, "Connector source not found.")
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
    user: dict = Depends(require_admin_session),
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
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(
            status_code=status_code, detail=safe_error_detail(exc, "Connector source not found.")
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
    user: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> ConnectorSyncJobListResponse:
    _ = user
    route = _route_or_404(provider_slug)
    if source_id:
        try:
            uuid.UUID(source_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid id") from exc
    jobs, total = await list_connector_sync_jobs(
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
