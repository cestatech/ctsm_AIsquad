"""CSR generation API — assemble Clinical Study Report from TLF artifacts."""

from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.permissions import Permission, check_permission
from app.models.artifact import ArtifactStatus, ArtifactType
from app.models.audit import AuditAction
from app.models.user import User
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.intelligence_repository import ValidationEvidenceRepository
from app.repositories.study_repository import StudyRepository
from app.schemas.csr import (
    CSRGenerationRequest,
    CSRGenerationResponse,
    CSRRequirementResponse,
    StudyCSRReadinessResponse,
)
from app.services.audit_service import AuditService
from app.services.context_graph_service import ContextGraphService
from app.services.csr_generation_service import CSRGenerationService
from app.services.reviewers_guide_generator import (
    build_reviewers_guide_filename,
    generate_reviewers_guide_pdf,
)
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


async def _collect_adam_dataset_inventory(
    repo: ArtifactRepository,
    study_id: UUID,
    organization_id: UUID,
) -> list[dict]:
    """Build the Reviewer's Guide dataset inventory from ADaM artifact content."""
    artifacts, _total = await repo.list_by_study(
        study_id, organization_id, limit=500, offset=0
    )
    inventory: list[dict] = []
    for artifact in artifacts:
        if artifact.artifact_type != ArtifactType.ADAM_DATASET:
            continue
        if artifact.status == ArtifactStatus.SUPERSEDED:
            continue
        if artifact.current_version_id is None:
            continue
        version = await repo.get_version(artifact.current_version_id)
        content = version.content or {}
        for ds in content.get("datasets", []):
            observations = ds.get("observations")
            record_count = (
                len(observations) if isinstance(observations, list) else None
            )
            inventory.append(
                {
                    "name": ds.get("dataset") or ds.get("name") or "—",
                    "label": ds.get("label") or "",
                    "record_count": record_count,
                }
            )
    return inventory


@router.get(
    "/artifacts/{artifact_id}/reviewers-guide",
    summary="Download Study Data Reviewer's Guide PDF for a CSR artifact",
    response_class=Response,
)
async def download_reviewers_guide(
    artifact_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Generate the Reviewer's Guide (SDRG) PDF from CSR content, ADaM dataset
    metadata, and validation evidence. Admin or Reviewer only."""
    # AUDIT_READ maps to exactly Admin + Reviewer — the established pattern for
    # reviewer-facing exports (see SubmissionService.get_manifest).
    check_permission(current_user, Permission.AUDIT_READ)

    repo = ArtifactRepository(db)
    artifact = await repo.get_by_id(artifact_id, current_user.organization_id)
    if artifact.artifact_type != ArtifactType.CSR:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_CSR",
                "message": "Artifact is not a CSR.",
            },
        )
    if artifact.status == ArtifactStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CSR_DRAFT",
                "message": (
                    "Reviewer's Guide requires the CSR to be past DRAFT "
                    "(submit it for review first)."
                ),
            },
        )
    if artifact.current_version_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NO_CONTENT",
                "message": "CSR artifact has no version content.",
            },
        )
    version = await repo.get_version(artifact.current_version_id)
    csr_content = version.content or {}

    study = await StudyRepository(db).get(
        artifact.study_id, current_user.organization_id
    )

    adam_datasets = await _collect_adam_dataset_inventory(
        repo, artifact.study_id, current_user.organization_id
    )

    evidence_repo = ValidationEvidenceRepository(db)
    evidence, _total = await evidence_repo.list_for_study(
        artifact.study_id, current_user.organization_id, limit=10000
    )
    validation_summary: dict[str, int] = {}
    for record in evidence:
        key = record.status.value
        validation_summary[key] = validation_summary.get(key, 0) + 1

    pdf_bytes = generate_reviewers_guide_pdf(
        study_title=study.name,
        protocol_number=study.protocol_number,
        csr_content=csr_content,
        adam_datasets=adam_datasets,
        validation_summary=validation_summary,
    )
    filename = build_reviewers_guide_filename(study.protocol_number)

    audit = AuditService(db)
    await audit.log(
        action=AuditAction.ARTIFACT_EXPORTED,
        resource_type="artifact",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_id=artifact.id,
        after_state={
            "artifact_id": str(artifact.id),
            "artifact_version_id": str(artifact.current_version_id),
            "artifact_type": artifact.artifact_type.value,
            "format": "reviewers-guide-pdf",
            "filename": filename,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    graph = ContextGraphService(db)
    await graph.emit_event(
        organization_id=current_user.organization_id,
        study_id=artifact.study_id,
        event_type="ARTIFACT_EXPORTED",
        payload={
            "entity_type": "artifact",
            "entity_id": str(artifact.id),
            "artifact_type": artifact.artifact_type.value,
            "format": "reviewers-guide-pdf",
            "filename": filename,
            "artifact_version_id": str(artifact.current_version_id),
        },
        actor_user_id=current_user.id,
    )
    await db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
