from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import User, UserSession
from bigrag.db.session import get_session
from bigrag.ids import uuid7
from bigrag.logging import get_logger
from bigrag.middleware.auth import invalidate_auth_principals, require_admin_session
from bigrag.models import StatusResponse
from bigrag.models.auth import (
    CreateUserRequest,
    UpdateUserRequest,
    UserListResponse,
    UserResponse,
)
from bigrag.routers import is_unique_violation, uuid_or_404
from bigrag.services import audit
from bigrag.services.auth import hash_password
from bigrag.services.pagination import apply_cursor, build_response_cursor, decode_cursor_or_400

logger = get_logger("bigrag.routers.admin_users")

router = APIRouter(prefix="/v1/admin/users", tags=["admin:users"])


async def _ensure_admin_role_can_change(
    session: AsyncSession,
    target: User,
    next_role: str,
) -> None:
    if target.role != "admin" or next_role == "admin":
        return
    admin_ids = (
        await session.scalars(sa.select(User.id).where(User.role == "admin").with_for_update())
    ).all()
    if len(admin_ids) <= 1:
        raise HTTPException(status_code=400, detail="Cannot demote the last admin")


@router.get("", response_model=UserListResponse)
async def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = Query(default=None),
    include_total: bool = Query(default=False),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> UserListResponse:
    cursor_tuple = decode_cursor_or_400(cursor)

    stmt = sa.select(User).order_by(User.created_at.asc(), User.id.asc())
    if cursor_tuple is not None:
        stmt = apply_cursor(stmt, User.created_at, User.id, cursor_tuple, direction="asc").limit(
            limit + 1
        )
    else:
        stmt = stmt.limit(limit + 1).offset(offset)

    rows = (await session.scalars(stmt)).all()
    page, next_cursor = build_response_cursor(list(rows), "created_at", "id", limit)

    total: int | None = None
    if include_total:
        total = (await session.scalar(sa.select(sa.func.count()).select_from(User))) or 0
    return UserListResponse(
        users=[UserResponse.from_user(u) for u in page],
        total=total,
        next_cursor=next_cursor,
    )


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: CreateUserRequest,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    user = User(
        id=uuid7(),
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
        if is_unique_violation(e):
            raise HTTPException(status_code=409, detail="Email is already registered") from e
        raise
    await session.refresh(user)
    logger.info("user created", email=body.email, role=body.role)
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
    target_id = uuid_or_404(user_id, "User")

    target = await session.get(User, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    password_changed = False
    fields: list[str] = []
    if body.email is not None:
        target.email = body.email.lower()
        fields.append("email")
    if body.display_name is not None:
        target.display_name = body.display_name
        fields.append("display_name")
    if body.role is not None:
        await _ensure_admin_role_can_change(session, target, body.role)
        target.role = body.role
        fields.append("role")
    if body.password is not None:
        target.password_hash = hash_password(body.password)
        password_changed = True
        fields.append("password")

    if password_changed:
        await session.execute(sa.delete(UserSession).where(UserSession.user_id == target_id))
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if is_unique_violation(e):
            raise HTTPException(status_code=409, detail="Email is already registered") from e
        raise
    await session.refresh(target)
    await invalidate_auth_principals()

    logger.info(
        "user updated",
        id=user_id,
        actor=admin["email"],
        display_name=body.display_name is not None,
        role=body.role is not None,
        password=password_changed,
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
    target_id = uuid_or_404(user_id, "User")

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
    await invalidate_auth_principals()

    logger.info("user deleted", id=user_id, actor=admin["email"])
    audit.record(
        request,
        user=admin,
        action="user.delete",
        resource_type="user",
        resource_id=str(target_id),
        metadata={"email": deleted_email, "role": deleted_role},
    )
    return StatusResponse(status="ok", message="User deleted")
