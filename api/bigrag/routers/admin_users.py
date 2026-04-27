from __future__ import annotations

import uuid

import sqlalchemy as sa
from asyncpg.exceptions import UniqueViolationError
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Session as DbSession
from bigrag.db.models import User
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import require_admin_session
from bigrag.models.auth import (
    CreateUserRequest,
    UpdateUserRequest,
    UserListResponse,
    UserResponse,
)
from bigrag.models.common import StatusResponse
from bigrag.services import audit
from bigrag.services.auth import hash_password

logger = get_logger("bigrag.routers.admin_users")

router = APIRouter(prefix="/v1/admin/users", tags=["admin:users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> UserListResponse:
    users = (
        await session.scalars(
            sa.select(User).order_by(User.created_at.asc()).limit(limit).offset(offset)
        )
    ).all()
    total = await session.scalar(sa.select(sa.func.count()).select_from(User))
    return UserListResponse(users=[UserResponse.from_user(u) for u in users], total=total or 0)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: CreateUserRequest,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    user = User(
        id=uuid.uuid4(),
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role=body.role,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if isinstance(e.orig, UniqueViolationError) or "unique" in str(e.orig).lower():
            raise HTTPException(status_code=409, detail="Email is already registered") from e
        raise
    await session.refresh(user)
    logger.info(f"User created: {body.email} role={body.role}")
    audit.record(
        request,
        user=admin,
        action="user.create",
        resource_type="user",
        resource_id=str(user.id),
        metadata={"email": user.email, "role": user.role},
    )
    return UserResponse.from_user(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    try:
        target_id = uuid.UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="User not found") from e

    target = await session.get(User, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    password_changed = False
    fields: list[str] = []
    if body.display_name is not None:
        target.display_name = body.display_name
        fields.append("display_name")
    if body.role is not None:
        target.role = body.role
        fields.append("role")
    if body.password is not None:
        target.password_hash = hash_password(body.password)
        password_changed = True
        fields.append("password")

    if password_changed:
        await session.execute(sa.delete(DbSession).where(DbSession.user_id == target_id))
    await session.commit()
    await session.refresh(target)

    logger.info(
        f"User updated: id={user_id} by={admin['email']} "
        f"display_name={body.display_name is not None} "
        f"role={body.role is not None} password={password_changed}"
    )
    audit.record(
        request,
        user=admin,
        action="user.update",
        resource_type="user",
        resource_id=str(target.id),
        metadata={"email": target.email, "fields": fields},
    )
    return UserResponse.from_user(target)


@router.delete("/{user_id}", response_model=StatusResponse)
async def delete_user(
    user_id: str,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    try:
        target_id = uuid.UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="User not found") from e

    if str(target_id) == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    target = await session.get(User, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    deleted_email = target.email
    deleted_role = target.role

    admin_count_subq = (
        sa.select(sa.func.count()).select_from(User).where(User.role == "admin").scalar_subquery()
    )
    result = await session.execute(
        sa.delete(User)
        .where(User.id == target_id)
        .where(sa.or_(User.role != "admin", admin_count_subq > 1))
    )
    if result.rowcount == 0:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Cannot delete the last admin")
    await session.commit()

    logger.info(f"User deleted: id={user_id} by={admin['email']}")
    audit.record(
        request,
        user=admin,
        action="user.delete",
        resource_type="user",
        resource_id=str(target_id),
        metadata={"email": deleted_email, "role": deleted_role},
    )
    return StatusResponse(status="ok", message="User deleted")
