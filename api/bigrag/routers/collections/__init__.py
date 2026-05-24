from __future__ import annotations

from bigrag.routers.collections import list_create, read, update_delete  # noqa: F401
from bigrag.routers.collections._router import router

__all__ = ["router"]
