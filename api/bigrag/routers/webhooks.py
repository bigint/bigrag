from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Webhook, WebhookDelivery
from bigrag.db.session import get_session
from bigrag.ids import uuid7
from bigrag.logging import get_logger
from bigrag.middleware.auth import require_admin_session
from bigrag.models import StatusResponse
from bigrag.models.webhook import (
    CreateWebhookRequest,
    CreateWebhookResponse,
    UpdateWebhookRequest,
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
    WebhookListResponse,
    WebhookResponse,
    WebhookTestResponse,
)
from bigrag.routers import uuid_or_404
from bigrag.services import audit
from bigrag.services.error_sanitize import safe_error_detail
from bigrag.services.pagination import paginate
from bigrag.services.runtime_settings import get_value
from bigrag.services.url_security import validate_webhook_url
from bigrag.services.webhook import generate_secret, webhook_dispatcher
from bigrag.services.webhook.dispatcher import invalidate_webhooks_cache

logger = get_logger("bigrag.routers.webhooks")

router = APIRouter(prefix="/v1/admin/webhooks", tags=["webhooks"])


async def _validate_webhook_target(url: str) -> None:
    try:
        await validate_webhook_url(url)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=safe_error_detail(exc, "Webhook URL rejected.")
        ) from exc


def _webhook_response(wh: Webhook) -> WebhookResponse:
    return WebhookResponse(
        id=str(wh.id),
        url=wh.url,
        events=list(wh.events),
        collections=list(wh.collections) if wh.collections else None,
        active=wh.active,
        created_by=str(wh.created_by) if wh.created_by else None,
        created_at=wh.created_at,
        updated_at=wh.updated_at,
    )


def _webhook_to_dict(wh: Webhook) -> dict:
    return {
        "id": wh.id,
        "url": wh.url,
        "secret": wh.secret,
        "events": list(wh.events),
        "collections": list(wh.collections) if wh.collections else None,
        "active": wh.active,
        "created_by": wh.created_by,
        "created_at": wh.created_at,
        "updated_at": wh.updated_at,
    }


def _delivery_response(d: WebhookDelivery) -> WebhookDeliveryResponse:
    return WebhookDeliveryResponse(
        id=str(d.id),
        webhook_id=str(d.webhook_id),
        event=d.event,
        payload=d.payload,
        status=d.status,
        attempts=d.attempts,
        last_status_code=d.last_status_code,
        last_error=d.last_error,
        created_at=d.created_at,
        completed_at=d.completed_at,
    )


@router.post("", response_model=CreateWebhookResponse, status_code=201)
async def create_webhook(
    body: CreateWebhookRequest,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
):
    count = await session.scalar(sa.select(sa.func.count()).select_from(Webhook))
    max_count = await get_value("webhook_max_count")
    if (count or 0) >= max_count:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum of {max_count} webhooks reached",
        )
    await _validate_webhook_target(body.url)

    secret = generate_secret()
    wh = Webhook(
        id=uuid7(),
        url=body.url,
        secret=secret,
        events=body.events,
        collections=body.collections,
        created_by=uuid.UUID(admin["id"]) if admin.get("id") else None,
    )
    session.add(wh)
    await session.commit()
    await session.refresh(wh)
    invalidate_webhooks_cache()

    logger.info("webhook created", id=str(wh.id), url=body.url, events=body.events)
    audit.record(
        request,
        user=admin,
        action="webhook.create",
        resource_type="webhook",
        resource_id=str(wh.id),
        metadata={"url": wh.url, "events": list(wh.events)},
    )

    base = _webhook_response(wh)
    return CreateWebhookResponse(**base.model_dump(), secret=secret)


@router.get("", response_model=WebhookListResponse)
async def list_webhooks(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = Query(default=None),
    include_total: bool = Query(default=False),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
):
    stmt = sa.select(Webhook).order_by(Webhook.created_at.desc(), Webhook.id.desc())
    result = await paginate(
        session,
        stmt,
        created_col=Webhook.created_at,
        id_col=Webhook.id,
        cursor=cursor,
        limit=limit,
        offset=offset,
        count_stmt=(sa.select(sa.func.count()).select_from(Webhook) if include_total else None),
    )
    return WebhookListResponse(
        webhooks=[_webhook_response(w) for w in result.rows],
        total=result.total,
        next_cursor=result.next_cursor,
    )


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
):
    wh = await session.get(Webhook, uuid_or_404(webhook_id, "Webhook"))
    if wh is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return _webhook_response(wh)


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    body: UpdateWebhookRequest,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
):
    wh = await session.get(Webhook, uuid_or_404(webhook_id, "Webhook"))
    if wh is None:
        raise HTTPException(status_code=404, detail="Webhook not found")

    fields: list[str] = []
    if body.url is not None:
        await _validate_webhook_target(body.url)
        wh.url = body.url
        fields.append("url")
    if body.events is not None:
        wh.events = body.events
        fields.append("events")
    if body.collections is not None:
        wh.collections = body.collections
        fields.append("collections")
    if body.active is not None:
        wh.active = body.active
        fields.append("active")

    await session.commit()
    await session.refresh(wh)
    invalidate_webhooks_cache()

    logger.info("webhook updated", id=webhook_id)
    audit.record(
        request,
        user=admin,
        action="webhook.update",
        resource_type="webhook",
        resource_id=str(wh.id),
        metadata={"url": wh.url, "fields": fields},
    )
    return _webhook_response(wh)


@router.delete("/{webhook_id}", response_model=StatusResponse)
async def delete_webhook(
    webhook_id: str,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
):
    wh = await session.get(Webhook, uuid_or_404(webhook_id, "Webhook"))
    if wh is None:
        raise HTTPException(status_code=404, detail="Webhook not found")

    deleted_url = wh.url
    await session.delete(wh)
    await session.commit()
    invalidate_webhooks_cache()
    logger.info("webhook deleted", id=webhook_id)
    audit.record(
        request,
        user=admin,
        action="webhook.delete",
        resource_type="webhook",
        resource_id=webhook_id,
        metadata={"url": deleted_url},
    )
    return StatusResponse(status="ok", message="Webhook deleted")


@router.get("/{webhook_id}/deliveries", response_model=WebhookDeliveryListResponse)
async def list_deliveries(
    webhook_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = Query(default=None),
    include_total: bool = Query(default=False),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
):
    wh_uuid = uuid_or_404(webhook_id, "Webhook")
    wh_exists = await session.scalar(sa.select(Webhook.id).where(Webhook.id == wh_uuid))
    if wh_exists is None:
        raise HTTPException(status_code=404, detail="Webhook not found")

    stmt = (
        sa.select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == wh_uuid)
        .order_by(WebhookDelivery.created_at.desc(), WebhookDelivery.id.desc())
    )
    result = await paginate(
        session,
        stmt,
        created_col=WebhookDelivery.created_at,
        id_col=WebhookDelivery.id,
        cursor=cursor,
        limit=limit,
        offset=offset,
        count_stmt=(
            sa.select(sa.func.count())
            .select_from(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == wh_uuid)
            if include_total
            else None
        ),
    )
    return WebhookDeliveryListResponse(
        deliveries=[_delivery_response(d) for d in result.rows],
        total=result.total,
        next_cursor=result.next_cursor,
    )


@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(
    webhook_id: str,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
):
    wh = await session.get(Webhook, uuid_or_404(webhook_id, "Webhook"))
    if wh is None:
        raise HTTPException(status_code=404, detail="Webhook not found")

    result = await webhook_dispatcher.deliver_test(_webhook_to_dict(wh))
    audit.record(
        request,
        user=admin,
        action="webhook.test",
        resource_type="webhook",
        resource_id=webhook_id,
        metadata={"url": wh.url, "status": result.get("status")},
    )
    return WebhookTestResponse(**result)


@router.post(
    "/{webhook_id}/deliveries/{delivery_id}/replay",
    response_model=WebhookTestResponse,
)
async def replay_delivery(
    webhook_id: str,
    delivery_id: str,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> WebhookTestResponse:

    wh_uuid = uuid_or_404(webhook_id, "Webhook")
    del_uuid = uuid_or_404(delivery_id, "Delivery")

    wh = await session.get(Webhook, wh_uuid)
    if wh is None:
        raise HTTPException(status_code=404, detail="Webhook not found")

    delivery = await session.scalar(
        sa.select(WebhookDelivery)
        .where(WebhookDelivery.id == del_uuid)
        .where(WebhookDelivery.webhook_id == wh_uuid)
    )
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")

    from datetime import UTC, datetime

    import orjson

    payload_dict = (
        dict(delivery.payload) if isinstance(delivery.payload, dict) else delivery.payload
    )
    if isinstance(payload_dict, dict):
        payload_dict["timestamp"] = datetime.now(UTC).isoformat()
    payload_str = orjson.dumps(payload_dict).decode()
    result = await webhook_dispatcher.deliver_once(
        _webhook_to_dict(wh),
        delivery.event,
        payload_str,
        delivery_id=str(delivery.id),
    )
    logger.info(
        "Webhook delivery replayed",
        webhook_id=webhook_id,
        delivery_id=delivery_id,
        status=result["status"],
    )
    audit.record(
        request,
        user=admin,
        action="webhook.replay",
        resource_type="webhook",
        resource_id=webhook_id,
        metadata={
            "delivery_id": delivery_id,
            "event": delivery.event,
            "status": result.get("status"),
        },
    )
    return WebhookTestResponse(**result)
