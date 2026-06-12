"""Approvals API — review queue and approval decisions.

Permissions:
  - GET /queue: any authenticated user (filtered to reviewer/admin in service)
  - POST /: Reviewer or Admin (enforced by ArtifactService.approve/reject)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.permissions import Permission, check_permission
from app.models.approval import Approval
from app.models.user import User
from app.repositories.artifact_repository import ArtifactRepository
from app.schemas.approval import (
    ApprovalQueueItem,
    ApprovalQueueResponse,
    ApprovalResponse,
    CreateApprovalRequest,
    CreatorBrief,
)
from app.services.artifact_service import ArtifactService

router = APIRouter()


@router.get(
    "/queue", response_model=ApprovalQueueResponse, summary="Artifacts pending review"
)
async def get_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApprovalQueueResponse:
    """Return IN_REVIEW artifacts for reviewers and admins in the organization."""
    check_permission(current_user, Permission.ARTIFACT_APPROVE)
    repo = ArtifactRepository(db)
    offset = (page - 1) * page_size
    artifacts, total = await repo.list_in_review(
        organization_id=current_user.organization_id,
        limit=page_size,
        offset=offset,
    )
    items = [
        ApprovalQueueItem(
            artifact_id=a.id,
            artifact_version_id=a.current_version_id,
            artifact_name=a.name,
            artifact_type=a.artifact_type,
            study_id=a.study_id,
            study_name=a.study.name,
            protocol_number=a.study.protocol_number,
            version_number=a.current_version_number,
            submitted_by=CreatorBrief(
                id=a.creator.id,
                full_name=a.creator.full_name,
                email=a.creator.email,
            ),
            submitted_at=a.updated_at,
        )
        for a in artifacts
    ]
    return ApprovalQueueResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
    )


@router.post(
    "",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit approval decision",
)
async def create_approval(
    body: CreateApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    """
    Approve or reject an artifact. Requires Reviewer or Admin role.

    Transitions the artifact status (IN_REVIEW → APPROVED or REJECTED) and
    creates an immutable Approval record with an electronic signature.
    """
    if body.decision.value == "REJECTED" and not body.comments:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "REJECTION_REASON_REQUIRED",
                "message": "A reason is required when rejecting an artifact.",
            },
        )

    svc = ArtifactService(db)
    if body.decision.value == "APPROVED":
        await svc.approve(
            artifact_id=body.artifact_id,
            organization_id=current_user.organization_id,
            user=current_user,
            comments=body.comments,
        )
    else:
        await svc.reject(
            artifact_id=body.artifact_id,
            organization_id=current_user.organization_id,
            user=current_user,
            comments=body.comments or "",
        )

    await db.flush()

    result = await db.execute(
        select(Approval)
        .where(
            Approval.artifact_id == body.artifact_id,
            Approval.approver_id == current_user.id,
        )
        .order_by(Approval.created_at.desc())
        .limit(1)
    )
    approval = result.scalar_one()
    return ApprovalResponse.model_validate(approval)
