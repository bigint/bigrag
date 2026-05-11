from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bigrag.services.google_drive import (
    GOOGLE_PROVIDER,
    GoogleDriveAuthError,
    GoogleDriveConfigError,
    GoogleDriveError,
    build_google_oauth_url,
    complete_google_oauth,
    create_google_source,
    delete_google_source,
    disconnect_google_account,
    get_google_account,
    get_google_config,
    google_account_public,
    google_config_public,
    google_oauth_error_redirect_url,
    google_source_public,
    google_sync_job_public,
    list_google_drive_files,
    list_google_sources,
    trigger_google_sync,
    update_google_source,
    upsert_google_config,
)


@dataclass(frozen=True)
class ConnectorRuntime:
    slug: str
    provider: str
    display_name: str
    error_query_param: str
    config_error: type[Exception]
    auth_error: type[Exception]
    service_error: type[Exception]
    get_config: Callable[..., Any]
    config_public: Callable[..., dict[str, Any]]
    upsert_config: Callable[..., Any]
    get_account: Callable[..., Any]
    account_public: Callable[..., dict[str, Any]]
    build_oauth_url: Callable[..., Any]
    complete_oauth: Callable[..., Any]
    oauth_error_redirect_url: Callable[..., Any]
    disconnect_account: Callable[..., Any]
    list_files: Callable[..., Any]
    list_sources: Callable[..., Any]
    create_source: Callable[..., Any]
    update_source: Callable[..., Any]
    delete_source: Callable[..., Any]
    trigger_sync: Callable[..., Any]
    source_public: Callable[..., dict[str, Any]]
    sync_job_public: Callable[..., dict[str, Any]]


google_runtime = ConnectorRuntime(
    slug="google",
    provider=GOOGLE_PROVIDER,
    display_name="Google Drive",
    error_query_param="google_error",
    config_error=GoogleDriveConfigError,
    auth_error=GoogleDriveAuthError,
    service_error=GoogleDriveError,
    get_config=get_google_config,
    config_public=google_config_public,
    upsert_config=upsert_google_config,
    get_account=get_google_account,
    account_public=google_account_public,
    build_oauth_url=build_google_oauth_url,
    complete_oauth=complete_google_oauth,
    oauth_error_redirect_url=google_oauth_error_redirect_url,
    disconnect_account=disconnect_google_account,
    list_files=list_google_drive_files,
    list_sources=list_google_sources,
    create_source=create_google_source,
    update_source=update_google_source,
    delete_source=delete_google_source,
    trigger_sync=trigger_google_sync,
    source_public=google_source_public,
    sync_job_public=google_sync_job_public,
)

connector_runtimes = {google_runtime.slug: google_runtime}


def connector_runtime(slug: str) -> ConnectorRuntime | None:
    return connector_runtimes.get(slug)
