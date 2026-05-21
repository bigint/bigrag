from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from bigrag import config as config_module
from bigrag.logging import get_logger
from bigrag.services import runtime_settings
from bigrag.services.backup import test_backup_target
from bigrag.services.embedding import reset_embedding_semaphores
from bigrag.services.queue import ingestion_queue
from bigrag.services.runtime_setting_specs import REGISTRY
from bigrag.services.storage import (
    StorageBackend,
    build_storage_from_values,
    replace_storage_backend,
)
from bigrag.services.vector_store import VectorStore, vector_store

logger = get_logger("bigrag.runtime_settings")

BACKUP_KEYS = {
    "backup_s3_access_key_id",
    "backup_s3_bucket",
    "backup_s3_endpoint_url",
    "backup_s3_force_path_style",
    "backup_s3_prefix",
    "backup_s3_region",
    "backup_s3_secret_access_key",
}

STORAGE_CONFIG_KEYS = {
    "storage_backend",
    "storage_s3_access_key_id",
    "storage_s3_bucket",
    "storage_s3_endpoint_url",
    "storage_s3_force_path_style",
    "storage_s3_prefix",
    "storage_s3_region",
    "storage_s3_secret_access_key",
}

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
    storage_backend: StorageBackend | None = None
    vector_backend: VectorStore | None = None

    async def close(self) -> None:
        if self.storage_backend is not None:
            await self.storage_backend.close()
            self.storage_backend = None
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
        if prepared.storage_backend is not None:
            app.state.storage = await replace_storage_backend(prepared.storage_backend)
            prepared.storage_backend = None
        if prepared.vector_backend is not None:
            await vector_store.replace_with(prepared.vector_backend)
            app.state.vector_store = vector_store
            prepared.vector_backend = None
        if "embedding_concurrency" in keyset:
            reset_embedding_semaphores()
        if "ingestion_workers" in keyset:
            await ingestion_queue.resize_workers(int(prepared.values["ingestion_workers"]))
    logger.info("runtime settings applied", keys=prepared.keys)


async def _prepare_runtime_settings(
    app: Any,
    keys: list[str],
    values: dict[str, Any],
    patch: dict[str, Any],
) -> PreparedRuntimeSettings:
    prepared = PreparedRuntimeSettings(keys=keys, values=values, patch=patch)
    keyset = set(keys)
    try:
        if keyset & BACKUP_KEYS:
            await test_backup_target(values)
        if keyset & STORAGE_CONFIG_KEYS:
            prepared.storage_backend = await _prepare_storage_backend(app, values)
        if keyset & VECTOR_CONFIG_KEYS:
            prepared.vector_backend = await _prepare_vector_backend(values)
        return prepared
    except Exception:
        await prepared.close()
        raise


async def _prepare_storage_backend(app: Any, values: dict[str, Any]) -> StorageBackend:
    upload_dir = getattr(app.state.settings, "upload_dir", config_module.settings.upload_dir)
    backend = build_storage_from_values(upload_dir, values)
    try:
        if values.get("storage_backend") == "s3":
            await backend.exists("__bigrag_settings_probe__")
        return backend
    except Exception:
        await backend.close()
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
