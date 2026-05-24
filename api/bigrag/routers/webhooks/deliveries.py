from __future__ import annotations

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Webhook, WebhookDelivery
from bigrag.db.session import get_session
from bigrag.middleware.auth import require_admin_session
from bigrag.models.webhook import (
    WebhookDeliveryListResponse,
    WebhookTestResponse,
)
from bigrag.routers import uuid_or_404
from bigrag.routers.webhooks._router import logger, router
from bigrag.routers.webhooks.serializers import _delivery_response, _webhook_to_dict
from bigrag.services import audit
from bigrag.services.pagination import paginate
from bigrag.services.webhook import webhook_dispatcher


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
