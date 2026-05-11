from __future__ import annotations

from bigrag.services.collection_config import get_embedding_model_for


def test_get_embedding_model_for_uses_preset_api_key(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_embedding_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("bigrag.services.embedding.get_embedding_model", fake_get_embedding_model)

    get_embedding_model_for(
        {
            "name": "test",
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "dimension": 1536,
            "embedding_api_key": None,
            "embedding_base_url": None,
            "embedding_preset_id": "preset-1",
            "embedding_preset_api_key": "preset-key",
            "embedding_preset_base_url": None,
        }
    )

    assert captured["api_key"] == "preset-key"
