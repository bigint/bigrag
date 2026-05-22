from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass, field

import orjson

CHANNEL_PREFIX = "bigrag:events:"
LATEST_PREFIX = "bigrag:progress:"
LATEST_TTL_SECONDS = 7 * 24 * 60 * 60
SUBSCRIBER_QUEUE_SIZE = 256
SSE_RETRY_MS = 5000
COMPLETED_MAX_ENTRIES = 10000

_COMPLETE_MARKER = b'{"_complete":true}'
_sse_id_counter = itertools.count(1)


def next_sse_id() -> int:
    return next(_sse_id_counter)


@dataclass
class IngestionEvent:
    document_id: str
    step: str
    status: str
    message: str
    progress: float = 0.0
    detail: dict = field(default_factory=dict)
    collection_name: str = ""

    def serialize(self) -> bytes:
        return orjson.dumps(asdict(self))

    @classmethod
    def deserialize(cls, data: bytes) -> IngestionEvent:
        d = orjson.loads(data)
        return cls(
            document_id=d["document_id"],
            step=d["step"],
            status=d["status"],
            message=d["message"],
            progress=d.get("progress", 0.0),
            detail=d.get("detail", {}),
            collection_name=d.get("collection_name", ""),
        )
