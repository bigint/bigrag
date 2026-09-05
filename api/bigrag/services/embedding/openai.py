from __future__ import annotations

import asyncio
import hashlib

from bigrag.services.embedding.base import EmbeddingModel, logger, truncate_to_tokens
from bigrag.services.embedding_gate import embedding_gate
from bigrag.services.url_security import (
    pinned_openai_client,
    resolve_and_pin_sync,
    validate_embedding_base_url_sync,
)


class OpenAIEmbedding(EmbeddingModel):
    _MAX_INPUTS_PER_REQUEST = 2048

    @staticmethod
    def _supports_dimensions(model_name: str) -> bool:
        return model_name.startswith("text-embedding-3-")

    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        api_key: str | None = None,
        dimension: int = 1536,
        base_url: str | None = None,
    ) -> None:
        try:
            import openai
        except ImportError as e:
            raise ImportError(
                "openai package is required for OpenAI-compatible embeddings. "
                "Install it with: pip install 'bigrag[openai]'"
            ) from e

        self._model_name = model_name
        self._dimension = dimension
        self._base_url = validate_embedding_base_url_sync(base_url)
        base_tag = hashlib.sha256((self._base_url or "").encode()).hexdigest()[:12]
        self._cache_identity = f"openai:{model_name}:{dimension}:{base_tag}"
        from bigrag.services.runtime_settings import sync_value

        effective_base_url = self._base_url or "https://api.openai.com/v1"
        pinned = resolve_and_pin_sync(
            effective_base_url,
            purpose="Embedding base URL",
            allowed_urls=sync_value("allowed_embedding_base_urls"),
            allow_private=sync_value("allow_private_embedding_base_urls"),
        )
        self._client = openai.AsyncOpenAI(
            api_key=api_key or "not-required",
            base_url=self._base_url,
            http_client=pinned_openai_client(pinned, timeout=60.0),
        )
        logger.info(
            "initialized openai-compatible embedding",
            model=model_name,
            dimension=dimension,
            base_url=self._base_url or "default",
        )

    async def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        _ = input_type
        texts, warnings = truncate_to_tokens(texts, self._model_name)
        if any(warnings):
            truncated = sum(1 for w in warnings if w)
            logger.warning(
                "openai inputs exceeded token limit and were truncated",
                truncated=truncated,
                inputs=len(texts),
                model=self._model_name,
            )
        if len(texts) > self._MAX_INPUTS_PER_REQUEST:
            sub_batches = [
                texts[i : i + self._MAX_INPUTS_PER_REQUEST]
                for i in range(0, len(texts), self._MAX_INPUTS_PER_REQUEST)
            ]
            results = await asyncio.gather(*[self._embed_single(b) for b in sub_batches])
            out: list[list[float]] = []
            for r in results:
                out.extend(r)
            return out
        return await self._embed_single(texts)

    async def _embed_single(self, texts: list[str]) -> list[list[float]]:
        kwargs: dict = {"input": texts, "model": self._model_name}
        if self._supports_dimensions(self._model_name):
            kwargs["dimensions"] = self._dimension
        async with embedding_gate(self._cache_identity, self.provider, self._model_name):
            response = await asyncio.wait_for(
                self._client.embeddings.create(**kwargs),
                timeout=60,
            )
        vectors = [item.embedding for item in response.data]
        for vector in vectors:
            if len(vector) != self._dimension:
                raise ValueError(
                    f"openai returned vector of length {len(vector)}, "
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
        return "openai"

    @property
    def cache_identity(self) -> str:
        return self._cache_identity
