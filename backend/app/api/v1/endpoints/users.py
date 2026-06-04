"""Users API — organization member listing and management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import (
    UserInviteRequest,
    UserInviteResponse,
    UserListResponse,
    UserResponse,
)
from app.services.user_service import UserService

router = APIRouter()


@router.get("", response_model=UserListResponse, summary="List organization users")
async def list_users(
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    """List all users in the authenticated user's organization."""
    filters = [
        User.organization_id == current_user.organization_id,
        User.deleted_at.is_(None),
    ]
    if is_active is not None:
        filters.append(User.is_active == is_active)

    count_result = await db.execute(
        select(func.count()).select_from(User).where(*filters)
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        select(User)
        .where(*filters)
        .order_by(User.full_name.asc())
        .limit(page_size)
        .offset(offset)
    )
    users = list(result.scalars().all())

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
    )


@router.post(
    "/invite",
    response_model=UserInviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a new user",
)
async def invite_user(
    body: UserInviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserInviteResponse:
    """Create a new organization member. Admin only. Returns a temporary password."""
    svc = UserService(db)
    user, temp_pw = await svc.invite(
        organization_id=current_user.organization_id,
        actor=current_user,
        email=body.email,
        full_name=body.full_name,
        is_admin=(body.role == "ADMIN"),
    )
    return UserInviteResponse(
        user=UserResponse.model_validate(user), temporary_password=temp_pw
    )


@router.post(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="Deactivate a user",
)
async def deactivate_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Deactivate a user account. Admin only. The user can no longer log in."""
    svc = UserService(db)
    user = await svc.deactivate(user_id, current_user.organization_id, current_user)
    return UserResponse.model_validate(user)


@router.post(
    "/{user_id}/activate",
    response_model=UserResponse,
    summary="Reactivate a user",
)
async def activate_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Reactivate a deactivated user account. Admin only."""
    svc = UserService(db)
    user = await svc.activate(user_id, current_user.organization_id, current_user)
    return UserResponse.model_validate(user)
