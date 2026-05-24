from __future__ import annotations

from abc import ABC, abstractmethod

from bigrag.logging import get_logger

logger = get_logger("bigrag.embedding")

_TOKEN_LIMITS: dict[str, int] = {
    "text-embedding-3-small": 8000,
    "text-embedding-3-large": 8000,
    "text-embedding-ada-002": 8000,
    "embed-english-v3.0": 500,
    "embed-multilingual-v3.0": 500,
    "embed-english-light-v3.0": 500,
    "embed-multilingual-light-v3.0": 500,
    "voyage-3-large": 32000,
    "voyage-3.5": 32000,
    "voyage-3.5-lite": 32000,
    "voyage-code-3": 32000,
    "voyage-finance-2": 32000,
    "voyage-law-2": 16000,
}


def truncate_to_tokens(
    texts: list[str],
    model: str | None,
    max_tokens: int | None = None,
) -> tuple[list[str], list[bool]]:

    limit = max_tokens
    if limit is None and model:
        limit = _TOKEN_LIMITS.get(model)
    if limit is None:
        limit = 8000

    try:
        import tiktoken

        try:
            enc = (
                tiktoken.encoding_for_model(model)
                if model
                else tiktoken.get_encoding("cl100k_base")
            )
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        out_texts: list[str] = []
        warnings: list[bool] = []
        for text in texts:
            tokens = enc.encode(text)
            if len(tokens) > limit:
                out_texts.append(enc.decode(tokens[:limit]))
                warnings.append(True)
            else:
                out_texts.append(text)
                warnings.append(False)
        return out_texts, warnings
    except Exception:
        char_limit = limit * 4
        out_texts = []
        warnings = []
        for text in texts:
            if len(text) > char_limit:
                out_texts.append(text[:char_limit])
                warnings.append(True)
            else:
                out_texts.append(text)
                warnings.append(False)
        return out_texts, warnings


class EmbeddingModel(ABC):
    @abstractmethod
    async def embed(
        self, texts: list[str], *, input_type: str = "document"
    ) -> list[list[float]]: ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def provider(self) -> str: ...

    @property
    @abstractmethod
    def cache_identity(self) -> str: ...
