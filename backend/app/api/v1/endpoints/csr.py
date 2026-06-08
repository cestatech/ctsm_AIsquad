"""CSR generation API — assemble Clinical Study Report from TLF artifacts."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.csr import CSRGenerationResponse, StudyCSRReadinessResponse
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyCSRReadinessResponse:
    """Check whether study TLF artifacts are ready for CSR assembly."""
    svc = CSRGenerationService(db)
    readiness = await svc.get_study_readiness(study_id, current_user.organization_id)
    return StudyCSRReadinessResponse(
        study_id=readiness.study_id,
        tlf_artifact_count=readiness.tlf_artifact_count,
        protocol_artifact_count=readiness.protocol_artifact_count,
        sap_artifact_count=readiness.sap_artifact_count,
        ready=readiness.ready,
        issues=readiness.issues,
        tlf_artifacts=readiness.tlf_artifacts,
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CSRGenerationResponse:
    """Merge all study TLF packages and assemble an ICH E3 CSR."""
    svc = CSRGenerationService(db)
    result = await svc.generate_from_study(
        study_id=study_id,
        actor=current_user,
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CSRGenerationResponse:
    """Assemble an ICH E3 CSR from one TLF package."""
    svc = CSRGenerationService(db)
    result = await svc.generate_from_tlf_artifact(
        tlf_artifact_id=artifact_id,
        actor=current_user,
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
