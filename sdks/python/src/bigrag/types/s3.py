"""S3 ingestion types."""

from __future__ import annotations

from bigrag.types._compat import Any, NotRequired, TypedDict
from bigrag.types.documents import Document


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
    documents: list[Document]
    total: int
    skipped: list[str]
