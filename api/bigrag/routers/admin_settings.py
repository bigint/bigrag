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
from bigrag.services.runtime_settings import (
    get_public_settings,
    reset_settings,
    update_settings,
)
from bigrag.services.runtime_settings_apply import (
    apply_prepared_runtime_settings,
    prepare_runtime_settings_reset,
    prepare_runtime_settings_update,
)

router = APIRouter(prefix="/v1/admin/settings", tags=["admin:settings"])


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
    prepared = None
    try:
        prepared = await prepare_runtime_settings_update(request.app, body.values)
        changed = await update_settings(session, body.values, updated_by=user_id)
        await apply_prepared_runtime_settings(request.app, prepared)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {exc.args[0]}") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if prepared is not None:
            await prepared.close()
    audit.record(
        request,
        user=admin,
        action="instance_settings.update",
        resource_type="instance_settings",
        resource_id="instance",
        metadata={"keys": changed},
    )
    return await get_public_settings(session)


@router.post("/test", response_model=InstanceSettingsTestResponse)
async def test_instance_settings(
    body: TestInstanceSettingsRequest,
    request: Request,
    _: dict = Depends(require_admin_session),
) -> InstanceSettingsTestResponse:
    prepared = None
    try:
        prepared = await prepare_runtime_settings_update(request.app, body.values)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {exc.args[0]}") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if prepared is not None:
            await prepared.close()
    return InstanceSettingsTestResponse(
        status="ok",
        checked=list(body.values),
        message="Settings validated",
    )


@router.post("/reset", response_model=StatusResponse)
async def reset_instance_settings(
    body: ResetInstanceSettingsRequest,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    prepared = None
    try:
        prepared = await prepare_runtime_settings_reset(request.app, body.keys)
        reset_keys = await reset_settings(session, body.keys)
        await apply_prepared_runtime_settings(request.app, prepared)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {exc.args[0]}") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if prepared is not None:
            await prepared.close()
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
