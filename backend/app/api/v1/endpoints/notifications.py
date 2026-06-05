"""Notifications API — per-user in-platform notifications."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("", response_model=NotificationListResponse, summary="List notifications")
async def list_notifications(
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """Return notifications for the authenticated user, newest first."""
    svc = NotificationService(db)
    offset = (page - 1) * page_size
    items, total = await svc.list_for_user(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        unread_only=unread_only,
        limit=page_size,
        offset=offset,
    )
    unread = await svc.unread_count(current_user.id, current_user.organization_id)
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        unread_count=unread,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
    )


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark notification as read",
)
async def mark_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    """Mark a single notification as read."""
    svc = NotificationService(db)
    n = await svc.mark_read(
        notification_id, current_user.id, current_user.organization_id
    )
    if n is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Notification not found."},
        )
    return NotificationResponse.model_validate(n)


@router.post(
    "/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Mark all notifications as read",
)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Mark all unread notifications for the authenticated user as read."""
    svc = NotificationService(db)
    await svc.mark_all_read(current_user.id, current_user.organization_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
