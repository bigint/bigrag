from __future__ import annotations

import asyncio

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import AccessLog, QueryLog, UploadSession, WebhookDelivery
from bigrag.logging import get_logger
from bigrag.services import embedding_cache
from bigrag.services.runtime_settings import get_values

logger = get_logger("bigrag.cleanup")

TERMINAL_SESSION_STATUSES = ("complete", "failed", "canceled")


async def cleanup_old_data() -> None:

    while True:
        try:
            await asyncio.sleep(86400)
            await cleanup_old_data_once()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("cleanup failed", error=repr(exc))


async def cleanup_old_data_once() -> None:
    retention = await get_values(
        [
            "query_log_retention_days",
            "access_log_retention_days",
            "webhook_delivery_retention_days",
            "upload_session_item_retention_hours",
            "embedding_cache_retention_days",
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
        upload_cutoff = sa.func.now() - sa.text("make_interval(hours => :hours)").bindparams(
            hours=retention["upload_session_item_retention_hours"]
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
        us_result = await session.execute(
            sa.delete(UploadSession)
            .where(UploadSession.updated_at < upload_cutoff)
            .where(UploadSession.status.in_(TERMINAL_SESSION_STATUSES))
        )
        await session.commit()
    logger.info("query_log cleanup", deleted=ql_result.rowcount or 0)
    logger.info("access_log cleanup", deleted=al_result.rowcount or 0)
    logger.info("webhook_deliveries cleanup", deleted=wd_result.rowcount or 0)
    logger.info("upload_sessions cleanup", deleted=us_result.rowcount or 0)
    purged_embeddings = await embedding_cache.purge_stale(
        int(retention["embedding_cache_retention_days"])
    )
    logger.info("embedding_cache cleanup", deleted=purged_embeddings)
