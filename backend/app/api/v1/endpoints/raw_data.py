"""Raw data API — datasets, field profiling, mapping, and validation."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.raw_data_repository import (
    RawDatasetRepository,
)
from app.schemas.raw_data import (
    FieldMappingRequest,
    FieldMappingVersionResponse,
    MappingApprovalRequest,
    MappingValidationResult,
    RawDatasetListResponse,
    RawDatasetResponse,
    RawFieldResponse,
)
from app.services.mapping_service import MappingService
from app.services.upload_service import UploadService
from app.schemas.upload import UploadedFileResponse

router = APIRouter()


@router.get(
    "/files/{file_id}",
    response_model=UploadedFileResponse,
    summary="Get upload detail",
)
async def get_upload_detail(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadedFileResponse:
    """Return metadata for a single uploaded file."""
    svc = UploadService(db)
    record = await svc.get_file(file_id, current_user.organization_id)
    return UploadedFileResponse.model_validate(record)


@router.get(
    "/files/{file_id}/datasets",
    response_model=RawDatasetListResponse,
    summary="List datasets for an uploaded file",
)
async def list_datasets(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RawDatasetListResponse:
    """List all parsed datasets (sheets) for an uploaded file."""
    svc = UploadService(db)
    await svc.get_file(file_id, current_user.organization_id)
    repo = RawDatasetRepository(db)
    items = await repo.list_for_file(file_id, current_user.organization_id)
    return RawDatasetListResponse(
        items=[RawDatasetResponse.model_validate(ds) for ds in items],
        total=len(items),
    )


@router.get(
    "/datasets/{dataset_id}/fields",
    response_model=list[RawFieldResponse],
    summary="List fields (columns) for a dataset",
)
async def list_fields(
    dataset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RawFieldResponse]:
    """List all profiled columns for a dataset, ordered by column index."""
    svc = MappingService(db)
    fields = await svc.list_fields_for_dataset(dataset_id, current_user.organization_id)
    return [RawFieldResponse.model_validate(f) for f in fields]


@router.put(
    "/fields/{field_id}/mapping",
    response_model=RawFieldResponse,
    summary="Set or update the eCRF/SDTM mapping for a raw field",
)
async def update_field_mapping(
    field_id: UUID,
    body: FieldMappingRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RawFieldResponse:
    """
    Map a raw column to an eCRF field name and/or SDTM variable name.

    Sets mapping_status to PENDING_APPROVAL and creates a versioned snapshot.
    Requires Admin or Contributor role.
    """
    svc = MappingService(db)
    field = await svc.map_field(
        field_id=field_id,
        mapped_ecrf_field_id=body.mapped_ecrf_field_id,
        mapped_sdtm_variable_id=body.mapped_sdtm_variable_id,
        notes=body.notes,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return RawFieldResponse.model_validate(field)


@router.post(
    "/fields/{field_id}/mapping/approve",
    response_model=RawFieldResponse,
    summary="Approve a pending mapping",
)
async def approve_field_mapping(
    field_id: UUID,
    body: MappingApprovalRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RawFieldResponse:
    """
    Approve a PENDING_APPROVAL mapping. Requires Reviewer or Admin role.
    Creates an APPROVED_BY edge in the context graph.
    """
    svc = MappingService(db)
    field = await svc.approve_mapping(
        field_id=field_id,
        notes=body.notes,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return RawFieldResponse.model_validate(field)


@router.post(
    "/fields/{field_id}/mapping/reject",
    response_model=RawFieldResponse,
    summary="Reject a pending mapping",
)
async def reject_field_mapping(
    field_id: UUID,
    body: MappingApprovalRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RawFieldResponse:
    """Reject a PENDING_APPROVAL mapping. Requires Reviewer or Admin role."""
    svc = MappingService(db)
    field = await svc.reject_mapping(
        field_id=field_id,
        notes=body.notes,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return RawFieldResponse.model_validate(field)


@router.get(
    "/datasets/{dataset_id}/validate",
    response_model=MappingValidationResult,
    summary="Validate mapping coverage for a dataset",
)
async def validate_dataset_mapping(
    dataset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MappingValidationResult:
    """
    Return mapping coverage stats and a list of issues (unmapped fields,
    incomplete chains). Used to gate downstream SDTM generation.
    """
    svc = MappingService(db)
    return await svc.validate_mapping(dataset_id, current_user.organization_id)


@router.get(
    "/fields/{field_id}/mapping/history",
    response_model=list[FieldMappingVersionResponse],
    summary="Mapping version history for a field",
)
async def get_field_mapping_history(
    field_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FieldMappingVersionResponse]:
    """Return the ordered version history of mappings for a raw field."""
    svc = MappingService(db)
    versions = await svc.list_versions_for_field(field_id, current_user.organization_id)
    return [FieldMappingVersionResponse.model_validate(v) for v in versions]
