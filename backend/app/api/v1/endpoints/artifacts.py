"""Artifacts API — artifact lifecycle management.

Permissions (enforced in service layer):
  - List / Get: any authenticated user (org-scoped)
  - Create: Admin, Contributor
  - Submit for review: Admin, Contributor
  - Approve / Reject: Admin, Reviewer (via /approvals)
  - Lock: Admin
  - Amend: Admin
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.artifact_repository import ArtifactRepository
from app.schemas.artifact import (
    ArtifactCreate,
    ArtifactListResponse,
    ArtifactResponse,
    ArtifactUpdate,
    ArtifactVersionResponse,
)
from app.services.artifact_service import ArtifactService

router = APIRouter()


@router.get("", response_model=ArtifactListResponse, summary="List artifacts")
async def list_artifacts(
    study_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactListResponse:
    """List artifacts for the org, optionally filtered by study."""
    repo = ArtifactRepository(db)
    offset = (page - 1) * page_size
    if study_id:
        items, total = await repo.list_by_study(
            study_id, current_user.organization_id, limit=page_size, offset=offset
        )
    else:
        items, total = await repo.list_all(
            current_user.organization_id, limit=page_size, offset=offset
        )
    return ArtifactListResponse(
        items=[ArtifactResponse.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
    )


@router.post(
    "",
    response_model=ArtifactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create artifact",
)
async def create_artifact(
    body: ArtifactCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Create a new artifact in DRAFT status. Contributor or Admin."""
    svc = ArtifactService(db)
    artifact = await svc.create_artifact(
        organization_id=current_user.organization_id,
        study_id=body.study_id,
        user=current_user,
        artifact_type=body.artifact_type,
        name=body.name,
        description=body.description,
        content=body.content or {},
        change_summary=body.change_summary,
    )
    return ArtifactResponse.model_validate(artifact)


@router.get("/{artifact_id}", response_model=ArtifactResponse, summary="Get artifact")
async def get_artifact(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Fetch a single artifact by ID, scoped to the authenticated org."""
    repo = ArtifactRepository(db)
    artifact = await repo.get_by_id(artifact_id, current_user.organization_id)
    return ArtifactResponse.model_validate(artifact)


@router.patch(
    "/{artifact_id}",
    response_model=ArtifactResponse,
    summary="Update artifact content",
)
async def update_artifact_content(
    artifact_id: UUID,
    body: ArtifactUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Update content of a DRAFT or REJECTED artifact, creating a new version. Contributor or Admin."""
    svc = ArtifactService(db)
    artifact = await svc.update_artifact_content(
        artifact_id=artifact_id,
        organization_id=current_user.organization_id,
        user=current_user,
        content=body.content,
        change_summary=body.change_summary,
    )
    return ArtifactResponse.model_validate(artifact)


@router.get(
    "/{artifact_id}/versions",
    response_model=list[ArtifactVersionResponse],
    summary="List artifact versions",
)
async def list_artifact_versions(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ArtifactVersionResponse]:
    """Return all version snapshots for an artifact, oldest first."""
    repo = ArtifactRepository(db)
    versions = await repo.list_versions(artifact_id, current_user.organization_id)
    return [ArtifactVersionResponse.model_validate(v) for v in versions]


@router.post(
    "/{artifact_id}/submit",
    response_model=ArtifactResponse,
    summary="Submit for review",
)
async def submit_for_review(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Transition artifact from DRAFT → IN_REVIEW. Contributor or Admin."""
    svc = ArtifactService(db)
    artifact = await svc.submit_for_review(
        artifact_id, current_user.organization_id, current_user
    )
    return ArtifactResponse.model_validate(artifact)


@router.post(
    "/{artifact_id}/lock",
    response_model=ArtifactResponse,
    summary="Lock artifact",
)
async def lock_artifact(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Lock an APPROVED artifact permanently. Admin only."""
    svc = ArtifactService(db)
    artifact = await svc.lock(artifact_id, current_user.organization_id, current_user)
    return ArtifactResponse.model_validate(artifact)


@router.post(
    "/{artifact_id}/amend",
    response_model=ArtifactResponse,
    summary="Amend locked artifact",
)
async def amend_artifact(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Begin amendment of a LOCKED artifact. Admin only."""
    svc = ArtifactService(db)
    artifact = await svc.amend(artifact_id, current_user.organization_id, current_user)
    return ArtifactResponse.model_validate(artifact)
