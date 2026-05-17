
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag.types.common import StatusResponse
from bigrag.types.webhooks import (
    CreateWebhookBody,
    CreateWebhookResponse,
    UpdateWebhookBody,
    Webhook,
    WebhookDeliveryListResponse,
    WebhookListResponse,
    WebhookTestResponse,
)

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class WebhooksResource:

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def create(self, body: CreateWebhookBody) -> CreateWebhookResponse:
        return await self._client._request("POST", "/v1/admin/webhooks", json=body)

    async def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> WebhookListResponse:
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        return await self._client._request("GET", "/v1/admin/webhooks", params=params)

    async def get(self, id: str) -> Webhook:
        return await self._client._request(
            "GET", f"/v1/admin/webhooks/{quote(id, safe='')}"
        )

    async def update(self, id: str, body: UpdateWebhookBody) -> Webhook:
        return await self._client._request(
            "PUT", f"/v1/admin/webhooks/{quote(id, safe='')}", json=body
        )

    async def delete(self, id: str) -> StatusResponse:
        return await self._client._request(
            "DELETE", f"/v1/admin/webhooks/{quote(id, safe='')}"
        )

    async def list_deliveries(
        self,
        id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> WebhookDeliveryListResponse:
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        return await self._client._request(
            "GET",
            f"/v1/admin/webhooks/{quote(id, safe='')}/deliveries",
            params=params,
        )

    async def test(self, id: str) -> WebhookTestResponse:
        return await self._client._request(
            "POST", f"/v1/admin/webhooks/{quote(id, safe='')}/test"
        )

    async def replay_delivery(self, id: str, delivery_id: str) -> WebhookTestResponse:
        return await self._client._request(
            "POST",
            (
                f"/v1/admin/webhooks/{quote(id, safe='')}/deliveries/"
                f"{quote(delivery_id, safe='')}/replay"
            ),
        )
