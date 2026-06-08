"""Raw data API — datasets, field profiling, mapping, and validation."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.raw_data_repository import (
    RawDatasetRepository,
)
from app.schemas.raw_data import (
    ApplyMappingSuggestionsRequest,
    BulkApproveMappingsResponse,
    FieldMappingRequest,
    FieldMappingVersionResponse,
    MappingApprovalRequest,
    MappingValidationResult,
    RawDatasetListResponse,
    RawDatasetResponse,
    RawFieldResponse,
    SDTMGenerationResponse,
    StudySDTMReadinessResponse,
    SuggestMappingsResponse,
)
from app.services.mapping_service import MappingService
from app.services.mapping_suggestion_service import MappingSuggestionService
from app.services.sdtm_generation_service import SDTMGenerationService
from app.services.upload_service import UploadService
from app.services.validation_executor import execute_validation_run
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
    await db.refresh(field)
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
    await db.refresh(field)
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
    await db.refresh(field)
    return RawFieldResponse.model_validate(field)


@router.post(
    "/datasets/{dataset_id}/mapping/bulk-approve",
    response_model=BulkApproveMappingsResponse,
    summary="Approve all pending mappings in a dataset",
)
async def bulk_approve_dataset_mappings(
    dataset_id: UUID,
    body: MappingApprovalRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BulkApproveMappingsResponse:
    """
    Approve every PENDING_APPROVAL mapping in a dataset.

    Requires Reviewer or Admin role. Skips fields not in PENDING_APPROVAL state.
    """
    svc = MappingService(db)
    approved, pending_count = await svc.bulk_approve_mappings(
        dataset_id=dataset_id,
        notes=body.notes,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    for field in approved:
        await db.refresh(field)
    return BulkApproveMappingsResponse(
        approved_count=len(approved),
        skipped_count=pending_count - len(approved),
        fields=[RawFieldResponse.model_validate(f) for f in approved],
    )


@router.get(
    "/datasets/{dataset_id}/mapping/export",
    summary="Export dataset mappings as CSV",
    response_class=Response,
)
async def export_dataset_mappings(
    dataset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download all column mappings for a dataset as CSV."""
    svc = MappingService(db)
    csv_content = await svc.export_mappings_csv(
        dataset_id, current_user.organization_id
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="mappings_{dataset_id}.csv"'
        },
    )


@router.post(
    "/datasets/{dataset_id}/suggest-mappings",
    response_model=SuggestMappingsResponse,
    summary="AI-propose eCRF/SDTM mappings for dataset columns",
)
async def suggest_dataset_mappings(
    dataset_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuggestMappingsResponse:
    """
    Use AI to propose raw column → eCRF/SDTM mappings.

    Returns suggestions for human review. Does not apply mappings automatically.
    Creates an AIDecision record per CIP mandatory rules.
    """
    svc = MappingSuggestionService(db)
    result = await svc.suggest_mappings(
        dataset_id=dataset_id,
        organization_id=current_user.organization_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return result


@router.post(
    "/datasets/{dataset_id}/apply-suggestions",
    response_model=list[RawFieldResponse],
    summary="Apply AI mapping suggestions as pending mappings",
)
async def apply_dataset_mapping_suggestions(
    dataset_id: UUID,
    body: ApplyMappingSuggestionsRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RawFieldResponse]:
    """
    Apply reviewed AI suggestions as PENDING_APPROVAL mappings.

    Reviewer/Admin approval is still required before mappings are finalized.
    """
    svc = MappingSuggestionService(db)
    fields = await svc.apply_suggestions(
        dataset_id=dataset_id,
        body=body,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    for field in fields:
        await db.refresh(field)
    return [RawFieldResponse.model_validate(f) for f in fields]


@router.get(
    "/studies/{study_id}/sdtm-readiness",
    response_model=StudySDTMReadinessResponse,
    summary="Study-wide SDTM generation readiness",
)
async def get_study_sdtm_readiness(
    study_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudySDTMReadinessResponse:
    """Check whether all study datasets have approved SDTM mappings."""
    svc = SDTMGenerationService(db)
    readiness = await svc.get_study_readiness(study_id, current_user.organization_id)
    return StudySDTMReadinessResponse(
        study_id=readiness.study_id,
        dataset_count=readiness.dataset_count,
        total_fields=readiness.total_fields,
        approved_fields=readiness.approved_fields,
        ready=readiness.ready,
        issues=readiness.issues,
        datasets=readiness.datasets,
    )


@router.post(
    "/studies/{study_id}/generate-sdtm",
    response_model=SDTMGenerationResponse,
    summary="Generate full-study SDTM package",
)
async def generate_study_sdtm(
    study_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SDTMGenerationResponse:
    """
    Merge all approved study datasets into one SDTM artifact.

    Runs internal CDISC validation and records ValidationEvidence per rule.
    """
    svc = SDTMGenerationService(db)
    result = await svc.generate_from_study(
        study_id=study_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    background_tasks.add_task(
        execute_validation_run, result.validation_run.id, result.validation_run.organization_id
    )
    return SDTMGenerationResponse(
        artifact_id=result.artifact.id,
        artifact_version_id=result.artifact.current_version_id,
        ai_decision_id=result.ai_decision_id,
        validation_run_id=result.validation_run.id,
        domain_count=result.domain_count,
        study_id=result.artifact.study_id,
        source_dataset_ids=result.source_dataset_ids,
    )


@router.post(
    "/datasets/{dataset_id}/generate-sdtm",
    response_model=SDTMGenerationResponse,
    summary="Generate SDTM dataset from approved mappings",
)
async def generate_sdtm_from_dataset(
    dataset_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SDTMGenerationResponse:
    """
    Derive an SDTM dataset artifact from fully approved raw field mappings.

    Requires all columns to have APPROVED SDTM mappings. Creates a DRAFT
    SDTM_DATASET artifact, records CIP lineage/graph links, and queues
    internal CDISC validation (Pinnacle 21 optional later).
    """
    svc = SDTMGenerationService(db)
    result = await svc.generate_from_dataset(
        dataset_id=dataset_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    background_tasks.add_task(
        execute_validation_run, result.validation_run.id, result.validation_run.organization_id
    )
    return SDTMGenerationResponse(
        artifact_id=result.artifact.id,
        artifact_version_id=result.artifact.current_version_id,
        ai_decision_id=result.ai_decision_id,
        validation_run_id=result.validation_run.id,
        domain_count=result.domain_count,
        study_id=result.artifact.study_id,
        source_dataset_ids=result.source_dataset_ids,
    )


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
