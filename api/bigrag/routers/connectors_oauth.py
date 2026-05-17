from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.session import get_session
from bigrag.middleware.auth import require_session
from bigrag.routers.connectors import _route_or_404
from bigrag.services.client_ip import is_trusted_proxy
from bigrag.services.connector_registry import ConnectorRuntime
from bigrag.services.error_sanitize import safe_error_detail
from bigrag.services.runtime_settings import get_value

router = APIRouter(prefix="/v1/connectors", tags=["connectors"])


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
        raise HTTPException(
            status_code=400, detail=safe_error_detail(exc, "Connector is not configured.")
        ) from exc
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
        raise HTTPException(
            status_code=400, detail=safe_error_detail(exc, "Connector is not configured.")
        ) from exc
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
