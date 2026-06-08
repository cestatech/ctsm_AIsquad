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
from app.models.audit import AuditAction
from app.models.user import User
from app.repositories.artifact_repository import ArtifactRepository
from app.schemas.tlf import TLFGenerationResponse
from app.services.audit_service import AuditService
from app.services.tlf_generation_service import TLFGenerationService
from app.services.tlf_renderer import TLFRenderer
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
    summary="Render TLF artifact as RTF",
    response_class=Response,
)
async def render_tlf_artifact(
    artifact_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Render a TLF artifact's current JSON spec as an RTF download."""
    repo = ArtifactRepository(db)
    artifact = await repo.get_by_id(artifact_id, current_user.organization_id)
    if artifact.artifact_type != ArtifactType.TLF:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "NOT_TLF", "message": "Artifact must be TLF."},
        )
    if artifact.current_version_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NO_CURRENT_VERSION",
                "message": "Artifact has no current version.",
            },
        )

    version = await repo.get_version(artifact.current_version_id)
    rtf_bytes = TLFRenderer().render_to_rtf(version.content or {})

    audit = AuditService(db)
    await audit.log(
        action=AuditAction.ARTIFACT_EXPORTED,
        resource_type="artifact",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_id=artifact.id,
        after_state={
            "artifact_id": str(artifact.id),
            "artifact_version_id": str(version.id),
            "format": "rtf",
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    safe_name = _safe_filename(artifact.name)
    return Response(
        content=rtf_bytes,
        media_type="application/rtf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.rtf"'},
    )


def _safe_filename(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name).strip("_")
    return safe or "tlf_artifact"
