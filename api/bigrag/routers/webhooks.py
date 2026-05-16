from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Webhook, WebhookDelivery
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import require_admin_session
from bigrag.models.common import StatusResponse
from bigrag.models.webhook import (
    CreateWebhookRequest,
    CreateWebhookResponse,
    UpdateWebhookRequest,
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
    WebhookListResponse,
    WebhookResponse,
    WebhookTestResponse,
    resolve_and_validate_url,
)
from bigrag.services import audit
from bigrag.services.runtime_settings import get_value
from bigrag.services.webhook import generate_secret, webhook_dispatcher

logger = get_logger("bigrag.routers.webhooks")

router = APIRouter(prefix="/v1/admin/webhooks", tags=["webhooks"])


def _webhook_uuid_or_404(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Webhook not found") from exc


def _delivery_uuid_or_404(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Delivery not found") from exc


async def _validate_webhook_target(url: str) -> None:
    try:
        await resolve_and_validate_url(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _webhook_response(wh: Webhook) -> WebhookResponse:
    return WebhookResponse(
        id=str(wh.id),
        url=wh.url,
        events=list(wh.events),
        collections=list(wh.collections) if wh.collections else None,
        description=wh.description,
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
        "description": wh.description,
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
        id=uuid.uuid4(),
        url=body.url,
        secret=secret,
        events=body.events,
        collections=body.collections,
        description=body.description,
        created_by=uuid.UUID(admin["id"]) if admin.get("id") else None,
    )
    session.add(wh)
    await session.commit()
    await session.refresh(wh)

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
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
):
    total = await session.scalar(sa.select(sa.func.count()).select_from(Webhook))
    webhooks = (
        await session.scalars(
            sa.select(Webhook).order_by(Webhook.created_at.desc()).limit(limit).offset(offset)
        )
    ).all()
    return WebhookListResponse(webhooks=[_webhook_response(w) for w in webhooks], total=total or 0)


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
):
    wh = await session.get(Webhook, _webhook_uuid_or_404(webhook_id))
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
    wh = await session.get(Webhook, _webhook_uuid_or_404(webhook_id))
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
    if body.description is not None:
        wh.description = body.description
        fields.append("description")
    if body.active is not None:
        wh.active = body.active
        fields.append("active")

    await session.commit()
    await session.refresh(wh)

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
    wh = await session.get(Webhook, _webhook_uuid_or_404(webhook_id))
    if wh is None:
        raise HTTPException(status_code=404, detail="Webhook not found")

    deleted_url = wh.url
    await session.delete(wh)
    await session.commit()
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
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
):
    wh_uuid = _webhook_uuid_or_404(webhook_id)
    wh_exists = await session.scalar(sa.select(Webhook.id).where(Webhook.id == wh_uuid))
    if wh_exists is None:
        raise HTTPException(status_code=404, detail="Webhook not found")

    deliveries = (
        await session.scalars(
            sa.select(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == wh_uuid)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    total = await session.scalar(
        sa.select(sa.func.count())
        .select_from(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == wh_uuid)
    )
    return WebhookDeliveryListResponse(
        deliveries=[_delivery_response(d) for d in deliveries],
        total=total or 0,
    )


@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(
    webhook_id: str,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
):
    wh = await session.get(Webhook, _webhook_uuid_or_404(webhook_id))
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

    wh_uuid = _webhook_uuid_or_404(webhook_id)
    del_uuid = _delivery_uuid_or_404(delivery_id)

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

    import orjson

    payload_str = orjson.dumps(delivery.payload).decode()
    result = await webhook_dispatcher.deliver_once(
        _webhook_to_dict(wh),
        delivery.event,
        payload_str,
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
