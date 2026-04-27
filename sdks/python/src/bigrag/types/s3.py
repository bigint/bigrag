"""S3 ingestion types."""

from __future__ import annotations

from bigrag.types._compat import Any, NotRequired, TypedDict


class S3IngestBody(TypedDict):
    bucket: str
    prefix: NotRequired[str]
    region: NotRequired[str]
    endpoint_url: NotRequired[str]
    access_key: NotRequired[str]
    secret_key: NotRequired[str]
    no_sign_request: NotRequired[bool]
    metadata: NotRequired[dict[str, Any]]
    file_types: NotRequired[list[str]]


class S3IngestResponse(TypedDict):
    status: str
    message: str


class S3Job(TypedDict):
    id: str
    collection_name: str
    bucket: str
    prefix: str
    region: str
    endpoint_url: str | None
    file_types: list[str]
    metadata: dict[str, Any]
    status: str
    total_found: int
    total_ingested: int
    total_skipped: int
    error_message: str | None
    created_at: str
    updated_at: str


class UpdateS3JobBody(TypedDict, total=False):
    file_types: list[str]
    metadata: dict[str, Any]


class S3JobListResponse(TypedDict):
    jobs: list[S3Job]
    total: int
