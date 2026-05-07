from __future__ import annotations

import asyncio

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import AccessLog, QueryLog, WebhookDelivery
from bigrag.logging import get_logger
from bigrag.services.runtime_settings import get_values

logger = get_logger("bigrag.cleanup")


async def cleanup_old_data() -> None:

    while True:
        try:
            await asyncio.sleep(86400)
            retention = await get_values(
                [
                    "query_log_retention_days",
                    "access_log_retention_days",
                    "webhook_delivery_retention_days",
                ]
            )
            async with session_factory()() as session:
                query_cutoff = sa.func.now() - sa.text("make_interval(days => :days)").bindparams(
                    days=retention["query_log_retention_days"]
                )
                access_cutoff = sa.func.now() - sa.text("make_interval(days => :days)").bindparams(
                    days=retention["access_log_retention_days"]
                )
                webhook_cutoff = sa.func.now() - sa.text("make_interval(days => :days)").bindparams(
                    days=retention["webhook_delivery_retention_days"]
                )
                ql_result = await session.execute(
                    sa.delete(QueryLog).where(QueryLog.created_at < query_cutoff)
                )
                al_result = await session.execute(
                    sa.delete(AccessLog).where(AccessLog.created_at < access_cutoff)
                )
                wd_result = await session.execute(
                    sa.delete(WebhookDelivery).where(WebhookDelivery.created_at < webhook_cutoff)
                )
                await session.commit()
            logger.info(f"query_log cleanup: {ql_result.rowcount or 0}")
            logger.info(f"access_log cleanup: {al_result.rowcount or 0}")
            logger.info(f"webhook_deliveries cleanup: {wd_result.rowcount or 0}")
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.warning(f"Cleanup failed: {e!r}")
