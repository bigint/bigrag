from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import orjson

from bigrag.ids import uuid7
from bigrag.logging import get_logger
from bigrag.services.webhook.http import (
    delivery_timeout,
    get_semaphore,
    jittered_delay,
    post_pinned,
    retry_delays,
)
from bigrag.services.webhook.signing import compute_signature

logger = get_logger("bigrag.webhook")


def _signed_headers(payload: str, *, secret: str, event: str, delivery: str) -> dict[str, str]:
    timestamp = str(int(datetime.now(UTC).timestamp()))
    signature = compute_signature(payload, secret, timestamp)
    return {
        "Content-Type": "application/json",
        "X-BigRAG-Signature": signature,
        "X-BigRAG-Timestamp": timestamp,
        "X-BigRAG-Event": event,
        "X-BigRAG-Delivery": delivery,
        "User-Agent": "bigrag-webhooks/1.0",
    }


def _classify_response(response) -> dict:
    delivered = 200 <= response.status_code < 300
    return {
        "status": "delivered" if delivered else "failed",
        "status_code": response.status_code,
        "error": None if delivered else f"HTTP {response.status_code}",
    }


async def process_due_deliveries(
    *,
    delivery_id: uuid.UUID | None = None,
    limit: int = 25,
) -> int:
    import sqlalchemy as sa

    from bigrag.db.engine import session_factory
    from bigrag.db.models import Webhook, WebhookDelivery

    delays = retry_delays()
    max_attempts = len(delays) + 1
    claim_seconds = max(max(delivery_timeout(), 1) * 2, 60)

    async with session_factory()() as session:
        stmt = (
            sa.select(WebhookDelivery, Webhook)
            .join(Webhook, Webhook.id == WebhookDelivery.webhook_id)
            .where(WebhookDelivery.status == "pending")
            .where(
                sa.or_(
                    WebhookDelivery.next_retry_at.is_(None),
                    WebhookDelivery.next_retry_at <= sa.func.now(),
                )
            )
            .order_by(WebhookDelivery.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        if delivery_id is not None:
            stmt = stmt.where(WebhookDelivery.id == delivery_id)
        rows = (await session.execute(stmt)).all()
        work = []
        for delivery, webhook in rows:
            attempt = int(delivery.attempts or 0) + 1
            delivery.attempts = attempt
            delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=claim_seconds)
            work.append(
                {
                    "attempt": attempt,
                    "delivery_id": delivery.id,
                    "event": delivery.event,
                    "payload": orjson.dumps(delivery.payload).decode(),
                    "webhook": {
                        "id": webhook.id,
                        "url": webhook.url,
                        "secret": webhook.secret,
                    },
                }
            )
        await session.commit()

    groups: dict[str, list[dict]] = {}
    for item in work:
        groups.setdefault(str(item["webhook"]["id"]), []).append(item)

    async def _process_group(items: list[dict]) -> None:
        await asyncio.gather(
            *[
                _attempt_delivery(
                    item["webhook"],
                    item["event"],
                    item["payload"],
                    item["delivery_id"],
                    item["attempt"],
                    delays,
                    max_attempts,
                )
                for item in items
            ]
        )

    await asyncio.gather(*[_process_group(items) for items in groups.values()])
    return len(work)


async def _attempt_delivery(
    webhook: dict,
    event: str,
    payload: str,
    delivery_id: uuid.UUID,
    attempt: int,
    delays: list[int],
    max_attempts: int,
) -> None:
    import sqlalchemy as sa

    from bigrag.db.engine import session_factory
    from bigrag.db.models import WebhookDelivery

    webhook_id = str(webhook["id"])
    sem = get_semaphore(webhook_id)
    last_error = None
    last_status_code = None
    delivered = False
    terminal = False

    async with sem:
        try:
            headers = _signed_headers(
                payload,
                secret=webhook["secret"],
                event=event,
                delivery=str(delivery_id),
            )
            response = await post_pinned(webhook["url"], payload, headers)
            classified = _classify_response(response)
            last_status_code = classified["status_code"]
            delivered = classified["status"] == "delivered"
            last_error = classified["error"]
        except ValueError as exc:
            last_error = f"Blocked: {exc}"
            terminal = True
        except Exception as exc:
            last_error = str(exc)

    terminal = terminal or delivered or attempt >= max_attempts
    if delivered:
        values = {
            "status": "delivered",
            "last_status_code": last_status_code,
            "last_error": None,
            "next_retry_at": None,
            "completed_at": sa.func.now(),
        }
    elif terminal:
        values = {
            "status": "failed",
            "last_status_code": last_status_code,
            "last_error": last_error,
            "next_retry_at": None,
            "completed_at": sa.func.now(),
        }
    else:
        delay = jittered_delay(delays[attempt - 1])
        logger.warning(
            "webhook delivery failed",
            webhook=webhook_id,
            webhook_event=event,
            delivery=str(delivery_id),
            attempt=attempt,
            error=last_error,
            retrying_in=round(delay, 1),
        )
        values = {
            "last_status_code": last_status_code,
            "last_error": last_error,
            "next_retry_at": datetime.now(UTC) + timedelta(seconds=int(delay)),
        }

    async with session_factory()() as session:
        await session.execute(
            sa.update(WebhookDelivery).where(WebhookDelivery.id == delivery_id).values(**values)
        )
        await session.commit()

    if delivered:
        logger.info(
            "webhook delivered",
            webhook=webhook_id,
            webhook_event=event,
            delivery=str(delivery_id),
            attempt=attempt,
            status=last_status_code,
        )
    elif terminal:
        logger.error(
            "webhook delivery permanently failed",
            webhook=webhook_id,
            webhook_event=event,
            delivery=str(delivery_id),
            error=last_error,
        )


async def deliver_once(
    webhook: dict,
    event: str,
    payload: str,
    delivery_id: str | None = None,
) -> dict:
    headers = _signed_headers(
        payload,
        secret=webhook["secret"],
        event=event,
        delivery=delivery_id if delivery_id is not None else str(uuid7()),
    )
    try:
        response = await post_pinned(webhook["url"], payload, headers)
        return _classify_response(response)
    except ValueError:
        return {
            "status": "failed",
            "status_code": None,
            "error": "Blocked: URL targets a private or internal network",
        }
    except Exception as exc:
        return {
            "status": "failed",
            "status_code": None,
            "error": f"{exc.__class__.__name__}: {exc}",
        }


async def deliver_test(webhook: dict, delivery_id: str | None = None) -> dict:
    payload = orjson.dumps(
        {
            "event": "webhook.test",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    ).decode()

    headers = _signed_headers(
        payload,
        secret=webhook["secret"],
        event="webhook.test",
        delivery=delivery_id if delivery_id is not None else str(uuid7()),
    )
    try:
        response = await post_pinned(webhook["url"], payload, headers)
        return _classify_response(response)
    except ValueError:
        return {
            "status": "failed",
            "status_code": None,
            "error": "Blocked: URL targets a private or internal network",
        }
    except Exception:
        return {"status": "failed", "status_code": None, "error": "Connection failed"}
