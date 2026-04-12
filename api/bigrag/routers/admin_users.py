"""Admin endpoints for managing other admin accounts."""

from __future__ import annotations

import uuid

from asyncpg.exceptions import UniqueViolationError
from fastapi import APIRouter, Depends, HTTPException, Query

from bigrag.database import build_update, db
from bigrag.logging import get_logger
from bigrag.middleware.auth import require_session
from bigrag.models.auth import (
    CreateUserRequest,
    UpdateUserRequest,
    UserListResponse,
    UserResponse,
)
from bigrag.models.common import StatusResponse
from bigrag.services.auth import hash_password

logger = get_logger("bigrag.routers.admin_users")

router = APIRouter(prefix="/v1/admin/users", tags=["admin:users"])


def _user_response(row: dict) -> UserResponse:
    return UserResponse(
        id=str(row["id"]),
        email=row["email"],
        display_name=row["display_name"],
        role=row["role"],
        last_login_at=row.get("last_login_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("", response_model=UserListResponse)
async def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_session),
) -> UserListResponse:
    rows = await db.fetch(
        "SELECT * FROM users ORDER BY created_at ASC LIMIT $1 OFFSET $2",
        limit,
        offset,
    )
    total = (await db.fetchrow("SELECT COUNT(*) AS cnt FROM users"))["cnt"]
    return UserListResponse(users=[_user_response(dict(r)) for r in rows], total=total)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: CreateUserRequest,
    _: dict = Depends(require_session),
) -> UserResponse:
    try:
        row = await db.fetchrow(
            """
            INSERT INTO users (id, email, password_hash, display_name, role)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            uuid.uuid4(),
            body.email.lower(),
            hash_password(body.password),
            body.display_name,
            body.role,
        )
    except UniqueViolationError as e:
        raise HTTPException(status_code=409, detail="Email is already registered") from e
    logger.info(f"User created: {body.email} role={body.role}")
    return _user_response(dict(row))


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    admin: dict = Depends(require_session),
) -> UserResponse:
    try:
        target_id = uuid.UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="User not found") from e

    fields: dict = {}
    if body.display_name is not None:
        fields["display_name"] = body.display_name
    if body.role is not None:
        fields["role"] = body.role
    if body.password is not None:
        fields["password_hash"] = hash_password(body.password)

    if not fields:
        row = await db.fetchrow("SELECT * FROM users WHERE id = $1", target_id)
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return _user_response(dict(row))

    sql, params = build_update("users", fields, "id", target_id)
    row = await db.fetchrow(sql, *params)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    if body.password is not None:
        await db.execute("DELETE FROM sessions WHERE user_id = $1", target_id)

    logger.info(f"User updated: id={user_id} by={admin['email']} fields={list(fields)}")
    return _user_response(dict(row))


@router.delete("/{user_id}", response_model=StatusResponse)
async def delete_user(
    user_id: str,
    admin: dict = Depends(require_session),
) -> StatusResponse:
    try:
        target_id = uuid.UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="User not found") from e

    if str(target_id) == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    remaining = await db.fetchrow(
        "SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin' AND id <> $1",
        target_id,
    )
    if remaining["cnt"] == 0:
        raise HTTPException(status_code=400, detail="Cannot delete the last admin")

    row = await db.fetchrow("DELETE FROM users WHERE id = $1 RETURNING id", target_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    logger.info(f"User deleted: id={user_id} by={admin['email']}")
    return StatusResponse(status="ok", message="User deleted")
