from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from rag_computer.db.session import get_session
from rag_computer.middleware.auth import require_admin_session
from rag_computer.models.connector import ConnectorConfigResponse, UpdateConnectorConfigRequest
from rag_computer.services import audit
from rag_computer.services.connector_registry import ConnectorRuntime, connector_runtime

router = APIRouter(prefix="/v1/admin/connectors", tags=["admin:connectors"])


def _route_or_404(provider_slug: str) -> ConnectorRuntime:
    route = connector_runtime(provider_slug)
    if route is None:
        raise HTTPException(status_code=404, detail="Connector provider not found")
    return route


def _callback_url(request: Request, route: ConnectorRuntime) -> str:
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_host:
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        prefix = request.headers.get("x-forwarded-prefix", "").rstrip("/")
        return f"{proto}://{forwarded_host}{prefix}/v1/connectors/{route.slug}/oauth/callback"
    return str(request.url_for("connector_oauth_callback", provider_slug=route.slug))


@router.get("/{provider_slug}", response_model=ConnectorConfigResponse)
async def get_connector_config(
    provider_slug: str,
    request: Request,
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> ConnectorConfigResponse:
    route = _route_or_404(provider_slug)
    config = await route.get_config(session)
    return ConnectorConfigResponse(
        **route.config_public(config, callback_url=_callback_url(request, route))
    )


@router.put("/{provider_slug}", response_model=ConnectorConfigResponse)
async def update_connector_config(
    provider_slug: str,
    body: UpdateConnectorConfigRequest,
    request: Request,
    user: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> ConnectorConfigResponse:
    route = _route_or_404(provider_slug)
    config = await route.upsert_config(
        session,
        enabled=body.enabled,
        client_id=body.client_id,
        client_secret=body.client_secret,
    )
    audit.record(
        request,
        user=user,
        action=f"connector.{route.slug}_config.update",
        resource_type="connector",
        resource_id=route.provider,
        metadata={"enabled": config.enabled, "has_client_id": bool(config.client_id)},
    )
    return ConnectorConfigResponse(
        **route.config_public(config, callback_url=_callback_url(request, route))
    )
