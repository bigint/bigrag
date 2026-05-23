from __future__ import annotations

from bigrag.services.event_bus import event_bus


def connector_sources_event_key(provider: str, collection_name: str | None = None) -> str:
    return f"connector:{provider}:sources:{collection_name or 'all'}"


def connector_sync_jobs_event_key(
    provider: str,
    collection_name: str | None = None,
    source_id: str | None = None,
) -> str:
    return f"connector:{provider}:sync-jobs:{collection_name or 'all'}:{source_id or 'all'}"


def notify_connector_sources(provider: str, collection_name: str | None = None) -> None:
    keys = {connector_sources_event_key(provider)}
    if collection_name:
        keys.add(connector_sources_event_key(provider, collection_name))
    for key in keys:
        event_bus.notify(key)


def notify_connector_sync_jobs(
    provider: str,
    collection_name: str | None = None,
    source_id: str | None = None,
) -> None:
    keys = {connector_sync_jobs_event_key(provider)}
    if collection_name:
        keys.add(connector_sync_jobs_event_key(provider, collection_name))
    if source_id:
        keys.add(connector_sync_jobs_event_key(provider, None, source_id))
    if collection_name and source_id:
        keys.add(connector_sync_jobs_event_key(provider, collection_name, source_id))
    for key in keys:
        event_bus.notify(key)


def notify_connector_state(
    provider: str,
    collection_name: str | None = None,
    source_id: str | None = None,
) -> None:
    notify_connector_sources(provider, collection_name)
    notify_connector_sync_jobs(provider, collection_name, source_id)
