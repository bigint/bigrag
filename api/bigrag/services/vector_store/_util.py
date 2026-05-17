from __future__ import annotations

from typing import cast

from bigrag.logging import get_logger
from bigrag.services.vector_store.base import VectorStoreBackend, VectorStoreProvider

logger = get_logger("bigrag.vector_store")

PROVIDERS: tuple[VectorStoreProvider, ...] = ("qdrant", "turbopuffer")


def validate_provider(value: str) -> VectorStoreProvider:
    if value not in PROVIDERS:
        raise ValueError(f"Unsupported vector store provider: {value}")
    return cast(VectorStoreProvider, value)


async def close_backends(
    backends: dict[VectorStoreProvider, VectorStoreBackend],
    *,
    log_errors: bool = False,
) -> None:
    seen: set[int] = set()
    for backend in backends.values():
        ident = id(backend)
        if ident in seen:
            continue
        seen.add(ident)
        try:
            await backend.close()
        except Exception as exc:
            if log_errors:
                logger.warning("old vector store close failed", error=str(exc))
            else:
                raise
