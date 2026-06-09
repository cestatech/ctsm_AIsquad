"""Study file uploads API — CSV/XLSX/PDF uploads scoped to a study."""

from __future__ import annotations

from uuid import UUID

from datetime import date

from fastapi import APIRouter, Depends, Form, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.data_source import DataSourceType
from app.schemas.upload import UploadedFileListResponse, UploadedFileResponse
from app.services.upload_service import UploadService

router = APIRouter()


@router.post(
    "/{study_id}/uploads",
    response_model=UploadedFileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file to a study",
)
async def upload_study_file(
    study_id: UUID,
    file: UploadFile,
    request: Request,
    description: str | None = Form(default=None),
    data_source_type: DataSourceType = Form(default=DataSourceType.LIVE_FINAL),
    data_cut_label: str | None = Form(default=None),
    data_cut_date: date | None = Form(default=None),
    notes: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadedFileResponse:
    """
    Upload a CSV, XLSX, PDF, or TXT file to a study.

    CSV files have column headers and row count automatically extracted.
    Every upload creates an audit log entry.
    Requires Admin or Contributor role.
    """
    svc = UploadService(db)
    record = await svc.upload_file(
        study_id=study_id,
        actor=current_user,
        file=file,
        description=description,
        data_source_type=data_source_type,
        data_cut_label=data_cut_label,
        data_cut_date=data_cut_date,
        notes=notes,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return UploadedFileResponse.model_validate(record)


@router.get(
    "/{study_id}/uploads",
    response_model=UploadedFileListResponse,
    summary="List uploads for a study",
)
async def list_study_uploads(
    study_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadedFileListResponse:
    """List all uploaded files for a study, newest first."""
    svc = UploadService(db)
    items, total = await svc.list_for_study(
        study_id=study_id,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
    )
    return UploadedFileListResponse(
        items=[UploadedFileResponse.model_validate(f) for f in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
    )
