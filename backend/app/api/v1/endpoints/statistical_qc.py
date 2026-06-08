"""Dual-programmer statistical QC API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.statistical_qc import StatisticalQCWorkflow
from app.models.user import User
from app.repositories.statistical_qc_repository import StatisticalQCRepository
from app.schemas.statistical_qc import (
    StatisticalQCRunListResponse,
    StatisticalQCRunResponse,
)

router = APIRouter()


@router.get(
    "/runs",
    response_model=StatisticalQCRunListResponse,
    summary="List dual-programmer QC runs",
)
async def list_qc_runs(
    study_id: UUID | None = Query(None),
    output_artifact_id: UUID | None = Query(None),
    workflow_step: StatisticalQCWorkflow | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatisticalQCRunListResponse:
    """List primary vs QC R program comparison runs for the organization."""
    repo = StatisticalQCRepository(db)
    offset = (page - 1) * page_size
    items, total = await repo.list_runs(
        current_user.organization_id,
        study_id=study_id,
        output_artifact_id=output_artifact_id,
        workflow_step=workflow_step,
        limit=page_size,
        offset=offset,
    )
    return StatisticalQCRunListResponse(
        items=[StatisticalQCRunResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/runs/{run_id}",
    response_model=StatisticalQCRunResponse,
    summary="Get dual-programmer QC run detail",
)
async def get_qc_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatisticalQCRunResponse:
    """Return full QC run including both R programs and comparison result."""
    repo = StatisticalQCRepository(db)
    run = await repo.get(run_id, current_user.organization_id)
    if run is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "QC run not found."},
        )
    return StatisticalQCRunResponse.model_validate(run)


@router.get(
    "/runs/{run_id}/primary-program",
    response_class=PlainTextResponse,
    summary="Download primary programmer R script",
)
async def download_primary_program(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """Download the primary statistical programmer R program as a .R file."""
    repo = StatisticalQCRepository(db)
    run = await repo.get(run_id, current_user.organization_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "QC run not found."},
        )
    filename = f"primary_{run.workflow_step.value.lower()}.R"
    return PlainTextResponse(
        content=run.primary_r_program,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        media_type="text/plain; charset=utf-8",
    )


@router.get(
    "/runs/{run_id}/qc-program",
    response_class=PlainTextResponse,
    summary="Download QC programmer R script",
)
async def download_qc_program(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """Download the independent QC programmer R program as a .R file."""
    repo = StatisticalQCRepository(db)
    run = await repo.get(run_id, current_user.organization_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "QC run not found."},
        )
    filename = f"qc_{run.workflow_step.value.lower()}.R"
    return PlainTextResponse(
        content=run.qc_r_program,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        media_type="text/plain; charset=utf-8",
    )
