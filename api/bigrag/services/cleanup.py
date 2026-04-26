from __future__ import annotations

import asyncio

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import QueryLog, WebhookDelivery
from bigrag.logging import get_logger

logger = get_logger("bigrag.cleanup")

_NINETY_DAYS = sa.text("make_interval(days => 90)")


async def cleanup_old_data() -> None:

    while True:
        try:
            await asyncio.sleep(86400)
            async with session_factory()() as session:
                cutoff = sa.func.now() - _NINETY_DAYS
                ql_result = await session.execute(
                    sa.delete(QueryLog).where(QueryLog.created_at < cutoff)
                )
                wd_result = await session.execute(
                    sa.delete(WebhookDelivery).where(WebhookDelivery.created_at < cutoff)
                )
                await session.commit()
            logger.info(f"query_log cleanup: {ql_result.rowcount or 0}")
            logger.info(f"webhook_deliveries cleanup: {wd_result.rowcount or 0}")
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.warning(f"Cleanup failed: {e!r}")
