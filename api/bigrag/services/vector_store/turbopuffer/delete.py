from __future__ import annotations

from itertools import batched

from turbopuffer import NotFoundError as TurbopufferNotFoundError

from bigrag.services.vector_store.turbopuffer.client import _DELETE_DOCUMENT_FILTER_SIZE


class _TurbopufferDeleteMixin:
    async def _safe_delete(self, collection: str, payloads: list[dict]) -> None:
        try:
            for payload in payloads:
                await self._write(collection, payload)
        except TurbopufferNotFoundError:
            return

    async def delete_by_document(self, collection: str, document_id: str) -> None:
        await self._safe_delete(
            collection,
            [{"delete_by_filter": ["document_id", "Eq", document_id]}],
        )

    async def delete_by_documents(self, collection: str, document_ids: list[str]) -> None:
        payloads = []
        for document_id_batch in batched(document_ids, _DELETE_DOCUMENT_FILTER_SIZE):
            if len(document_id_batch) == 1:
                delete_filter = ["document_id", "Eq", document_id_batch[0]]
            else:
                delete_filter = ["document_id", "In", list(document_id_batch)]
            payloads.append({"delete_by_filter": delete_filter})
        await self._safe_delete(collection, payloads)

    async def delete_by_ids(self, collection: str, ids: list[str]) -> None:
        deletes = [self._point_id(collection, id_) for id_ in ids]
        await self._safe_delete(collection, [{"deletes": deletes}])
