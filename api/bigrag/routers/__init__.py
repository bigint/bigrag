from __future__ import annotations

from fastapi import HTTPException

from bigrag.database import db


async def get_collection_or_404(name: str) -> dict:
    """Shared helper to fetch a collection by name or raise 404."""
    row = await db.fetchrow("SELECT * FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")
    return dict(row)
