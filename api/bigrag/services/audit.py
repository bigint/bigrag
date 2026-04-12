"""Audit log service.

Records privileged actions with actor, resource, metadata, and
request provenance so SOC2-style auditors have a trail. Writes are
fire-and-forget so a logging blip never fails a user request.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request

from bigrag.database import db
from bigrag.logging import get_logger
from bigrag.utils import safe_create_task

logger = get_logger("bigrag.audit")


async def _insert(
    *,
    actor_id: str | None,
    actor_email: str | None,
    api_key_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    metadata: dict,
    ip: str | None,
    user_agent: str | None,
) -> None:
    try:
        await db.execute(
            """
            INSERT INTO audit_log
                (actor_id, actor_email, api_key_id, action, resource_type,
                 resource_id, metadata, ip, user_agent)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            uuid.UUID(actor_id) if actor_id else None,
            actor_email,
            uuid.UUID(api_key_id) if api_key_id else None,
            action,
            resource_type,
            resource_id,
            metadata,
            ip,
            user_agent,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "audit: insert failed — falling back to stderr",
            action=action,
            resource_type=resource_type,
            error=str(exc),
        )


def record(
    request: Request,
    *,
    user: dict | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record an audit entry. Non-blocking — runs in a background task."""
    client = request.client
    ip = client[0] if client else None
    user_agent = request.headers.get("user-agent")
    actor_id = user.get("id") if user else None
    actor_email = user.get("email") if user else None
    api_key_id = user.get("api_key_id") if user else None

    safe_create_task(
        _insert(
            actor_id=actor_id,
            actor_email=actor_email,
            api_key_id=api_key_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata or {},
            ip=ip,
            user_agent=user_agent,
        ),
        name="audit_insert",
    )
