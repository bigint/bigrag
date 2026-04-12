"""FastAPI session dependency — yields a fresh AsyncSession per request."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.engine import session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as session:
        yield session
