from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from bigrag import config as config_module
from bigrag.logging import get_logger
from bigrag.services import runtime_settings
from bigrag.services.embedding import reset_embedding_limiters
from bigrag.services.runtime_setting_specs import REGISTRY
from bigrag.services.vector_store import VectorStore, vector_store

logger = get_logger("bigrag.runtime_settings")

VECTOR_CONFIG_KEYS = {
    "turbopuffer_api_key",
    "turbopuffer_base_url",
    "turbopuffer_namespace_prefix",
    "turbopuffer_region",
}

_apply_lock = asyncio.Lock()


@dataclass
class PreparedRuntimeSettings:
    keys: list[str]
    values: dict[str, Any]
    patch: dict[str, Any]
    vector_backend: VectorStore | None = None

    async def close(self) -> None:
        if self.vector_backend is not None:
            await self.vector_backend.close()
            self.vector_backend = None


async def prepare_runtime_settings_update(
    app: Any,
    raw_values: dict[str, Any],
    *,
    values_are_validated: bool = False,
) -> PreparedRuntimeSettings:
    values = await runtime_settings.all_runtime_values()
    patch: dict[str, Any] = {}
    keys: list[str] = []
    for key, raw_value in raw_values.items():
        patch[key] = (
            raw_value
            if values_are_validated
            else runtime_settings.validate_setting_value(key, raw_value)
        )
        keys.append(key)
    values.update(patch)
    return await _prepare_runtime_settings(app, keys, values, patch)


async def prepare_runtime_settings_reset(app: Any, keys: list[str]) -> PreparedRuntimeSettings:
    target_keys = list(REGISTRY) if not keys else list(keys)
    unknown = [key for key in target_keys if key not in REGISTRY]
    if unknown:
        raise KeyError(unknown[0])
    values = await runtime_settings.all_runtime_values()
    values.update(runtime_settings.default_values(target_keys))
    return await _prepare_runtime_settings(app, target_keys, values, {})


async def apply_prepared_runtime_settings(app: Any, prepared: PreparedRuntimeSettings) -> None:
    keyset = set(prepared.keys)
    async with _apply_lock:
        _apply_settings_object(app, prepared.values)
        if prepared.vector_backend is not None:
            await vector_store.replace_with(prepared.vector_backend)
            app.state.vector_store = vector_store
            prepared.vector_backend = None
        if "embedding_concurrency" in keyset:
            reset_embedding_limiters()
    logger.info("runtime settings applied", keys=prepared.keys)


async def _prepare_runtime_settings(
    app: Any,
    keys: list[str],
    values: dict[str, Any],
    patch: dict[str, Any],
) -> PreparedRuntimeSettings:
    prepared = PreparedRuntimeSettings(keys=keys, values=values, patch=patch)
    try:
        if set(keys) & VECTOR_CONFIG_KEYS:
            prepared.vector_backend = await _prepare_vector_backend(values)
        return prepared
    except Exception:
        await prepared.close()
        raise


async def _prepare_vector_backend(values: dict[str, Any]) -> VectorStore:
    store = VectorStore()
    _configure_vector_store(store, values)
    try:
        if values.get("turbopuffer_api_key"):
            store.connect()
            await store.health_check()
        return store
    except Exception:
        await store.close()
        raise


def _configure_vector_store(store: VectorStore, values: dict[str, Any]) -> None:
    store.configure(
        turbopuffer_api_key=values["turbopuffer_api_key"],
        turbopuffer_base_url=values["turbopuffer_base_url"],
        turbopuffer_region=values["turbopuffer_region"],
        turbopuffer_namespace_prefix=values["turbopuffer_namespace_prefix"],
    )


def _apply_settings_object(app: Any, values: dict[str, Any]) -> None:
    settings = app.state.settings
    for key, value in values.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
        if hasattr(config_module.settings, key):
            setattr(config_module.settings, key, value)
