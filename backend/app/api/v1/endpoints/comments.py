"""Comments API — threaded review comments on artifacts.

Permissions:
  - List / Create: any authenticated user (org-scoped)
  - Edit: comment author only
  - Resolve: any authenticated user (org-scoped)
  - Delete: author or Admin
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.comment import (
    CommentCreate,
    CommentListResponse,
    CommentResponse,
    CommentUpdate,
)
from app.services.comment_service import CommentService

router = APIRouter()


@router.get("", response_model=CommentListResponse, summary="List comments")
async def list_comments(
    artifact_id: UUID = Query(...),
    include_resolved: bool = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentListResponse:
    """List top-level comments for an artifact. Replies are nested under each comment."""
    svc = CommentService(db)
    items, total = await svc.list(
        artifact_id=artifact_id,
        organization_id=current_user.organization_id,
        include_resolved=include_resolved,
        page=page,
        page_size=page_size,
    )
    return CommentListResponse(
        items=[CommentResponse.model_validate(c) for c in items],
        total=total,
    )


@router.post(
    "",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a comment",
)
async def create_comment(
    body: CommentCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """Post a new comment (or reply) on an artifact."""
    svc = CommentService(db)
    comment = await svc.create(
        body=body,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return CommentResponse.model_validate(comment)


@router.patch(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="Edit a comment",
)
async def update_comment(
    comment_id: UUID,
    body: CommentUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """Edit the body of a comment. Author only; resolved comments cannot be edited."""
    svc = CommentService(db)
    comment = await svc.update(
        comment_id=comment_id,
        body=body,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return CommentResponse.model_validate(comment)


@router.post(
    "/{comment_id}/resolve",
    response_model=CommentResponse,
    summary="Resolve a comment",
)
async def resolve_comment(
    comment_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """Mark a comment as resolved. Any authenticated org member can resolve."""
    svc = CommentService(db)
    comment = await svc.resolve(
        comment_id=comment_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return CommentResponse.model_validate(comment)


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
)
async def delete_comment(
    comment_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Soft-delete a comment. Author or Admin only."""
    svc = CommentService(db)
    await svc.delete(
        comment_id=comment_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
