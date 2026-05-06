from __future__ import annotations

from bigrag.config import settings
from bigrag.exceptions import ValidationError


def get_embedding_model_for(collection: dict):
    from bigrag.services.embedding import get_embedding_model

    provider = collection["embedding_provider"]
    if collection.get("embedding_preset_id"):
        api_key = (
            collection.get("embedding_preset_api_key")
            or collection.get("embedding_api_key")
            or settings.embedding_api_key
        )
        base_url = (
            collection.get("embedding_preset_base_url")
            or collection.get("embedding_base_url")
            or settings.embedding_base_url
        )
    else:
        api_key = collection.get("embedding_api_key") or settings.embedding_api_key
        base_url = collection.get("embedding_base_url") or settings.embedding_base_url
    if not api_key and provider in ("openai", "openai_compatible", "cohere", "voyage"):
        raise ValidationError(
            f"Collection '{collection['name']}' uses "
            f"'{provider}' embeddings but no API key is configured. "
            "Link the collection to an embedding preset with a valid key, "
            "or save a key on the collection itself."
        )

    return get_embedding_model(
        provider=provider,
        model_name=collection["embedding_model"],
        dimension=collection["dimension"],
        api_key=api_key,
        base_url=base_url,
    )


def get_reranking_config(collection: dict) -> dict:
    return {
        "enabled": collection.get("reranking_enabled", False),
        "model": collection.get("reranking_model", "rerank-v3.5"),
        "api_key": collection.get("reranking_api_key") or settings.embedding_api_key,
    }
