from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.engine import session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
