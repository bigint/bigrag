from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta
from typing import Any

import httpx
import sqlalchemy as sa

from bigrag.db.models import ConnectorAccount, ConnectorProviderConfig, ConnectorSource
from bigrag.services.connector_core import (
    account_public,
    config_public,
    configured,
    disconnect_account,
    get_connector_account,
    get_provider_config,
    oauth_error_redirect_url,
    oauth_redirect_url,
    prepare_oauth_account,
    upsert_provider_config,
    utcnow,
)
from bigrag.services.connectors.google_drive_client import google_drive_client
from bigrag.services.connectors.google_drive_types import (
    GOOGLE_OAUTH_SCOPES,
    GOOGLE_PROVIDER,
    GoogleDriveAuthError,
    GoogleDriveConfigError,
    _account_has_required_scope,
    google_drive_file_public,
)

_REFRESH_LOCKS: dict[uuid.UUID, asyncio.Lock] = {}


def _refresh_lock_for(account_id: uuid.UUID) -> asyncio.Lock:
    lock = _REFRESH_LOCKS.get(account_id)
    if lock is None:
        lock = asyncio.Lock()
        _REFRESH_LOCKS[account_id] = lock
    return lock


async def get_google_config(session) -> ConnectorProviderConfig | None:
    return await get_provider_config(session, GOOGLE_PROVIDER)


def google_config_public(
    config: ConnectorProviderConfig | None,
    *,
    callback_url: str,
) -> dict[str, Any]:
    return config_public(config, provider=GOOGLE_PROVIDER, callback_url=callback_url)


async def upsert_google_config(
    session,
    *,
    enabled: bool,
    client_id: str,
    client_secret: str | None,
) -> ConnectorProviderConfig:
    return await upsert_provider_config(
        session,
        provider=GOOGLE_PROVIDER,
        enabled=enabled,
        client_id=client_id,
        client_secret=client_secret,
    )


async def get_google_account(session, user_id: str) -> ConnectorAccount | None:
    return await get_connector_account(session, provider=GOOGLE_PROVIDER, user_id=user_id)


def google_account_public(
    *,
    config: ConnectorProviderConfig | None,
    account: ConnectorAccount | None,
) -> dict[str, Any]:
    return account_public(
        provider=GOOGLE_PROVIDER,
        config=config,
        account=account,
        has_required_scope=_account_has_required_scope,
    )


async def build_google_oauth_url(
    session,
    *,
    user_id: str,
    redirect_uri: str,
    redirect_path: str,
    redirect_origin: str | None = None,
) -> str:
    config = await get_google_config(session)
    if not configured(config) or config is None:
        raise GoogleDriveConfigError("Google Drive connector is not configured")

    _, state = await prepare_oauth_account(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        redirect_path=redirect_path,
        redirect_origin=redirect_origin,
    )

    params = {
        "client_id": config.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    query = httpx.QueryParams(params)
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


async def complete_google_oauth(
    session,
    *,
    user_id: str,
    code: str,
    state: str,
    redirect_uri: str,
) -> str:
    config = await get_google_config(session)
    if not configured(config) or config is None:
        raise GoogleDriveConfigError("Google Drive connector is not configured")

    account = await get_google_account(session, user_id)
    if account is None or not account.oauth_state or account.oauth_state != state:
        raise GoogleDriveAuthError("Invalid Google OAuth state")

    token_payload = await google_drive_client.exchange_code(
        config=config,
        code=code,
        redirect_uri=redirect_uri,
    )
    access_token = token_payload.get("access_token")
    refresh_token = token_payload.get("refresh_token") or account.refresh_token
    if not access_token or not refresh_token:
        raise GoogleDriveAuthError(
            "Google did not return a refresh token. Reconnect and approve offline access."
        )

    info = await google_drive_client.userinfo(access_token)
    expires_in = int(token_payload.get("expires_in") or 3600)
    account.account_email = info.get("email") or account.account_email
    account.access_token = access_token
    account.refresh_token = refresh_token
    account.token_expires_at = utcnow() + timedelta(seconds=max(60, expires_in - 60))
    account.scopes = str(token_payload.get("scope") or " ".join(GOOGLE_OAUTH_SCOPES)).split()
    account.status = "connected"
    account.oauth_state = None
    account.last_connected_at = utcnow()
    redirect_path = await oauth_redirect_url(
        account,
        str((account.meta or {}).get("redirect_path") or "/"),
    )
    await session.commit()
    return redirect_path


async def google_oauth_error_redirect_url(
    session,
    *,
    user_id: str,
    state: str | None,
    path: str,
) -> str:
    return await oauth_error_redirect_url(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        state=state,
        path=path,
    )


async def disconnect_google_account(session, *, user_id: str) -> None:
    await disconnect_account(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        source_error="Google account disconnected",
    )


async def _access_token_for_account(
    session,
    *,
    config: ConnectorProviderConfig,
    account: ConnectorAccount,
) -> str:
    if account.status != "connected" or not account.refresh_token:
        raise GoogleDriveAuthError("Google Drive account needs reconnection")
    if not _account_has_required_scope(account):
        account.status = "needs_reauth"
        account.access_token = None
        await session.execute(
            sa.update(ConnectorSource)
            .where(ConnectorSource.account_id == account.id)
            .values(
                status="needs_reauth",
                last_error="Reconnect Google Drive to grant read-only access",
            )
        )
        await session.commit()
        raise GoogleDriveAuthError("Reconnect Google Drive to grant read-only access")

    if account.access_token and account.token_expires_at and account.token_expires_at > utcnow():
        return account.access_token

    lock = _refresh_lock_for(account.id)
    async with lock:
        await session.refresh(account)
        if (
            account.access_token
            and account.token_expires_at
            and account.token_expires_at > utcnow()
        ):
            return account.access_token

        try:
            payload = await google_drive_client.refresh_access_token(
                config=config,
                refresh_token=account.refresh_token,
            )
        except GoogleDriveAuthError:
            account.status = "needs_reauth"
            account.access_token = None
            await session.execute(
                sa.update(ConnectorSource)
                .where(ConnectorSource.account_id == account.id)
                .values(status="needs_reauth", last_error="Google account needs reconnection")
            )
            await session.commit()
            raise

        account.access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in") or 3600)
        account.token_expires_at = utcnow() + timedelta(seconds=max(60, expires_in - 60))
        if payload.get("scope"):
            account.scopes = str(payload["scope"]).split()
        await session.commit()
        return account.access_token


async def list_google_drive_files(
    session,
    *,
    user_id: str,
    parent_id: str = "root",
    query: str | None = None,
    page_token: str | None = None,
    page_size: int = 100,
) -> dict[str, Any]:
    config = await get_google_config(session)
    account = await get_google_account(session, user_id)
    if not configured(config) or config is None:
        raise GoogleDriveConfigError("Google Drive connector is not configured")
    if account is None or account.status != "connected":
        raise GoogleDriveAuthError("Connect Google Drive before browsing files")
    try:
        access_token = await _access_token_for_account(session, config=config, account=account)
        files, next_page_token = await google_drive_client.list_files(
            access_token=access_token,
            parent_id=parent_id,
            query=query,
            page_token=page_token,
            page_size=page_size,
        )
    except GoogleDriveAuthError:
        account.status = "needs_reauth"
        account.access_token = None
        await session.commit()
        raise
    return {
        "provider": GOOGLE_PROVIDER,
        "parent_id": parent_id or "root",
        "query": query or "",
        "files": [google_drive_file_public(file) for file in files],
        "next_page_token": next_page_token,
    }
