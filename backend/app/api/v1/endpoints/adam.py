"""ADaM generation API — derive ADaM from SDTM artifacts."""

from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.artifact import ArtifactType
from app.models.audit import AuditAction
from app.models.user import User
from app.repositories.artifact_repository import ArtifactRepository
from app.schemas.adam import ADAMGenerationResponse, StudyADAMReadinessResponse
from app.services.adam_define_service import build_adam_define_xml
from app.services.adam_generation_service import ADAMGenerationService
from app.services.adrg_generation_service import (
    build_adrg_docx,
    build_adrg_filename,
    build_adam_define_filename,
)
from app.services.audit_service import AuditService
from app.services.context_graph_service import ContextGraphService
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


async def _load_adam_artifact_content(
    artifact_id: UUID,
    organization_id: UUID,
    db: AsyncSession,
) -> tuple:
    """Load ADAM_DATASET artifact and current version content."""
    repo = ArtifactRepository(db)
    artifact = await repo.get_by_id(artifact_id, organization_id)
    if artifact.artifact_type != ArtifactType.ADAM_DATASET:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_ADAM",
                "message": "Artifact is not an ADAM_DATASET.",
            },
        )
    if artifact.current_version_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NO_CONTENT",
                "message": "Artifact has no version content to export.",
            },
        )
    version = await repo.get_version(artifact.current_version_id)
    return artifact, version.content or {}


async def _audit_artifact_export(
    db: AsyncSession,
    *,
    artifact,
    user: User,
    export_format: str,
    filename: str,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    audit = AuditService(db)
    graph = ContextGraphService(db)
    version_id = artifact.current_version_id
    after_state = {
        "artifact_id": str(artifact.id),
        "artifact_version_id": str(version_id) if version_id else None,
        "artifact_type": artifact.artifact_type.value,
        "format": export_format,
        "filename": filename,
    }
    await audit.log(
        action=AuditAction.ARTIFACT_EXPORTED,
        resource_type="artifact",
        organization_id=user.organization_id,
        actor_user_id=user.id,
        resource_id=artifact.id,
        after_state=after_state,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await graph.emit_event(
        organization_id=user.organization_id,
        study_id=artifact.study_id,
        event_type="ARTIFACT_EXPORTED",
        payload={
            "entity_type": "artifact",
            "entity_id": str(artifact.id),
            "artifact_type": artifact.artifact_type.value,
            "format": export_format,
            "filename": filename,
            "artifact_version_id": str(version_id) if version_id else None,
        },
        actor_user_id=user.id,
    )


@router.get(
    "/artifacts/{artifact_id}/define-xml",
    summary="Export define.xml for ADaM dataset artifact",
    response_class=Response,
)
async def export_adam_define_xml(
    artifact_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export CDISC Define-XML 2.1 for an ADAM_DATASET artifact."""
    artifact, content = await _load_adam_artifact_content(
        artifact_id, current_user.organization_id, db
    )
    xml = build_adam_define_xml(content)
    filename = build_adam_define_filename(
        content.get("protocol_number"),
        content.get("study_name"),
    )
    await _audit_artifact_export(
        db,
        artifact=artifact,
        user=current_user,
        export_format="xml",
        filename=filename,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return Response(
        content=xml.encode("utf-8"),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/artifacts/{artifact_id}/adrg",
    summary="Export ADRG skeleton for ADaM dataset artifact",
    response_class=Response,
)
async def export_adam_adrg(
    artifact_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export Analysis Data Reviewer's Guide (ADRG) DOCX for an ADAM_DATASET artifact."""
    artifact, content = await _load_adam_artifact_content(
        artifact_id, current_user.organization_id, db
    )
    body = build_adrg_docx(content)
    filename = build_adrg_filename(
        content.get("protocol_number"),
        content.get("study_name"),
    )
    await _audit_artifact_export(
        db,
        artifact=artifact,
        user=current_user,
        export_format="docx",
        filename=filename,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return Response(
        content=body,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
