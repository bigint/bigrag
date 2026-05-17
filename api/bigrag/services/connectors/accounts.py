from __future__ import annotations

import hmac
import secrets
import uuid
from collections.abc import Callable
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

from bigrag.db.models import ConnectorAccount, ConnectorProviderConfig, ConnectorSource
from bigrag.ids import uuid7


def configured(config: ConnectorProviderConfig | None) -> bool:
    return bool(config and config.enabled and config.client_id and config.client_secret)


async def get_provider_config(session: Any, provider: str) -> ConnectorProviderConfig | None:
    return await session.scalar(
        sa.select(ConnectorProviderConfig).where(ConnectorProviderConfig.provider == provider)
    )


def config_public(
    config: ConnectorProviderConfig | None,
    *,
    provider: str,
    callback_url: str,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "configured": configured(config),
        "enabled": bool(config.enabled) if config else False,
        "client_id": config.client_id if config else "",
        "has_client_secret": bool(config and config.client_secret),
        "callback_url": callback_url,
        "created_at": config.created_at if config else None,
        "updated_at": config.updated_at if config else None,
    }


async def upsert_provider_config(
    session: Any,
    *,
    provider: str,
    enabled: bool,
    client_id: str,
    client_secret: str | None,
) -> ConnectorProviderConfig:
    existing = await get_provider_config(session, provider)
    values = {
        "id": uuid7(),
        "provider": provider,
        "enabled": enabled,
        "client_id": client_id.strip(),
    }
    if client_secret is not None:
        values["client_secret"] = client_secret.strip() or None
    elif existing is not None:
        values["client_secret"] = existing.client_secret

    stmt = pg_insert(ConnectorProviderConfig).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ConnectorProviderConfig.provider],
        set_={
            "enabled": stmt.excluded.enabled,
            "client_id": stmt.excluded.client_id,
            "client_secret": stmt.excluded.client_secret,
            "updated_at": sa.func.now(),
        },
    ).returning(ConnectorProviderConfig)
    config = (await session.execute(stmt)).scalar_one()
    await session.commit()
    await session.refresh(config)
    return config


async def get_connector_account(
    session: Any,
    *,
    provider: str,
    user_id: str | uuid.UUID,
    tenant_id: str | None = None,
) -> ConnectorAccount | None:
    stmt = (
        sa.select(ConnectorAccount)
        .where(ConnectorAccount.provider == provider)
        .where(ConnectorAccount.user_id == uuid.UUID(str(user_id)))
    )
    if tenant_id is not None:
        stmt = stmt.where(ConnectorAccount.tenant_id == tenant_id)
    return await session.scalar(stmt)


def account_public(
    *,
    provider: str,
    config: ConnectorProviderConfig | None,
    account: ConnectorAccount | None,
    has_required_scope: Callable[[ConnectorAccount | None], bool],
) -> dict[str, Any]:
    scope_ok = has_required_scope(account)
    status = account.status if account else None
    if account and account.status == "connected" and not scope_ok:
        status = "needs_reauth"
    return {
        "provider": provider,
        "configured": configured(config),
        "connected": bool(
            account and account.status == "connected" and account.refresh_token and scope_ok
        ),
        "status": status,
        "email": account.account_email if account else None,
        "scopes": list(account.scopes or []) if account else [],
        "token_expires_at": account.token_expires_at if account else None,
        "last_connected_at": account.last_connected_at if account else None,
    }


async def prepare_oauth_account(
    session: Any,
    *,
    provider: str,
    user_id: str,
    redirect_path: str,
    redirect_origin: str | None,
    tenant_id: str | None = None,
) -> tuple[ConnectorAccount, str]:
    state = secrets.token_urlsafe(32)
    user_uuid = uuid.UUID(user_id)
    account = await get_connector_account(
        session, provider=provider, user_id=user_uuid, tenant_id=tenant_id
    )
    if account is None:
        account = ConnectorAccount(
            provider=provider,
            user_id=user_uuid,
            tenant_id=tenant_id,
            status="pending",
        )
        session.add(account)
    elif tenant_id is not None and account.tenant_id != tenant_id:
        account.tenant_id = tenant_id
    account.oauth_state = state
    account.status = "pending" if account.status != "connected" else account.status
    account.meta = {
        **dict(account.meta or {}),
        "redirect_origin": redirect_origin,
        "redirect_path": redirect_path or "/",
    }
    await session.commit()
    return account, state


async def oauth_redirect_url(account: ConnectorAccount, path: str) -> str:
    origin = str((account.meta or {}).get("redirect_origin") or "").rstrip("/")
    if not origin:
        return path
    from bigrag.services.runtime_settings import get_value

    cors_origins = await get_value("cors_origins")
    if origin not in cors_origins:
        return path
    return f"{origin}{path}"


async def oauth_error_redirect_url(
    session: Any,
    *,
    provider: str,
    user_id: str,
    state: str | None,
    path: str,
    tenant_id: str | None = None,
) -> str:
    if not state:
        return path
    account = await get_connector_account(
        session, provider=provider, user_id=user_id, tenant_id=tenant_id
    )
    if (
        account is None
        or not account.oauth_state
        or not hmac.compare_digest(account.oauth_state, state)
    ):
        return path
    return await oauth_redirect_url(account, path)


async def disconnect_account(
    session: Any,
    *,
    provider: str,
    user_id: str,
    source_error: str,
    tenant_id: str | None = None,
) -> None:
    account = await get_connector_account(
        session, provider=provider, user_id=user_id, tenant_id=tenant_id
    )
    if account is None:
        return
    account.status = "revoked"
    account.access_token = None
    account.refresh_token = None
    account.token_expires_at = None
    account.oauth_state = None
    await session.execute(
        sa.update(ConnectorSource)
        .where(ConnectorSource.account_id == account.id)
        .values(status="needs_reauth", last_error=source_error)
    )
    await session.commit()
