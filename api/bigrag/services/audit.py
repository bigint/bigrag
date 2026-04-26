from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request

from bigrag.db.engine import session_factory
from bigrag.db.models import AuditLog
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
        async with session_factory()() as session:
            session.add(
                AuditLog(
                    actor_id=uuid.UUID(actor_id) if actor_id else None,
                    actor_email=actor_email,
                    api_key_id=uuid.UUID(api_key_id) if api_key_id else None,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    meta=metadata,
                    ip=ip,
                    user_agent=user_agent,
                )
            )
            await session.commit()
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
