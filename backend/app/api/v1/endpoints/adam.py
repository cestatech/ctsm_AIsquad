"""ADaM generation API — derive ADaM from SDTM artifacts."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.adam import ADAMGenerationResponse, StudyADAMReadinessResponse
from app.services.adam_generation_service import ADAMGenerationService
from app.services.validation_executor import execute_validation_run

router = APIRouter()


@router.get(
    "/studies/{study_id}/adam-readiness",
    response_model=StudyADAMReadinessResponse,
    summary="Study-wide ADaM generation readiness",
)
async def get_study_adam_readiness(
    study_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyADAMReadinessResponse:
    """Check whether study SDTM artifacts are ready for ADaM derivation."""
    svc = ADAMGenerationService(db)
    readiness = await svc.get_study_readiness(study_id, current_user.organization_id)
    return StudyADAMReadinessResponse(
        study_id=readiness.study_id,
        sdtm_artifact_count=readiness.sdtm_artifact_count,
        ready=readiness.ready,
        issues=readiness.issues,
        sdtm_artifacts=readiness.sdtm_artifacts,
    )


@router.post(
    "/studies/{study_id}/generate-adam",
    response_model=ADAMGenerationResponse,
    summary="Generate full-study ADaM package from SDTM artifacts",
)
async def generate_study_adam(
    study_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ADAMGenerationResponse:
    """Merge all study SDTM artifacts and derive ADaM analysis datasets."""
    svc = ADAMGenerationService(db)
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
    return ADAMGenerationResponse(
        artifact_id=result.artifact.id,
        artifact_version_id=result.artifact.current_version_id,
        ai_decision_id=result.ai_decision_id,
        validation_run_id=result.validation_run.id,
        dataset_count=result.dataset_count,
        study_id=result.artifact.study_id,
        source_sdtm_artifact_ids=result.source_sdtm_artifact_ids,
    )


@router.post(
    "/artifacts/{artifact_id}/generate-adam",
    response_model=ADAMGenerationResponse,
    summary="Generate ADaM from a single SDTM artifact",
)
async def generate_adam_from_sdtm(
    artifact_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ADAMGenerationResponse:
    """Derive ADaM analysis datasets from one SDTM_DATASET artifact."""
    svc = ADAMGenerationService(db)
    result = await svc.generate_from_sdtm_artifact(
        sdtm_artifact_id=artifact_id,
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
    return ADAMGenerationResponse(
        artifact_id=result.artifact.id,
        artifact_version_id=result.artifact.current_version_id,
        ai_decision_id=result.ai_decision_id,
        validation_run_id=result.validation_run.id,
        dataset_count=result.dataset_count,
        study_id=result.artifact.study_id,
        source_sdtm_artifact_ids=result.source_sdtm_artifact_ids,
    )
