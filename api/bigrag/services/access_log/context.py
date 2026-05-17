from __future__ import annotations

import uuid
from typing import Any

from starlette.requests import Request

from bigrag.ids import uuid7
from bigrag.services.access_log.payload import _safe_metadata


def _uuid_or_none(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        return None


def set_context(
    request: Request,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    collection_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    context = dict(getattr(request.state, "access_log_context", {}) or {})
    if action is not None:
        context["action"] = action
    if resource_type is not None:
        context["resource_type"] = resource_type
    if resource_id is not None:
        context["resource_id"] = resource_id
    if collection_name is not None:
        context["collection_name"] = collection_name
    if metadata:
        existing = dict(context.get("metadata") or {})
        existing.update(metadata)
        context["metadata"] = existing
    request.state.access_log_context = context


def build_row(
    *,
    actor_id: str | None,
    actor_email: str | None,
    api_key_id: str | None,
    api_key_name: str | None,
    auth_method: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    collection_name: str | None,
    method: str,
    path: str,
    route: str | None,
    status_code: int,
    latency_ms: float,
    request_id: str | None,
    metadata: dict[str, Any],
    ip: str | None,
    user_agent: str | None,
) -> dict[str, Any]:
    return {
        "id": uuid7(),
        "actor_id": _uuid_or_none(actor_id),
        "actor_email": actor_email,
        "api_key_id": _uuid_or_none(api_key_id),
        "api_key_name": api_key_name,
        "auth_method": auth_method,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "collection_name": collection_name,
        "method": method,
        "path": path,
        "route": route,
        "status_code": status_code,
        "success": 200 <= status_code < 400,
        "latency_ms": latency_ms,
        "request_id": request_id,
        "meta": _safe_metadata(metadata),
        "ip": ip,
        "user_agent": user_agent,
    }
