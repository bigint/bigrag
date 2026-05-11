from __future__ import annotations

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import ConnectorAccount
from bigrag.db.session import get_session
from bigrag.middleware.auth import require_session
from bigrag.models.common import StatusResponse
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
from bigrag.services.client_ip import is_trusted_proxy
from bigrag.services.connector_core import list_sync_jobs as list_connector_sync_jobs
from bigrag.services.connector_registry import ConnectorRuntime, connector_runtime
from bigrag.services.runtime_settings import get_value

router = APIRouter(prefix="/v1/connectors", tags=["connectors"])


def _route_or_404(provider_slug: str) -> ConnectorRuntime:
    route = connector_runtime(provider_slug)
    if route is None:
        raise HTTPException(status_code=404, detail="Connector provider not found")
    return route


def _redirect_uri(request: Request, route: ConnectorRuntime) -> str:
    forwarded_host = request.headers.get("x-forwarded-host")
    immediate = request.client[0] if request.client else None
    if forwarded_host and is_trusted_proxy(immediate):
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        prefix = request.headers.get("x-forwarded-prefix", "").rstrip("/")
        return f"{proto}://{forwarded_host}{prefix}/v1/connectors/{route.slug}/oauth/callback"
    return str(request.url_for("connector_oauth_callback", provider_slug=route.slug))


def _safe_redirect_path(path: str | None) -> str:
    if not path or not path.startswith("/") or path.startswith("//"):
        return "/"
    return path


async def _allowed_spa_origin(request: Request) -> str | None:
    origin = request.headers.get("origin")
    cors_origins = await get_value("cors_origins")
    if origin and origin in cors_origins:
        return origin.rstrip("/")
    return None


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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except route.auth_error as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except route.service_error as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{provider_slug}/oauth/start", response_class=RedirectResponse)
async def connector_oauth_start(
    provider_slug: str,
    request: Request,
    redirect_path: str | None = Query(default="/"),
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
):
    route = _route_or_404(provider_slug)
    try:
        auth_url = await route.build_oauth_url(
            session,
            user_id=user["id"],
            redirect_uri=_redirect_uri(request, route),
            redirect_path=_safe_redirect_path(redirect_path),
            redirect_origin=await _allowed_spa_origin(request),
        )
    except route.config_error as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(auth_url)


@router.get("/{provider_slug}/oauth/start-url", response_model=dict[str, str])
async def connector_oauth_start_url(
    provider_slug: str,
    request: Request,
    redirect_path: str | None = Query(default="/"),
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    route = _route_or_404(provider_slug)
    try:
        auth_url = await route.build_oauth_url(
            session,
            user_id=user["id"],
            redirect_uri=_redirect_uri(request, route),
            redirect_path=_safe_redirect_path(redirect_path),
            redirect_origin=await _allowed_spa_origin(request),
        )
    except route.config_error as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"auth_url": auth_url}


@router.get(
    "/{provider_slug}/oauth/callback",
    name="connector_oauth_callback",
    response_class=RedirectResponse,
)
async def connector_oauth_callback(
    provider_slug: str,
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
):
    route = _route_or_404(provider_slug)
    if error:
        redirect_url = await route.oauth_error_redirect_url(
            session,
            user_id=user["id"],
            state=state,
            path=f"/settings?tab=connectors&{route.error_query_param}={quote(error)}",
        )
        return RedirectResponse(redirect_url)
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth code or state")
    try:
        redirect_path = await route.complete_oauth(
            session,
            user_id=user["id"],
            code=code,
            state=state,
            redirect_uri=_redirect_uri(request, route),
        )
    except (route.auth_error, route.config_error) as exc:
        redirect_url = await route.oauth_error_redirect_url(
            session,
            user_id=user["id"],
            state=state,
            path=f"/settings?tab=connectors&{route.error_query_param}={quote(str(exc))}",
        )
        return RedirectResponse(redirect_url)
    return RedirectResponse(redirect_path)


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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except route.auth_error as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
        uuid_or_400(source_id)
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


def uuid_or_400(value: str):
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid id") from exc
