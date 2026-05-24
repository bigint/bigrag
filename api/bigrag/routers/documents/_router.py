from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/v1/collections/{collection_name}/documents", tags=["documents"])
