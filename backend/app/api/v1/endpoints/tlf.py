"""TLF generation API — derive TLF from ADaM artifacts."""

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
from app.models.user import User
from app.repositories.artifact_repository import ArtifactRepository
from app.schemas.tlf import TLFGenerationResponse
from app.services.artifact_service import ArtifactService
from app.services.tlf_generation_service import TLFGenerationService
from app.services.validation_executor import execute_validation_run

router = APIRouter()


@router.post(
    "/artifacts/{artifact_id}/generate-tlf",
    response_model=TLFGenerationResponse,
    summary="Generate TLF package from ADaM artifact",
)
async def generate_tlf_from_adam(
    artifact_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TLFGenerationResponse:
    """Derive TLF tables from an ADAM_DATASET artifact with dual-programmer R QC."""
    svc = TLFGenerationService(db)
    result = await svc.generate_from_adam_artifact(
        adam_artifact_id=artifact_id,
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
    return TLFGenerationResponse(
        artifact_id=result.artifact.id,
        artifact_version_id=result.artifact.current_version_id,
        ai_decision_id=result.ai_decision_id,
        validation_run_id=result.validation_run.id,
        table_count=result.table_count,
        study_id=result.artifact.study_id,
        source_adam_artifact_ids=result.source_adam_artifact_ids,
    )


@router.post(
    "/artifacts/{artifact_id}/render",
    summary="Render TLF artifact as PDF",
    response_class=Response,
)
async def render_tlf_artifact(
    artifact_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Render a TLF artifact as PDF via the unified export service."""
    repo = ArtifactRepository(db)
    artifact = await repo.get_by_id(artifact_id, current_user.organization_id)
    if artifact.artifact_type != ArtifactType.TLF:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "NOT_TLF", "message": "Artifact must be TLF."},
        )

    svc = ArtifactService(db)
    result = await svc.export_artifact_file(
        artifact_id,
        current_user.organization_id,
        current_user,
        "pdf",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )
