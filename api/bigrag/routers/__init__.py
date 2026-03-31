from __future__ import annotations

import logging

from fastapi import HTTPException

from bigrag.database import db
from bigrag.services.crypto import decrypt

logger = logging.getLogger("bigrag.routers")


async def get_collection_or_404(name: str) -> dict:
    """Shared helper to fetch a collection by name or raise 404."""
    row = await db.fetchrow("SELECT * FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")
    data = dict(row)
    # Decrypt the embedding API key if stored encrypted
    if data.get("embedding_api_key"):
        try:
            data["embedding_api_key"] = decrypt(data["embedding_api_key"])
        except Exception as e:
            logger.error(f"Failed to decrypt API key for collection '{name}': {e}")
            data["embedding_api_key"] = None
    return data
