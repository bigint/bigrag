from __future__ import annotations

from typing import Any

from turbopuffer import AsyncTurbopuffer
from turbopuffer import NotFoundError as TurbopufferNotFoundError

from bigrag.logging import get_logger
from bigrag.services._retrieval_filters import FilterCondition, FilterExpression
from bigrag.services.vector_store.attributes import decode_attributes
from bigrag.services.vector_store.base import _backend_name, _point_id
from bigrag.services.vector_store.dimensions import (
    VectorStoreDimensionMismatchError,
    collection_schema,
    vector_dimension,
)

logger = get_logger("bigrag.vector_store")

_PUBLIC_ID_FIELD = "bigrag_id"
_EXPORT_PAGE_SIZE = 10000
_DELETE_DOCUMENT_FILTER_SIZE = 1000


def _to_turbopuffer_filter(filters: FilterExpression | None) -> tuple | None:
    if filters is None:
        return None
    clauses = [_to_turbopuffer_condition(condition) for condition in filters.conditions]
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return ("And", tuple(clauses))


def _to_turbopuffer_condition(condition: FilterCondition) -> tuple:
    field = _PUBLIC_ID_FIELD if condition.field == "id" else condition.field
    op = {
        "eq": "Eq",
        "ne": "NotEq",
        "gt": "Gt",
        "gte": "Gte",
        "lt": "Lt",
        "lte": "Lte",
        "in": "In",
    }[condition.operator]
    return (field, op, condition.value)


def _row_payload(row: dict) -> dict:
    decoded = decode_attributes(row)
    payload = {
        k: v
        for k, v in decoded.items()
        if k not in {"$dist", "vector", _PUBLIC_ID_FIELD} and v is not None
    }
    payload["id"] = decoded.get(_PUBLIC_ID_FIELD) or decoded.get("id")
    return payload


def _response_row(row: Any) -> dict:
    if isinstance(row, dict):
        return row
    if hasattr(row, "to_dict"):
        return row.to_dict()
    if hasattr(row, "model_dump"):
        return row.model_dump(mode="json", by_alias=True)
    return dict(row)


class _TurbopufferClientMixin:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        region: str = "aws-us-east-1",
        namespace_prefix: str = "bigrag_",
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.region = region
        self.prefix = namespace_prefix or "bigrag_"
        self.base_url = base_url.rstrip("/") if base_url else None
        self.client: AsyncTurbopuffer | None = None

    def connect(self) -> None:
        if not self.api_key:
            raise RuntimeError("turbopuffer API key is not configured")
        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        else:
            kwargs["region"] = self.region
        self.client = AsyncTurbopuffer(
            **kwargs,
            max_retries=2,
            timeout=30,
        )
        logger.info("connected to turbopuffer", region=self.region, base_url=self.base_url)

    def _client(self) -> AsyncTurbopuffer:
        if self.client is None:
            self.connect()
        if self.client is None:
            raise RuntimeError("turbopuffer client is not connected")
        return self.client

    def _namespace_client(self, name: str):
        return self._client().namespace(self._namespace(name))

    def _namespace(self, name: str) -> str:
        return _backend_name(self.prefix, name)

    def _point_id(self, collection: str, value: str) -> str:
        return _point_id(self._namespace(collection), value)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            self.client = None

    async def health_check(self) -> None:
        async for _ in self._client().namespaces(prefix=self.prefix, page_size=1):
            break

    async def create_collection(
        self,
        name: str,
        dimension: int,
        tenant_field: str | None = None,
    ) -> None:
        await self.health_check()
        schema = await self._collection_schema(name)
        actual_dimension = vector_dimension(schema)
        if actual_dimension is not None and actual_dimension != dimension:
            raise VectorStoreDimensionMismatchError(
                collection=name,
                namespace=self._namespace(name),
                expected=dimension,
                actual=actual_dimension,
            )
        if schema is not None and actual_dimension is None:
            await self._namespace_client(name).update_schema(
                schema=collection_schema(dimension, _PUBLIC_ID_FIELD)
            )

    async def _collection_schema(self, name: str) -> dict[str, Any] | None:
        try:
            return await self._namespace_client(name).schema()
        except TurbopufferNotFoundError:
            return None

    async def delete_collection(self, name: str) -> None:
        try:
            await self._namespace_client(name).delete_all()
        except TurbopufferNotFoundError:
            return
