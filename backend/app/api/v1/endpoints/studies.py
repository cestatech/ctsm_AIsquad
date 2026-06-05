"""Studies API — CRUD for clinical trial workspaces and member management.

Permissions (enforced in service layer):
  - Create study: Admin only
  - Update study: Admin or Contributor with study membership
  - Archive study: Admin only
  - List/Get study: any authenticated user (org-scoped)
  - Manage members: Admin only
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.permissions import Role
from app.models.study import StudyStatus
from app.models.user import User
from app.schemas.study import (
    AddMemberRequest,
    StudyCreate,
    StudyListResponse,
    StudyMemberResponse,
    StudyResponse,
    UpdateMemberRoleRequest,
    StudyUpdate,
)
from app.services.study_service import StudyService

router = APIRouter()


# ---------------------------------------------------------------------------
# Studies CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=StudyListResponse, summary="List studies")
async def list_studies(
    study_status: StudyStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyListResponse:
    """List all studies for the authenticated user's organization."""
    svc = StudyService(db)
    studies, total = await svc.list_studies(
        organization_id=current_user.organization_id,
        status_filter=study_status,
        page=page,
        page_size=page_size,
    )
    return StudyListResponse(
        items=[StudyResponse.model_validate(s) for s in studies],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
    )


@router.post(
    "",
    response_model=StudyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a study",
)
async def create_study(
    body: StudyCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyResponse:
    """Create a new clinical trial study workspace. Admin only."""
    svc = StudyService(db)
    study = await svc.create(
        body=body,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return StudyResponse.model_validate(study)


@router.get("/{study_id}", response_model=StudyResponse, summary="Get a study")
async def get_study(
    study_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyResponse:
    """Get a single study by ID. Org-scoped."""
    svc = StudyService(db)
    study = await svc.get(study_id, current_user.organization_id)
    return StudyResponse.model_validate(study)


@router.patch("/{study_id}", response_model=StudyResponse, summary="Update a study")
async def update_study(
    study_id: UUID,
    body: StudyUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyResponse:
    """Update study metadata. Admin or Contributor with study membership."""
    svc = StudyService(db)
    study = await svc.update(
        study_id=study_id,
        body=body,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return StudyResponse.model_validate(study)


@router.post(
    "/{study_id}/archive",
    response_model=StudyResponse,
    summary="Archive a study",
)
async def archive_study(
    study_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyResponse:
    """Archive a study. Admin only. Archived studies are read-only."""
    svc = StudyService(db)
    study = await svc.archive(
        study_id=study_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return StudyResponse.model_validate(study)


# ---------------------------------------------------------------------------
# Member management
# ---------------------------------------------------------------------------


@router.get(
    "/{study_id}/members",
    response_model=list[StudyMemberResponse],
    summary="List study members",
)
async def list_members(
    study_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StudyMemberResponse]:
    """List all members assigned to a study."""
    svc = StudyService(db)
    members = await svc.list_members(study_id, current_user.organization_id)
    return [StudyMemberResponse.model_validate(m) for m in members]


@router.post(
    "/{study_id}/members",
    response_model=StudyMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member",
)
async def add_member(
    study_id: UUID,
    body: AddMemberRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyMemberResponse:
    """Add a user to this study with a specific role. Admin only."""
    svc = StudyService(db)
    member = await svc.add_member(
        study_id=study_id,
        user_id=body.user_id,
        role=Role(body.role),
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return StudyMemberResponse.model_validate(member)


@router.delete(
    "/{study_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member",
)
async def remove_member(
    study_id: UUID,
    user_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove a user from this study. Admin only."""
    svc = StudyService(db)
    await svc.remove_member(
        study_id=study_id,
        user_id=user_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{study_id}/members/{user_id}",
    response_model=StudyMemberResponse,
    summary="Update a member's role",
)
async def update_member_role(
    study_id: UUID,
    user_id: UUID,
    body: UpdateMemberRoleRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyMemberResponse:
    """Change the role of an existing study member. Admin only."""
    svc = StudyService(db)
    member = await svc.update_member_role(
        study_id=study_id,
        user_id=user_id,
        new_role=Role(body.role),
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return StudyMemberResponse.model_validate(member)
