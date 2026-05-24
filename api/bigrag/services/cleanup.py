from __future__ import annotations

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import AccessLog, QueryLog, UploadSession, WebhookDelivery
from bigrag.logging import get_logger
from bigrag.services import embedding_cache
from bigrag.services.runtime_settings import get_values
from bigrag.services.staged_files import cleanup_terminal_staged_files

logger = get_logger("bigrag.cleanup")

TERMINAL_SESSION_STATUSES = ("complete", "failed", "canceled")
_DELETE_CHUNK = 5000


def _days_ago(days: int):
    return sa.func.now() - sa.text("make_interval(days => :days)").bindparams(days=days)


def _hours_ago(hours: int):
    return sa.func.now() - sa.text("make_interval(hours => :hours)").bindparams(hours=hours)


async def _delete_in_chunks(model, condition) -> int:
    total = 0
    while True:
        async with session_factory()() as session:
            subquery = sa.select(model.id).where(condition).limit(_DELETE_CHUNK)
            result = await session.execute(sa.delete(model).where(model.id.in_(subquery)))
            await session.commit()
        deleted = result.rowcount or 0
        total += deleted
        if deleted < _DELETE_CHUNK:
            return total


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
    ql = await _delete_in_chunks(
        QueryLog, QueryLog.created_at < _days_ago(retention["query_log_retention_days"])
    )
    al = await _delete_in_chunks(
        AccessLog, AccessLog.created_at < _days_ago(retention["access_log_retention_days"])
    )
    wd = await _delete_in_chunks(
        WebhookDelivery,
        WebhookDelivery.created_at < _days_ago(retention["webhook_delivery_retention_days"]),
    )
    us = await _delete_in_chunks(
        UploadSession,
        sa.and_(
            UploadSession.updated_at < _hours_ago(retention["upload_session_item_retention_hours"]),
            UploadSession.status.in_(TERMINAL_SESSION_STATUSES),
        ),
    )
    logger.info("query_log cleanup", deleted=ql)
    logger.info("access_log cleanup", deleted=al)
    logger.info("webhook_deliveries cleanup", deleted=wd)
    logger.info("upload_sessions cleanup", deleted=us)
    purged_embeddings = await embedding_cache.purge_stale(
        int(retention["embedding_cache_retention_days"])
    )
    logger.info("embedding_cache cleanup", deleted=purged_embeddings)
    cleaned_staged_files = await cleanup_terminal_staged_files()
    logger.info("staged_files cleanup", deleted=cleaned_staged_files)
