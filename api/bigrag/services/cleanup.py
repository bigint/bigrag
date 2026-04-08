from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("bigrag.cleanup")


async def cleanup_old_data(db) -> None:
    """Periodically clean query_log and webhook_deliveries older than 90 days."""
    while True:
        try:
            await asyncio.sleep(86400)  # Run daily
            deleted = await db.execute(
                "DELETE FROM query_log WHERE created_at < now() - interval '90 days'"
            )
            logger.info(f"query_log cleanup: {deleted}")
            deleted = await db.execute(
                "DELETE FROM webhook_deliveries WHERE created_at < now() - interval '90 days'"
            )
            logger.info(f"webhook_deliveries cleanup: {deleted}")
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.warning(f"Cleanup failed: {e!r}")
