from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BackupCreateRequest(BaseModel):
    label: str = Field(default="", max_length=160)


class BackupJobResponse(BaseModel):
    id: str
    label: str
    status: str
    progress: float
    destination_prefix: str
    object_count: int
    byte_count: int
    manifest: dict
    error_message: str | None = None
    created_by: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class BackupJobListResponse(BaseModel):
    jobs: list[BackupJobResponse]
    total: int | None = None
    next_cursor: str | None = None
