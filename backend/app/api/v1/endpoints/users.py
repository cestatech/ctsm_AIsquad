"""Users API — organization member listing and management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import UserListResponse, UserResponse

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
