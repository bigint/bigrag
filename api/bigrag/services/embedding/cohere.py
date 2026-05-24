from __future__ import annotations

import asyncio

from bigrag.services.embedding.base import EmbeddingModel, logger, truncate_to_tokens
from bigrag.services.embedding_gate import embedding_gate


class CohereEmbedding(EmbeddingModel):
    _INPUT_TYPE_MAP = {
        "document": "search_document",
        "query": "search_query",
    }
    _MAX_INPUTS_PER_REQUEST = 96

    def __init__(
        self,
        model_name: str = "embed-english-v3.0",
        api_key: str | None = None,
        dimension: int = 1024,
    ) -> None:
        try:
            import cohere
        except ImportError as e:
            raise ImportError(
                "cohere package is required for Cohere embeddings. "
                "Install it with: pip install 'bigrag[cohere]'"
            ) from e

        self._model_name = model_name
        self._dimension = dimension
        self._cache_identity = f"cohere:{model_name}:{dimension}"
        self._client = cohere.AsyncClient(api_key=api_key)
        logger.info("initialized cohere embedding", model=model_name, dimension=dimension)

    async def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        texts, warnings = truncate_to_tokens(texts, self._model_name)
        if any(warnings):
            truncated = sum(1 for w in warnings if w)
            logger.warning(
                "cohere inputs exceeded token limit and were truncated",
                truncated=truncated,
                inputs=len(texts),
                model=self._model_name,
            )
        cohere_input_type = self._INPUT_TYPE_MAP.get(input_type, "search_document")
        if len(texts) > self._MAX_INPUTS_PER_REQUEST:
            sub_batches = [
                texts[i : i + self._MAX_INPUTS_PER_REQUEST]
                for i in range(0, len(texts), self._MAX_INPUTS_PER_REQUEST)
            ]
            results = await asyncio.gather(
                *[self._embed_single(b, cohere_input_type) for b in sub_batches]
            )
            out: list[list[float]] = []
            for r in results:
                out.extend(r)
            return out
        return await self._embed_single(texts, cohere_input_type)

    async def _embed_single(self, texts: list[str], cohere_input_type: str) -> list[list[float]]:
        async with embedding_gate(self._cache_identity, self.provider, self._model_name):
            response = await asyncio.wait_for(
                self._client.embed(
                    texts=texts,
                    model=self._model_name,
                    input_type=cohere_input_type,
                    embedding_types=["float"],
                ),
                timeout=60,
            )
        vectors = [list(e) for e in response.embeddings.float_]
        for vector in vectors:
            if len(vector) != self._dimension:
                raise ValueError(
                    f"cohere returned vector of length {len(vector)}, "
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
        return "cohere"

    @property
    def cache_identity(self) -> str:
        return self._cache_identity
