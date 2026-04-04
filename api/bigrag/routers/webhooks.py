from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from bigrag.database import db
from bigrag.middleware.auth import require_admin
from bigrag.models.webhook import (
    MAX_WEBHOOKS,
    CreateWebhookRequest,
    CreateWebhookResponse,
    UpdateWebhookRequest,
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookTestResponse,
)
from bigrag.services.crypto import encrypt
from bigrag.services.webhook import generate_secret, webhook_dispatcher

logger = logging.getLogger("bigrag.routers.webhooks")

router = APIRouter(prefix="/v1/admin/webhooks", tags=["webhooks"])


def _row_to_response(row: dict) -> WebhookResponse:
    r = {}
    for k, v in row.items():
        if k == "secret":
            continue
        elif isinstance(v, uuid.UUID):
            r[k] = str(v)
        else:
            r[k] = v
    return WebhookResponse(**r)


def _delivery_row_to_response(row: dict) -> WebhookDeliveryResponse:
    r = {}
    for k, v in row.items():
        if isinstance(v, uuid.UUID):
            r[k] = str(v)
        else:
            r[k] = v
    return WebhookDeliveryResponse(**r)


@router.post("", response_model=CreateWebhookResponse, status_code=201)
async def create_webhook(body: CreateWebhookRequest, admin: dict = Depends(require_admin)):
    count_row = await db.fetchrow("SELECT COUNT(*) as cnt FROM webhooks")
    if count_row["cnt"] >= MAX_WEBHOOKS:
        raise HTTPException(status_code=400, detail=f"Maximum of {MAX_WEBHOOKS} webhooks reached")

    secret = generate_secret()
    encrypted_secret = encrypt(secret)
    webhook_id = uuid.uuid4()

    row = await db.fetchrow(
        """
        INSERT INTO webhooks (id, url, secret, events, collections, description, created_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
        """,
        webhook_id,
        body.url,
        encrypted_secret,
        body.events,
        body.collections,
        body.description,
        uuid.UUID(admin["id"]) if admin.get("id") else None,
    )

    webhook_dispatcher.invalidate_cache()
    logger.info(f"Webhook created: id={webhook_id} url={body.url} events={body.events}")

    r = {k: str(v) if isinstance(v, uuid.UUID) else v for k, v in dict(row).items()}
    r.pop("secret")
    r["secret"] = secret
    return CreateWebhookResponse(**r)


@router.get("")
async def list_webhooks(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_admin),
):
    rows = await db.fetch(
        "SELECT * FROM webhooks ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        limit,
        offset,
    )
    return {"webhooks": [_row_to_response(dict(r)) for r in rows]}


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(webhook_id: str, _: dict = Depends(require_admin)):
    row = await db.fetchrow("SELECT * FROM webhooks WHERE id = $1", uuid.UUID(webhook_id))
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return _row_to_response(dict(row))


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    body: UpdateWebhookRequest,
    _: dict = Depends(require_admin),
):
    row = await db.fetchrow("SELECT * FROM webhooks WHERE id = $1", uuid.UUID(webhook_id))
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")

    from bigrag.database import build_update

    fields = {}
    if body.url is not None:
        fields["url"] = body.url
    if body.events is not None:
        fields["events"] = body.events
    if body.collections is not None:
        fields["collections"] = body.collections
    if body.description is not None:
        fields["description"] = body.description
    if body.active is not None:
        fields["active"] = body.active

    if not fields:
        return _row_to_response(dict(row))

    sql, params = build_update("webhooks", fields, "id", uuid.UUID(webhook_id))
    updated = await db.fetchrow(sql, *params)

    webhook_dispatcher.invalidate_cache()
    logger.info(f"Webhook updated: id={webhook_id}")
    return _row_to_response(dict(updated))


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str, _: dict = Depends(require_admin)):
    row = await db.fetchrow("SELECT id FROM webhooks WHERE id = $1", uuid.UUID(webhook_id))
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await db.execute("DELETE FROM webhooks WHERE id = $1", uuid.UUID(webhook_id))
    webhook_dispatcher.invalidate_cache()
    logger.info(f"Webhook deleted: id={webhook_id}")
    return {"status": "ok", "message": "Webhook deleted"}


@router.get("/{webhook_id}/deliveries", response_model=WebhookDeliveryListResponse)
async def list_deliveries(
    webhook_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_admin),
):
    wh = await db.fetchrow("SELECT id FROM webhooks WHERE id = $1", uuid.UUID(webhook_id))
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")

    rows = await db.fetch(
        """
        SELECT * FROM webhook_deliveries
        WHERE webhook_id = $1
        ORDER BY created_at DESC LIMIT $2 OFFSET $3
        """,
        uuid.UUID(webhook_id),
        limit,
        offset,
    )
    count_row = await db.fetchrow(
        "SELECT COUNT(*) as cnt FROM webhook_deliveries WHERE webhook_id = $1",
        uuid.UUID(webhook_id),
    )
    return WebhookDeliveryListResponse(
        deliveries=[_delivery_row_to_response(dict(r)) for r in rows],
        total=count_row["cnt"],
    )


@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(webhook_id: str, _: dict = Depends(require_admin)):
    row = await db.fetchrow("SELECT * FROM webhooks WHERE id = $1", uuid.UUID(webhook_id))
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")

    result = await webhook_dispatcher.deliver_test(dict(row))
    return WebhookTestResponse(**result)
