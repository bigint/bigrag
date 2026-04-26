from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, model_validator

from bigrag.models.webhook import resolve_and_validate_url


def validate_s3_endpoint_url(url: str) -> None:
    """Reject S3 endpoint URLs that target private networks or use unsupported
    schemes. Loopback http is allowed for local MinIO dev."""
    parsed = urlparse(url)
    is_localhost = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_localhost):
        raise ValueError(
            "endpoint_url must use HTTPS (HTTP allowed only for localhost)"
        )
    resolve_and_validate_url(url)


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

    @model_validator(mode="after")
    def _validate_endpoint_url(self):
        if self.endpoint_url:
            validate_s3_endpoint_url(self.endpoint_url)
        return self


class S3IngestResponse(BaseModel):
    status: str
    message: str


class S3JobResponse(BaseModel):
    id: str
    collection_name: str
    bucket: str
    prefix: str
    region: str
    endpoint_url: str | None = None
    file_types: list[str] = []
    metadata: dict = {}
    status: str
    total_found: int
    total_ingested: int
    total_skipped: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class UpdateS3JobRequest(BaseModel):
    file_types: list[str] | None = None
    metadata: dict | None = None


class S3JobListResponse(BaseModel):
    jobs: list[S3JobResponse]
    total: int
