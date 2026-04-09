from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class S3IngestRequest(BaseModel):
    bucket: str
    prefix: str = ""
    region: str = "us-east-1"
    endpoint_url: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    no_sign_request: bool = False
    metadata: dict = {}
    file_types: list[str] = []  # empty means all supported types


class S3IngestResponse(BaseModel):
    status: str
    message: str


class S3JobResponse(BaseModel):
    id: str
    collection_name: str
    bucket: str
    prefix: str
    region: str
    status: str
    total_found: int
    total_ingested: int
    total_skipped: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class S3JobListResponse(BaseModel):
    jobs: list[S3JobResponse]
    total: int
