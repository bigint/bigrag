from __future__ import annotations

from bigrag.routers.documents import crud, elements, listing  # noqa: F401
from bigrag.routers.documents._router import router

__all__ = ["router"]
