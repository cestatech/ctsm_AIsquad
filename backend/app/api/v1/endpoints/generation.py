"""AI Generation API — trigger and inspect AI artifact generation jobs.

Permissions (enforced in service layer):
  - Trigger job: Admin, Contributor
  - List / Get: any authenticated user (org-scoped)

Every job triggers an AIDecision record per CIP mandatory rules. Output artifacts
are created as DRAFT and surface in /intelligence/decisions as PENDING_REVIEW.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.generation import (
    GenerationJobCreate,
    GenerationJobListResponse,
    GenerationJobResponse,
)
from app.services.generation_service import GenerationService

router = APIRouter()


@router.post(
    "/jobs",
    response_model=GenerationJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger AI generation job",
)
async def create_generation_job(
    body: GenerationJobCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobResponse:
    """Trigger an AI generation job for an artifact type. Admin or Contributor."""
    svc = GenerationService(db)
    job = await svc.create_job(
        body=body,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return GenerationJobResponse.model_validate(job)


@router.get("/jobs", response_model=GenerationJobListResponse, summary="List generation jobs")
async def list_generation_jobs(
    study_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobListResponse:
    """List AI generation jobs for the org, optionally filtered by study."""
    svc = GenerationService(db)
    items, total = await svc.list(
        organization_id=current_user.organization_id,
        study_id=study_id,
        page=page,
        page_size=page_size,
    )
    return GenerationJobListResponse(
        items=[GenerationJobResponse.model_validate(j) for j in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=GenerationJobResponse,
    summary="Get generation job",
)
async def get_generation_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobResponse:
    """Fetch a single generation job by ID."""
    svc = GenerationService(db)
    job = await svc.get(job_id, current_user.organization_id)
    return GenerationJobResponse.model_validate(job)
