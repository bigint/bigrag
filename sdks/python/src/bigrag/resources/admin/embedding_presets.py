from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag.resources.admin._shared import _pagination
from bigrag.types.admin import (
    CreateEmbeddingPresetBody,
    EmbeddingPreset,
    EmbeddingPresetListResponse,
    UpdateEmbeddingPresetBody,
)
from bigrag.types.common import StatusResponse

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminEmbeddingPresetsResource:

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> EmbeddingPresetListResponse:
        params = _pagination(limit=limit, offset=offset)
        return await self._client._request(
            "GET", "/v1/admin/embedding-presets", params=params
        )

    async def create(self, body: CreateEmbeddingPresetBody) -> EmbeddingPreset:
        return await self._client._request(
            "POST", "/v1/admin/embedding-presets", json=body
        )

    async def update(
        self, preset_id: str, body: UpdateEmbeddingPresetBody
    ) -> EmbeddingPreset:
        return await self._client._request(
            "PATCH",
            f"/v1/admin/embedding-presets/{quote(preset_id, safe='')}",
            json=body,
        )

    async def test(
        self,
        *,
        provider: str,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> StatusResponse:
        body: dict[str, str | None] = {"provider": provider, "model": model}
        if api_key is not None:
            body["api_key"] = api_key
        if base_url is not None:
            body["base_url"] = base_url
        return await self._client._request(
            "POST", "/v1/admin/embedding-presets/test", json=body
        )

    async def test_saved(self, preset_id: str) -> StatusResponse:
        return await self._client._request(
            "POST", f"/v1/admin/embedding-presets/{quote(preset_id, safe='')}/test"
        )

    async def delete(self, preset_id: str) -> StatusResponse:
        return await self._client._request(
            "DELETE", f"/v1/admin/embedding-presets/{quote(preset_id, safe='')}"
        )
