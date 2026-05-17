from __future__ import annotations

from bigrag.logging import get_logger

logger = get_logger("bigrag.retrieval")


async def log_query(
    collection_name: str,
    query: str,
    top_k: int,
    result_count: int,
    avg_score: float | None,
    latency_ms: float,
    search_mode: str,
    collection_id: str | None = None,
) -> None:
    try:
        import uuid as _uuid

        import sqlalchemy as _sa

        from bigrag.db.engine import session_factory
        from bigrag.db.models import Collection, QueryLog

        async with session_factory()() as session:
            cid = None
            if collection_id is not None:
                try:
                    cid = _uuid.UUID(collection_id)
                except (TypeError, ValueError):
                    cid = None
            if cid is None:
                cid = await session.scalar(
                    _sa.select(Collection.id).where(Collection.name == collection_name)
                )
            session.add(
                QueryLog(
                    collection_id=cid,
                    collection_name=collection_name,
                    query=query[:500],
                    top_k=top_k,
                    result_count=result_count,
                    avg_score=avg_score,
                    latency_ms=latency_ms,
                    search_mode=search_mode,
                )
            )
            await session.commit()
    except Exception as exc:
        logger.warning("failed to log query", error=repr(exc))
