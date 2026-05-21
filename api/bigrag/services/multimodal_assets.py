from __future__ import annotations

import base64
from pathlib import PurePosixPath
from typing import Any

from bigrag.services.storage import get_storage

IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


async def image_content_parts_for_refs(
    refs: list[dict[str, Any]],
    *,
    max_images: int = 4,
    max_bytes: int = 5_000_000,
) -> list[dict[str, Any]]:
    storage = get_storage()
    parts = []
    seen = set()
    for ref in refs:
        if len(parts) >= max_images:
            break
        asset_path = ref.get("asset_path")
        if not isinstance(asset_path, str) or asset_path in seen:
            continue
        suffix = PurePosixPath(asset_path).suffix.lower()
        mime = IMAGE_MIME_BY_SUFFIX.get(suffix)
        if mime is None:
            continue
        try:
            data = await storage.get(asset_path)
        except Exception:
            continue
        if not data or len(data) > max_bytes:
            continue
        seen.add(asset_path)
        parts.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
                },
            }
        )
    return parts
