from __future__ import annotations

import asyncio

import httpx

from bigrag.services.embedding.base import EmbeddingModel, get_semaphore, logger, truncate_to_tokens
from bigrag.services.embedding_rate_limit import (
    is_rate_limit_error,
    rate_limit_cooldown_key,
    rate_limit_delay,
    record_rate_limit_cooldown,
    wait_for_rate_limit_cooldown,
)
from bigrag.services.url_security import pin_embedding_base_url, pinned_async_client


class VoyageHTTPError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.headers: object | None = None


class VoyageEmbedding(EmbeddingModel):
    _DEFAULT_BASE_URL = "https://api.voyageai.com/v1"
    _EMBEDDINGS_PATH = "/embeddings"
    _INPUT_TYPES = {"document", "query"}
    _MAX_INPUTS_PER_REQUEST = 128

    def __init__(
        self,
        model_name: str = "voyage-3.5",
        api_key: str | None = None,
        dimension: int = 1024,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for the Voyage embedding provider")
        self._model_name = model_name
        self._dimension = dimension
        self._api_key = api_key
        self._semaphore_key = "voyage"
        self._cache_identity = f"voyage:{model_name}:{dimension}"
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()
        logger.info("initialized voyage embedding", model=model_name, dimension=dimension)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        async with self._client_lock:
            if self._client is not None:
                return self._client
            pinned = await pin_embedding_base_url(self._DEFAULT_BASE_URL)
            self._client = pinned_async_client(pinned, timeout=60.0)
            return self._client

    async def aclose(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            try:
                await client.aclose()
            except Exception as exc:
                logger.warning("failed to close voyage client", error=repr(exc))

    async def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        texts, warnings = truncate_to_tokens(texts, self._model_name)
        if any(warnings):
            truncated = sum(1 for w in warnings if w)
            logger.warning(
                "voyage inputs exceeded token limit and were truncated",
                truncated=truncated,
                inputs=len(texts),
                model=self._model_name,
            )
        voyage_input_type = input_type if input_type in self._INPUT_TYPES else "document"
        if len(texts) > self._MAX_INPUTS_PER_REQUEST:
            sub_batches = [
                texts[i : i + self._MAX_INPUTS_PER_REQUEST]
                for i in range(0, len(texts), self._MAX_INPUTS_PER_REQUEST)
            ]
            results = await asyncio.gather(
                *[self._embed_single(b, voyage_input_type) for b in sub_batches]
            )
            out: list[list[float]] = []
            for r in results:
                out.extend(r)
            return out
        return await self._embed_single(texts, voyage_input_type)

    async def _embed_single(self, texts: list[str], voyage_input_type: str) -> list[list[float]]:
        payload = {
            "input": texts,
            "model": self._model_name,
            "input_type": voyage_input_type,
            "output_dimension": self._dimension,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        cooldown_key = rate_limit_cooldown_key(
            self._cache_identity, self.provider, self._model_name, self._dimension
        )
        client = await self._get_client()
        async with await get_semaphore(self._semaphore_key):
            await wait_for_rate_limit_cooldown(cooldown_key, self.provider, self._model_name)
            try:
                response = await client.post(
                    f"{self._DEFAULT_BASE_URL}{self._EMBEDDINGS_PATH}",
                    json=payload,
                    headers=headers,
                )
            except Exception as exc:
                if is_rate_limit_error(exc):
                    await record_rate_limit_cooldown(cooldown_key, rate_limit_delay(exc, 1.0))
                raise
            if response.status_code >= 400:
                logger.warning(
                    "voyage embed http error",
                    status=response.status_code,
                    body_preview=response.text[:500],
                    model=self._model_name,
                )
                exc = VoyageHTTPError(
                    response.status_code,
                    f"Voyage embed failed ({response.status_code})",
                )
                exc.headers = response.headers
                if is_rate_limit_error(exc):
                    await record_rate_limit_cooldown(cooldown_key, rate_limit_delay(exc, 1.0))
                raise exc
        data = response.json()
        vectors = [item["embedding"] for item in data["data"]]
        for vector in vectors:
            if len(vector) != self._dimension:
                raise ValueError(
                    f"voyage returned vector of length {len(vector)}, "
                    f"expected {self._dimension} for model {self._model_name}"
                )
        return vectors

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "voyage"

    @property
    def cache_identity(self) -> str:
        return self._cache_identity
