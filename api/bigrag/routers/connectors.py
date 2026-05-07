from __future__ import annotations

import uuid
from urllib.parse import quote

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import ConnectorAccount, ConnectorSource, ConnectorSyncJob
from bigrag.db.session import get_session
from bigrag.middleware.auth import require_session
from bigrag.models.common import StatusResponse
from bigrag.models.connector import (
    CreateGoogleSourceRequest,
    GoogleAccountResponse,
    GoogleDriveFileListResponse,
    GoogleDriveFileResponse,
    GoogleSourceListResponse,
    GoogleSourceResponse,
    GoogleSyncJobListResponse,
    GoogleSyncJobResponse,
    UpdateGoogleSourceRequest,
)
from bigrag.services import audit
from bigrag.services.google_drive import (
    GOOGLE_PROVIDER,
    GoogleDriveAuthError,
    GoogleDriveConfigError,
    GoogleDriveError,
    build_google_oauth_url,
    complete_google_oauth,
    create_google_source,
    delete_google_source,
    disconnect_google_account,
    get_google_account,
    get_google_config,
    google_account_public,
    google_oauth_error_redirect_url,
    google_source_public,
    google_sync_job_public,
    list_google_drive_files,
    list_google_sources,
    trigger_google_sync,
    update_google_source,
)
from bigrag.services.runtime_settings import get_value

router = APIRouter(prefix="/v1/connectors/google", tags=["connectors:google"])


def _redirect_uri(request: Request) -> str:
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_host:
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        prefix = request.headers.get("x-forwarded-prefix", "").rstrip("/")
        return f"{proto}://{forwarded_host}{prefix}/v1/connectors/google/oauth/callback"
    return str(request.url_for("google_oauth_callback"))


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


@router.get("/account", response_model=GoogleAccountResponse)
async def google_account(
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> GoogleAccountResponse:
    config = await get_google_config(session)
    account = await get_google_account(session, user["id"])
    return GoogleAccountResponse(**google_account_public(config=config, account=account))


@router.get("/files", response_model=GoogleDriveFileListResponse)
async def google_files(
    parent_id: str = Query(default="root", min_length=1, max_length=500),
    query: str | None = Query(default=None, max_length=200),
    page_token: str | None = Query(default=None, max_length=1000),
    page_size: int = Query(default=100, ge=1, le=100),
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> GoogleDriveFileListResponse:
    try:
        data = await list_google_drive_files(
            session,
            user_id=user["id"],
            parent_id=parent_id,
            query=query,
            page_token=page_token,
            page_size=page_size,
        )
        return GoogleDriveFileListResponse(
            provider=data["provider"],
            parent_id=data["parent_id"],
            query=data["query"],
            files=[GoogleDriveFileResponse(**item) for item in data["files"]],
            next_page_token=data["next_page_token"],
        )
    except GoogleDriveConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GoogleDriveAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except GoogleDriveError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/oauth/start")
async def google_oauth_start(
    request: Request,
    redirect_path: str | None = Query(default="/"),
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
):
    try:
        auth_url = await build_google_oauth_url(
            session,
            user_id=user["id"],
            redirect_uri=_redirect_uri(request),
            redirect_path=_safe_redirect_path(redirect_path),
            redirect_origin=await _allowed_spa_origin(request),
        )
    except GoogleDriveConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(auth_url)


@router.get("/oauth/start-url")
async def google_oauth_start_url(
    request: Request,
    redirect_path: str | None = Query(default="/"),
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    try:
        auth_url = await build_google_oauth_url(
            session,
            user_id=user["id"],
            redirect_uri=_redirect_uri(request),
            redirect_path=_safe_redirect_path(redirect_path),
            redirect_origin=await _allowed_spa_origin(request),
        )
    except GoogleDriveConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"auth_url": auth_url}


@router.get("/oauth/callback", name="google_oauth_callback")
async def google_oauth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
):
    if error:
        redirect_url = await google_oauth_error_redirect_url(
            session,
            user_id=user["id"],
            state=state,
            path=f"/settings?tab=connectors&google_error={quote(error)}",
        )
        return RedirectResponse(redirect_url)
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing Google OAuth code or state")
    try:
        redirect_path = await complete_google_oauth(
            session,
            user_id=user["id"],
            code=code,
            state=state,
            redirect_uri=_redirect_uri(request),
        )
    except (GoogleDriveAuthError, GoogleDriveConfigError) as exc:
        redirect_url = await google_oauth_error_redirect_url(
            session,
            user_id=user["id"],
            state=state,
            path=f"/settings?tab=connectors&google_error={quote(str(exc))}",
        )
        return RedirectResponse(redirect_url)
    return RedirectResponse(redirect_path)


@router.post("/disconnect", response_model=StatusResponse)
async def google_disconnect(
    request: Request,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    await disconnect_google_account(session, user_id=user["id"])
    audit.record(
        request,
        user=user,
        action="connector.google.disconnect",
        resource_type="connector",
        resource_id="google_drive",
        metadata={},
    )
    return StatusResponse(status="ok", message="Google Drive disconnected")


@router.get("/sources", response_model=GoogleSourceListResponse)
async def google_sources(
    collection: str | None = Query(default=None, max_length=120),
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> GoogleSourceListResponse:
    sources, total = await list_google_sources(
        session,
        user_id=user["id"],
        collection_name=collection,
    )
    return GoogleSourceListResponse(
        sources=[GoogleSourceResponse(**s) for s in sources],
        total=total,
    )


@router.post("/sources", response_model=GoogleSourceResponse, status_code=201)
async def google_source_create(
    body: CreateGoogleSourceRequest,
    request: Request,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> GoogleSourceResponse:
    try:
        source, job = await create_google_source(
            session,
            user_id=user["id"],
            collection_name=body.collection_name,
            root_id=body.root_id,
            root_name=body.root_name,
            root_mime_type=body.root_mime_type,
            source_type=body.source_type,
            metadata=body.metadata,
        )
    except GoogleDriveConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GoogleDriveAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    account = await session.get(ConnectorAccount, source.account_id)
    audit.record(
        request,
        user=user,
        action="connector.google_source.create",
        resource_type="connector_source",
        resource_id=str(source.id),
        metadata={
            "collection": source.collection_name,
            "root_id": source.root_id,
            "source_type": source.source_type,
            "sync_job_id": str(job.id),
        },
    )
    return GoogleSourceResponse(**google_source_public((source, account)))


@router.patch("/sources/{source_id}", response_model=GoogleSourceResponse)
async def google_source_update(
    source_id: str,
    body: UpdateGoogleSourceRequest,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> GoogleSourceResponse:
    try:
        source = await update_google_source(
            session,
            user_id=user["id"],
            source_id=source_id,
            schedule_enabled=body.schedule_enabled,
            sync_interval_hours=body.sync_interval_hours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    account = await session.get(ConnectorAccount, source.account_id)
    return GoogleSourceResponse(**google_source_public((source, account)))


@router.delete("/sources/{source_id}", response_model=StatusResponse)
async def google_source_delete(
    source_id: str,
    request: Request,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    try:
        await delete_google_source(session, user_id=user["id"], source_id=source_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit.record(
        request,
        user=user,
        action="connector.google_source.delete",
        resource_type="connector_source",
        resource_id=source_id,
        metadata={},
    )
    return StatusResponse(status="ok", message="Google Drive source removed")


@router.post("/sources/{source_id}/sync", response_model=GoogleSyncJobResponse)
async def google_source_sync(
    source_id: str,
    request: Request,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> GoogleSyncJobResponse:
    try:
        job = await trigger_google_sync(
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
        action="connector.google_source.sync",
        resource_type="connector_sync_job",
        resource_id=str(job.id),
        metadata={"source_id": source_id},
    )
    return GoogleSyncJobResponse(**google_sync_job_public(job))


@router.get("/sync-jobs", response_model=GoogleSyncJobListResponse)
async def google_sync_jobs(
    source_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> GoogleSyncJobListResponse:
    stmt = (
        sa.select(ConnectorSyncJob)
        .join(ConnectorSource, ConnectorSource.id == ConnectorSyncJob.source_id)
        .join(ConnectorAccount, ConnectorAccount.id == ConnectorSource.account_id)
        .where(ConnectorAccount.user_id == uuid.UUID(user["id"]))
        .where(ConnectorSyncJob.provider == GOOGLE_PROVIDER)
        .order_by(ConnectorSyncJob.created_at.desc())
        .limit(limit)
    )
    count_stmt = (
        sa.select(sa.func.count())
        .select_from(ConnectorSyncJob)
        .join(ConnectorSource, ConnectorSource.id == ConnectorSyncJob.source_id)
        .join(ConnectorAccount, ConnectorAccount.id == ConnectorSource.account_id)
        .where(ConnectorAccount.user_id == uuid.UUID(user["id"]))
        .where(ConnectorSyncJob.provider == GOOGLE_PROVIDER)
    )
    if source_id:
        sid = uuid_or_400(source_id)
        stmt = stmt.where(ConnectorSyncJob.source_id == sid)
        count_stmt = count_stmt.where(ConnectorSyncJob.source_id == sid)
    rows = (await session.scalars(stmt)).all()
    total = await session.scalar(count_stmt)
    return GoogleSyncJobListResponse(
        jobs=[GoogleSyncJobResponse(**google_sync_job_public(job)) for job in rows],
        total=total or 0,
    )


def uuid_or_400(value: str):
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid id") from exc
