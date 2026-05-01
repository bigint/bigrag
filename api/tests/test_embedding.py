from __future__ import annotations

import pytest

from bigrag.config import settings
from bigrag.services import embedding


def test_openai_compatible_uses_openai_embedding_client(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeOpenAIEmbedding:
        def __init__(self, model_name, api_key=None, dimension=1536, base_url=None) -> None:
            calls.append(
                {
                    "model_name": model_name,
                    "api_key": api_key,
                    "dimension": dimension,
                    "base_url": base_url,
                }
            )

        @property
        def dimension(self) -> int:
            return 768

        @property
        def name(self) -> str:
            return "nomic-embed-text"

        @property
        def provider(self) -> str:
            return "openai_compatible"

    embedding._models.clear()
    monkeypatch.setattr(embedding, "OpenAIEmbedding", FakeOpenAIEmbedding)
    monkeypatch.setattr(settings, "allowed_embedding_base_urls", ["http://ollama:11434/v1"])

    model = embedding.get_embedding_model(
        provider="openai_compatible",
        model_name="nomic-embed-text",
        api_key="dummy",
        dimension=768,
        base_url="http://ollama:11434/v1",
    )

    assert model.dimension == 768
    assert calls == [
        {
            "model_name": "nomic-embed-text",
            "api_key": "dummy",
            "dimension": 768,
            "base_url": "http://ollama:11434/v1",
        }
    ]


def test_openai_compatible_requires_base_url() -> None:
    embedding._models.clear()

    with pytest.raises(ValueError, match="base_url is required"):
        embedding.get_embedding_model(
            provider="openai_compatible",
            model_name="nomic-embed-text",
            api_key="dummy",
            dimension=768,
        )
