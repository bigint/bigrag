from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.session import get_session
from bigrag.middleware.auth import require_admin_session
from bigrag.models.connector import (
    GoogleConnectorConfigResponse,
    UpdateGoogleConnectorConfigRequest,
)
from bigrag.services import audit
from bigrag.services.google_drive import (
    get_google_config,
    google_config_public,
    upsert_google_config,
)

router = APIRouter(prefix="/v1/admin/connectors", tags=["admin:connectors"])


def _callback_url(request: Request) -> str:
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_host:
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        prefix = request.headers.get("x-forwarded-prefix", "").rstrip("/")
        return f"{proto}://{forwarded_host}{prefix}/v1/connectors/google/oauth/callback"
    return str(request.url_for("google_oauth_callback"))


@router.get("/google", response_model=GoogleConnectorConfigResponse)
async def get_google_connector_config(
    request: Request,
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> GoogleConnectorConfigResponse:
    config = await get_google_config(session)
    return GoogleConnectorConfigResponse(
        **google_config_public(config, callback_url=_callback_url(request))
    )


@router.put("/google", response_model=GoogleConnectorConfigResponse)
async def update_google_connector_config(
    body: UpdateGoogleConnectorConfigRequest,
    request: Request,
    user: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> GoogleConnectorConfigResponse:
    config = await upsert_google_config(
        session,
        enabled=body.enabled,
        client_id=body.client_id,
        client_secret=body.client_secret,
    )
    audit.record(
        request,
        user=user,
        action="connector.google_config.update",
        resource_type="connector",
        resource_id="google_drive",
        metadata={"enabled": config.enabled, "has_client_id": bool(config.client_id)},
    )
    return GoogleConnectorConfigResponse(
        **google_config_public(config, callback_url=_callback_url(request))
    )
