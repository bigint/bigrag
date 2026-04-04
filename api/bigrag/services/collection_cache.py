from __future__ import annotations

import logging
import time

from fastapi import HTTPException

from bigrag.config import settings
from bigrag.database import db
from bigrag.services.crypto import decrypt

logger = logging.getLogger("bigrag.collection_cache")

_cache: dict[str, tuple[dict, float]] = {}


def invalidate(name: str | None = None) -> None:
    if name:
        _cache.pop(name, None)
    else:
        _cache.clear()


async def get_or_404(name: str) -> dict:
    entry = _cache.get(name)
    if entry:
        data, expires_at = entry
        if time.monotonic() < expires_at:
            return data
        _cache.pop(name, None)

    row = await db.fetchrow("SELECT * FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")
    data = dict(row)
    if data.get("embedding_api_key"):
        try:
            data["embedding_api_key"] = decrypt(data["embedding_api_key"])
        except Exception as e:
            logger.error(f"Failed to decrypt API key for collection '{name}': {e}")
            data["embedding_api_key"] = None

    _cache[name] = (data, time.monotonic() + settings.collection_cache_ttl)
    return data
