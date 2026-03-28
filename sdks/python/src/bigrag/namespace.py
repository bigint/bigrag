"""Namespace operations for the bigRAG Python SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Sequence, Union

from bigrag.types import (
    Document,
    NamespaceMetadata,
    QueryResponse,
    WriteResponse,
)

if TYPE_CHECKING:
    from bigrag.client import AsyncBigRAG, BigRAG


class Namespace:
    """Synchronous interface for a single bigRAG namespace."""

    def __init__(self, client: BigRAG, name: str) -> None:
        self._client = client
        self.name = name

    def __repr__(self) -> str:
        return f"Namespace({self.name!r})"

    # -- writes ----------------------------------------------------------------

    def upsert(
        self,
        rows: Sequence[dict[str, Any] | Document],
        *,
        distance_metric: str | None = None,
        schema: dict[str, Any] | None = None,
    ) -> WriteResponse:
        """Upsert rows into the namespace."""
        serialized = [
            r.to_dict() if isinstance(r, Document) else r for r in rows
        ]
        body: dict[str, Any] = {"upsert_rows": serialized}
        if distance_metric is not None:
            body["distance_metric"] = distance_metric
        if schema is not None:
            body["schema"] = schema
        data = self._client._post(f"/v2/namespaces/{self.name}", json=body)
        return WriteResponse.from_dict(data)

    def delete(self, ids: Sequence[int | str]) -> WriteResponse:
        """Delete rows by their IDs."""
        body: dict[str, Any] = {"delete_ids": list(ids)}
        data = self._client._post(f"/v2/namespaces/{self.name}", json=body)
        return WriteResponse.from_dict(data)

    def delete_all(self) -> None:
        """Delete the entire namespace."""
        self._client._delete(f"/v2/namespaces/{self.name}")

    def delete_by_filter(
        self,
        filter: list[Any],
        *,
        max_affected: int = 5_000_000,
        allow_partial: bool = False,
    ) -> WriteResponse:
        """Delete rows matching a filter expression."""
        body: dict[str, Any] = {
            "delete_by_filter": filter,
            "max_affected": max_affected,
            "allow_partial": allow_partial,
        }
        data = self._client._post(f"/v2/namespaces/{self.name}", json=body)
        return WriteResponse.from_dict(data)

    def patch(
        self, rows: Sequence[dict[str, Any] | Document]
    ) -> WriteResponse:
        """Patch (partial update) existing rows."""
        serialized = [
            r.to_dict() if isinstance(r, Document) else r for r in rows
        ]
        body: dict[str, Any] = {"patch_rows": serialized}
        data = self._client._post(f"/v2/namespaces/{self.name}", json=body)
        return WriteResponse.from_dict(data)

    # -- reads -----------------------------------------------------------------

    def query(
        self,
        *,
        rank_by: Optional[list[Any]] = None,
        filters: Optional[list[Any]] = None,
        top_k: int = 10,
        include_attributes: Optional[Union[bool, List[str]]] = None,
        include_vectors: bool = False,
    ) -> QueryResponse:
        """Query the namespace."""
        body: dict[str, Any] = {"top_k": top_k}
        if rank_by is not None:
            body["rank_by"] = rank_by
        if filters is not None:
            body["filters"] = filters
        if include_attributes is not None:
            body["include_attributes"] = include_attributes
        if include_vectors:
            body["include_vectors"] = True
        data = self._client._post(
            f"/v2/namespaces/{self.name}/query", json=body
        )
        return QueryResponse.from_dict(data)

    def metadata(self) -> NamespaceMetadata:
        """Get namespace metadata."""
        data = self._client._get(f"/v1/namespaces/{self.name}/metadata")
        return NamespaceMetadata.from_dict(data)

    def schema(self) -> dict[str, Any]:
        """Get the namespace schema."""
        return self._client._get(f"/v1/namespaces/{self.name}/schema")

    def update_schema(self, schema: dict[str, Any]) -> None:
        """Update the namespace schema."""
        self._client._put(f"/v1/namespaces/{self.name}/schema", json=schema)

    def recall(self, *, num: int = 25, top_k: int = 10) -> dict[str, Any]:
        """Run a recall debug check."""
        body: dict[str, Any] = {"num": num, "top_k": top_k}
        return self._client._post(
            f"/v1/namespaces/{self.name}/_debug/recall", json=body
        )


class AsyncNamespace:
    """Asynchronous interface for a single bigRAG namespace."""

    def __init__(self, client: AsyncBigRAG, name: str) -> None:
        self._client = client
        self.name = name

    def __repr__(self) -> str:
        return f"AsyncNamespace({self.name!r})"

    # -- writes ----------------------------------------------------------------

    async def upsert(
        self,
        rows: Sequence[dict[str, Any] | Document],
        *,
        distance_metric: str | None = None,
        schema: dict[str, Any] | None = None,
    ) -> WriteResponse:
        """Upsert rows into the namespace."""
        serialized = [
            r.to_dict() if isinstance(r, Document) else r for r in rows
        ]
        body: dict[str, Any] = {"upsert_rows": serialized}
        if distance_metric is not None:
            body["distance_metric"] = distance_metric
        if schema is not None:
            body["schema"] = schema
        data = await self._client._post(
            f"/v2/namespaces/{self.name}", json=body
        )
        return WriteResponse.from_dict(data)

    async def delete(self, ids: Sequence[int | str]) -> WriteResponse:
        """Delete rows by their IDs."""
        body: dict[str, Any] = {"delete_ids": list(ids)}
        data = await self._client._post(
            f"/v2/namespaces/{self.name}", json=body
        )
        return WriteResponse.from_dict(data)

    async def delete_all(self) -> None:
        """Delete the entire namespace."""
        await self._client._delete(f"/v2/namespaces/{self.name}")

    async def delete_by_filter(
        self,
        filter: list[Any],
        *,
        max_affected: int = 5_000_000,
        allow_partial: bool = False,
    ) -> WriteResponse:
        """Delete rows matching a filter expression."""
        body: dict[str, Any] = {
            "delete_by_filter": filter,
            "max_affected": max_affected,
            "allow_partial": allow_partial,
        }
        data = await self._client._post(
            f"/v2/namespaces/{self.name}", json=body
        )
        return WriteResponse.from_dict(data)

    async def patch(
        self, rows: Sequence[dict[str, Any] | Document]
    ) -> WriteResponse:
        """Patch (partial update) existing rows."""
        serialized = [
            r.to_dict() if isinstance(r, Document) else r for r in rows
        ]
        body: dict[str, Any] = {"patch_rows": serialized}
        data = await self._client._post(
            f"/v2/namespaces/{self.name}", json=body
        )
        return WriteResponse.from_dict(data)

    # -- reads -----------------------------------------------------------------

    async def query(
        self,
        *,
        rank_by: Optional[list[Any]] = None,
        filters: Optional[list[Any]] = None,
        top_k: int = 10,
        include_attributes: Optional[Union[bool, List[str]]] = None,
        include_vectors: bool = False,
    ) -> QueryResponse:
        """Query the namespace."""
        body: dict[str, Any] = {"top_k": top_k}
        if rank_by is not None:
            body["rank_by"] = rank_by
        if filters is not None:
            body["filters"] = filters
        if include_attributes is not None:
            body["include_attributes"] = include_attributes
        if include_vectors:
            body["include_vectors"] = True
        data = await self._client._post(
            f"/v2/namespaces/{self.name}/query", json=body
        )
        return QueryResponse.from_dict(data)

    async def metadata(self) -> NamespaceMetadata:
        """Get namespace metadata."""
        data = await self._client._get(
            f"/v1/namespaces/{self.name}/metadata"
        )
        return NamespaceMetadata.from_dict(data)

    async def schema(self) -> dict[str, Any]:
        """Get the namespace schema."""
        return await self._client._get(
            f"/v1/namespaces/{self.name}/schema"
        )

    async def update_schema(self, schema: dict[str, Any]) -> None:
        """Update the namespace schema."""
        await self._client._put(
            f"/v1/namespaces/{self.name}/schema", json=schema
        )

    async def recall(
        self, *, num: int = 25, top_k: int = 10
    ) -> dict[str, Any]:
        """Run a recall debug check."""
        body: dict[str, Any] = {"num": num, "top_k": top_k}
        return await self._client._post(
            f"/v1/namespaces/{self.name}/_debug/recall", json=body
        )
