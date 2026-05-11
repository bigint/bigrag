from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.session import get_session
from bigrag.middleware.auth import require_admin_session
from bigrag.models.common import StatusResponse
from bigrag.models.instance_settings import (
    InstanceSettingsResponse,
    InstanceSettingsTestResponse,
    ResetInstanceSettingsRequest,
    TestInstanceSettingsRequest,
    UpdateInstanceSettingsRequest,
)
from bigrag.services import audit, embedding_cache
from bigrag.services.backup import test_backup_target
from bigrag.services.queue import ingestion_queue
from bigrag.services.runtime_settings import (
    all_runtime_values,
    get_public_settings,
    reset_settings,
    update_settings,
    validate_setting_value,
)
from bigrag.services.storage import build_storage_from_values
from bigrag.services.vector_store import VectorStore

router = APIRouter(prefix="/admin/settings", tags=["admin:settings"])


@router.get("", response_model=InstanceSettingsResponse)
async def list_instance_settings(
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> InstanceSettingsResponse:
    return await get_public_settings(session)


@router.put("", response_model=InstanceSettingsResponse)
async def update_instance_settings(
    body: UpdateInstanceSettingsRequest,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> InstanceSettingsResponse:
    user_id = UUID(admin["id"]) if admin.get("id") else None
    try:
        changed = await update_settings(session, body.values, updated_by=user_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {exc.args[0]}") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Settings update failed: {exc.__class__.__name__}: {exc}",
        ) from exc
    audit.record(
        request,
        user=admin,
        action="instance_settings.update",
        resource_type="instance_settings",
        resource_id="instance",
        metadata={"keys": changed},
    )
    if "ingestion_workers" in changed:
        await ingestion_queue.resize_workers(int(body.values["ingestion_workers"]))
    return await get_public_settings(session)


@router.post("/test", response_model=InstanceSettingsTestResponse)
async def test_instance_settings(
    body: TestInstanceSettingsRequest,
    _: dict = Depends(require_admin_session),
) -> InstanceSettingsTestResponse:
    checked: list[str] = []
    try:
        for key, value in body.values.items():
            validate_setting_value(key, value)
            checked.append(key)
        if any(key.startswith("storage_") for key in body.values):
            storage_values = await all_runtime_values()
            storage_values.update(
                {
                    key: validate_setting_value(key, body.values[key])
                    for key in body.values
                    if key.startswith("storage_")
                }
            )
            if storage_values.get("storage_backend") == "s3":
                probe = build_storage_from_values("__settings_test__", storage_values)
                try:
                    await probe.exists("__bigrag_settings_probe__")
                finally:
                    await probe.close()
        if any(key.startswith("backup_") for key in body.values):
            backup_values = await all_runtime_values()
            backup_values.update(
                {
                    key: validate_setting_value(key, body.values[key])
                    for key in body.values
                    if key.startswith("backup_")
                }
            )
            await test_backup_target(backup_values)
        vector_keys = {
            "qdrant_api_key",
            "qdrant_connect_timeout_seconds",
            "qdrant_required",
            "qdrant_search_ef",
            "qdrant_url",
            "s3_vectors_access_key_id",
            "s3_vectors_bucket",
            "s3_vectors_index_prefix",
            "s3_vectors_region",
            "s3_vectors_secret_access_key",
            "turbopuffer_api_key",
            "turbopuffer_namespace_prefix",
            "turbopuffer_region",
            "vector_store_provider",
        }
        if any(key in vector_keys for key in body.values):
            vector_values = await all_runtime_values()
            vector_values.update(
                {
                    key: validate_setting_value(key, body.values[key])
                    for key in body.values
                    if key in vector_keys
                }
            )
            probe = VectorStore()
            probe.configure(
                provider=vector_values["vector_store_provider"],
                qdrant_url=vector_values["qdrant_url"],
                qdrant_api_key=vector_values["qdrant_api_key"],
                connect_timeout_seconds=vector_values["qdrant_connect_timeout_seconds"],
                search_ef=vector_values["qdrant_search_ef"],
                s3_vectors_bucket=vector_values["s3_vectors_bucket"],
                s3_vectors_region=vector_values["s3_vectors_region"],
                s3_vectors_index_prefix=vector_values["s3_vectors_index_prefix"],
                s3_vectors_access_key_id=vector_values["s3_vectors_access_key_id"],
                s3_vectors_secret_access_key=vector_values["s3_vectors_secret_access_key"],
                turbopuffer_api_key=vector_values["turbopuffer_api_key"],
                turbopuffer_region=vector_values["turbopuffer_region"],
                turbopuffer_namespace_prefix=vector_values["turbopuffer_namespace_prefix"],
            )
            try:
                probe.connect()
                await probe.health_check()
            finally:
                await probe.close()
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InstanceSettingsTestResponse(
        status="ok",
        checked=checked,
        message="Settings validated",
    )


@router.post("/reset", response_model=StatusResponse)
async def reset_instance_settings(
    body: ResetInstanceSettingsRequest,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    try:
        reset_keys = await reset_settings(session, body.keys)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {exc.args[0]}") from exc
    audit.record(
        request,
        user=admin,
        action="instance_settings.reset",
        resource_type="instance_settings",
        resource_id="instance",
        metadata={"keys": reset_keys},
    )
    return StatusResponse(status="ok", message="Settings reset")


@router.post("/embedding-cache/purge", response_model=StatusResponse)
async def purge_embedding_cache(
    request: Request,
    admin: dict = Depends(require_admin_session),
) -> StatusResponse:
    purged = await embedding_cache.purge_all()
    audit.record(
        request,
        user=admin,
        action="embedding_cache.purge",
        resource_type="embedding_cache",
        resource_id="embedding_cache",
        metadata={"purged": purged},
    )
    return StatusResponse(status="ok", message=f"Purged {purged} embedding cache rows")
