from __future__ import annotations

from fastapi import APIRouter

from bigrag.logging import get_logger

logger = get_logger("bigrag.routers.webhooks")

router = APIRouter(prefix="/v1/admin/webhooks", tags=["webhooks"])
