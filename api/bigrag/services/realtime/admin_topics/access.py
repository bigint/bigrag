from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from bigrag.services.access_log.queries import access_logs_payload, access_overview_payload
from bigrag.services.audit import audit_log_payload
from bigrag.services.realtime.admin_topics._session import with_session
from bigrag.services.realtime.params import boolean, integer, string
from bigrag.services.realtime.specs import SnapshotTopic, TopicError, fixed
from bigrag.services.usage import usage_payload


def _access_overview_topic(
    websocket: WebSocket, user: dict, params: dict[str, Any]
) -> SnapshotTopic:
    window_days = integer(params, "window_days", default=7, minimum=1, maximum=90)
    snapshot_topic = f"access:overview:{window_days}"

    async def load():
        return await with_session(
            lambda session: access_overview_payload(session, window_days=window_days)
        )

    return SnapshotTopic(snapshot_topic, load, fixed(20.0))


def _access_logs_topic(websocket: WebSocket, user: dict, params: dict[str, Any]) -> SnapshotTopic:
    action = string(params, "action", max_length=100)
    actor_id = string(params, "actor_id", max_length=120)
    collection = string(params, "collection", max_length=120)
    method = string(params, "method", max_length=10)
    path = string(params, "path", max_length=300)
    status_family = string(params, "status_family", max_length=3)
    success = boolean(params, "success")
    limit = integer(params, "limit", default=100, minimum=1, maximum=1000)
    offset = integer(params, "offset", default=0, minimum=0)
    if status_family is not None and status_family not in {"1xx", "2xx", "3xx", "4xx", "5xx"}:
        raise TopicError("status_family must be one of 1xx, 2xx, 3xx, 4xx, or 5xx")
    snapshot_topic = ":".join(
        [
            "access:logs",
            action or "*",
            actor_id or "*",
            collection or "*",
            method or "*",
            path or "*",
            status_family or "*",
            str(success),
            str(limit),
            str(offset),
        ]
    )

    async def load():
        return await with_session(
            lambda session: access_logs_payload(
                session,
                action=action,
                actor_id=actor_id,
                collection=collection,
                method=method,
                path=path,
                status_family=status_family,
                success=success,
                limit=limit,
                offset=offset,
                cursor=None,
                include_total=False,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(20.0))


def _audit_topic(websocket: WebSocket, user: dict, params: dict[str, Any]) -> SnapshotTopic:
    action = string(params, "action", max_length=100)
    actor_id = string(params, "actor_id", max_length=120)
    resource_type = string(params, "resource_type", max_length=50)
    limit = integer(params, "limit", default=100, minimum=1, maximum=1000)
    offset = integer(params, "offset", default=0, minimum=0)
    snapshot_topic = (
        f"audit:{action or '*'}:{actor_id or '*'}:{resource_type or '*'}:{limit}:{offset}"
    )

    async def load():
        return await with_session(
            lambda session: audit_log_payload(
                session,
                action=action,
                actor_id=actor_id,
                resource_type=resource_type,
                limit=limit,
                offset=offset,
                cursor=None,
                include_total=False,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(60.0))


def _usage_topic(websocket: WebSocket, user: dict, params: dict[str, Any]) -> SnapshotTopic:
    window_days = integer(params, "window_days", default=30, minimum=1, maximum=365)
    snapshot_topic = f"usage:{window_days}"

    async def load():
        return await with_session(lambda session: usage_payload(session, window_days=window_days))

    return SnapshotTopic(snapshot_topic, load, fixed(60.0))
