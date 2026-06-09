"""CSR generation API — assemble Clinical Study Report from TLF artifacts."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.csr import (
    CSRGenerationRequest,
    CSRGenerationResponse,
    CSRRequirementResponse,
    StudyCSRReadinessResponse,
)
from app.services.csr_generation_service import CSRGenerationService
from app.services.validation_executor import execute_validation_run

router = APIRouter()


@router.get(
    "/studies/{study_id}/csr-readiness",
    response_model=StudyCSRReadinessResponse,
    summary="Study-wide CSR generation readiness",
)
async def get_study_csr_readiness(
    study_id: UUID,
    data_cut_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyCSRReadinessResponse:
    """Check whether upstream artifacts are ready for CSR assembly."""
    svc = CSRGenerationService(db)
    readiness = await svc.get_study_readiness(
        study_id, current_user.organization_id, data_cut_id=data_cut_id
    )
    return StudyCSRReadinessResponse(
        study_id=readiness.study_id,
        tlf_artifact_count=readiness.tlf_artifact_count,
        protocol_artifact_count=readiness.protocol_artifact_count,
        sap_artifact_count=readiness.sap_artifact_count,
        ready=readiness.ready,
        issues=readiness.issues,
        tlf_artifacts=readiness.tlf_artifacts,
        data_cut_id=readiness.data_cut_id,
        data_source_type=readiness.data_source_type,
        data_cut_label=readiness.data_cut_label,
        csr_kind=readiness.csr_kind,
        requirements=[
            CSRRequirementResponse(**r) for r in (readiness.requirements or [])
        ],
        sdtm_artifact_id=readiness.sdtm_artifact_id,
        adam_artifact_id=readiness.adam_artifact_id,
    )


@router.post(
    "/studies/{study_id}/generate-csr",
    response_model=CSRGenerationResponse,
    summary="Generate full-study CSR from TLF artifacts",
)
async def generate_study_csr(
    study_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    body: CSRGenerationRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CSRGenerationResponse:
    """Assemble an ICH E3 CSR for a study data cut with full upstream evidence."""
    svc = CSRGenerationService(db)
    opts = body or CSRGenerationRequest()
    result = await svc.generate_from_study(
        study_id=study_id,
        actor=current_user,
        data_cut_id=opts.data_cut_id,
        generate_shell=opts.generate_shell,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    background_tasks.add_task(
        execute_validation_run,
        result.validation_run.id,
        result.validation_run.organization_id,
    )
    return CSRGenerationResponse(
        artifact_id=result.artifact.id,
        artifact_version_id=result.artifact.current_version_id,
        ai_decision_id=result.ai_decision_id,
        validation_run_id=result.validation_run.id,
        section_count=result.section_count,
        study_id=result.artifact.study_id,
        source_tlf_artifact_ids=result.source_tlf_artifact_ids,
        source_study_artifact_ids=result.source_study_artifact_ids,
    )


@router.post(
    "/artifacts/{artifact_id}/generate-csr",
    response_model=CSRGenerationResponse,
    summary="Generate CSR from a single TLF artifact",
)
async def generate_csr_from_tlf(
    artifact_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    body: CSRGenerationRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CSRGenerationResponse:
    """Assemble an ICH E3 CSR from one TLF package and matching upstream artifacts."""
    svc = CSRGenerationService(db)
    opts = body or CSRGenerationRequest()
    result = await svc.generate_from_tlf_artifact(
        tlf_artifact_id=artifact_id,
        actor=current_user,
        generate_shell=opts.generate_shell,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    background_tasks.add_task(
        execute_validation_run,
        result.validation_run.id,
        result.validation_run.organization_id,
    )
    return CSRGenerationResponse(
        artifact_id=result.artifact.id,
        artifact_version_id=result.artifact.current_version_id,
        ai_decision_id=result.ai_decision_id,
        validation_run_id=result.validation_run.id,
        section_count=result.section_count,
        study_id=result.artifact.study_id,
        source_tlf_artifact_ids=result.source_tlf_artifact_ids,
        source_study_artifact_ids=result.source_study_artifact_ids,
    )
