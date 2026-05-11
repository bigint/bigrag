from __future__ import annotations

from pydantic import BaseModel


class StatusResponse(BaseModel):
    status: str = "ok"
    message: str = ""
