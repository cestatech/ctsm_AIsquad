"""Validation API — trigger and inspect CDISC validation runs.

Permissions (enforced in service layer):
  - Trigger run: Admin, Contributor, Reviewer
  - List / Get: any authenticated user (org-scoped)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.validation import (
    ValidationRunCreate,
    ValidationRunListResponse,
    ValidationRunResponse,
)
from app.services.validation_executor import execute_validation_run
from app.services.validation_service import ValidationService

router = APIRouter()


@router.post(
    "/runs",
    response_model=ValidationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger validation run",
)
async def trigger_validation_run(
    body: ValidationRunCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationRunResponse:
    """Trigger a CDISC validation run for an artifact version. All roles."""
    svc = ValidationService(db)
    run = await svc.trigger(
        body=body,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    background_tasks.add_task(execute_validation_run, run.id, run.organization_id)
    return ValidationRunResponse.model_validate(run)


@router.get("/runs", response_model=ValidationRunListResponse, summary="List validation runs")
async def list_validation_runs(
    artifact_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationRunListResponse:
    """List validation runs for the org, optionally filtered by artifact."""
    svc = ValidationService(db)
    items, total = await svc.list(
        organization_id=current_user.organization_id,
        artifact_id=artifact_id,
        page=page,
        page_size=page_size,
    )
    return ValidationRunListResponse(
        items=[ValidationRunResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
    )


@router.get(
    "/runs/{run_id}",
    response_model=ValidationRunResponse,
    summary="Get validation run",
)
async def get_validation_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationRunResponse:
    """Fetch a single validation run by ID."""
    svc = ValidationService(db)
    run = await svc.get(run_id, current_user.organization_id)
    return ValidationRunResponse.model_validate(run)
