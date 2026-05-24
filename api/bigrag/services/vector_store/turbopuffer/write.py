from __future__ import annotations

from typing import Any

from turbopuffer import BadRequestError as TurbopufferBadRequestError

from bigrag.services.vector_store.attributes import encode_attributes
from bigrag.services.vector_store.base import _build_payload
from bigrag.services.vector_store.dimensions import (
    VectorStoreDimensionMismatchError,
    collection_schema,
    is_turbopuffer_dimension_mismatch,
    turbopuffer_error_message,
    turbopuffer_mismatch_dimension,
    write_payload_dimension,
)
from bigrag.services.vector_store.turbopuffer.client import _PUBLIC_ID_FIELD


class _TurbopufferWriteMixin:
    async def insert(
        self,
        collection: str,
        ids: list[str],
        document_ids: list[str],
        chunk_indices: list[int],
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict] | None = None,
    ) -> int:
        rows = []
        for i in range(len(ids)):
            payload = _build_payload(
                id_=ids[i],
                document_id=document_ids[i],
                chunk_index=chunk_indices[i],
                text=texts[i],
                metadata=metadata[i] if metadata else None,
            )
            public_id = payload.pop("id")
            payload[_PUBLIC_ID_FIELD] = public_id
            rows.append(
                encode_attributes(
                    {
                        "id": self._point_id(collection, ids[i]),
                        "vector": embeddings[i],
                        **payload,
                    }
                )
            )
        write_payload: dict[str, Any] = {
            "upsert_rows": rows,
            "distance_metric": "cosine_distance",
        }
        if embeddings:
            dimension = len(embeddings[0])
            write_payload["schema"] = collection_schema(dimension, _PUBLIC_ID_FIELD)
        await self._write(collection, write_payload)
        return len(rows)

    async def _write(self, collection: str, payload: dict) -> dict:
        try:
            response = await self._namespace_client(collection).write(**payload)
        except TurbopufferBadRequestError as exc:
            message = turbopuffer_error_message(exc)
            if is_turbopuffer_dimension_mismatch(message):
                raise VectorStoreDimensionMismatchError(
                    collection=collection,
                    namespace=self._namespace(collection),
                    expected=write_payload_dimension(payload) or 0,
                    actual=turbopuffer_mismatch_dimension(message),
                ) from exc
            raise
        if hasattr(response, "to_dict"):
            return response.to_dict()
        return {}

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadata: list[dict] | None = None,
    ) -> int:
        return await self.insert(
            collection,
            ids,
            [""] * len(ids),
            [0] * len(ids),
            texts,
            embeddings,
            metadata,
        )
