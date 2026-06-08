"""Submission packaging API — eCTD Module 5 bundle assembly and export."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.audit import AuditAction
from app.models.user import User
from app.schemas.submission import (
    SubmissionCreateResponse,
    SubmissionManifestResponse,
    SubmissionPackageListResponse,
    SubmissionPackageResponse,
    SubmissionReadinessResponse,
)
from app.services.audit_service import AuditService
from app.services.submission_executor import execute_submission_assembly
from app.services.submission_service import SubmissionService

router = APIRouter()


@router.get(
    "/studies/{study_id}/readiness",
    response_model=SubmissionReadinessResponse,
    summary="Submission packaging readiness check",
)
async def get_submission_readiness(
    study_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionReadinessResponse:
    """Check whether all required approved artifacts exist for packaging."""
    svc = SubmissionService(db)
    readiness = await svc.get_readiness(study_id, current_user.organization_id)
    return SubmissionReadinessResponse(
        study_id=readiness.study_id,
        ready=readiness.ready,
        issues=readiness.issues,
        required_artifacts=readiness.required_artifacts,
    )


@router.post(
    "/studies/{study_id}/create",
    response_model=SubmissionCreateResponse,
    summary="Create eCTD submission package",
)
async def create_submission_package(
    study_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionCreateResponse:
    """Validate readiness, create DRAFT package, queue async assembly. Admin only."""
    svc = SubmissionService(db)
    package = await svc.create_submission_package(
        study_id=study_id,
        actor=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    background_tasks.add_task(
        execute_submission_assembly,
        package.id,
        current_user.organization_id,
    )
    return SubmissionCreateResponse(
        package_id=package.id,
        status=package.status,
        artifact_ids=package.artifact_ids,
    )


@router.get(
    "/studies/{study_id}",
    response_model=SubmissionPackageListResponse,
    summary="List submission packages for study",
)
async def list_study_submissions(
    study_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionPackageListResponse:
    """Return all submission packages for a study."""
    svc = SubmissionService(db)
    items, total = await svc.list_for_study(study_id, current_user.organization_id)
    return SubmissionPackageListResponse(
        items=[SubmissionPackageResponse.model_validate(p) for p in items],
        total=total,
    )


@router.get(
    "/{package_id}/manifest",
    response_model=SubmissionManifestResponse,
    summary="Submission package manifest with checksums",
)
async def get_submission_manifest(
    package_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionManifestResponse:
    """Return JSON manifest. Reviewer or Admin."""
    svc = SubmissionService(db)
    package = await svc.get_manifest(package_id, current_user)
    return SubmissionManifestResponse(
        package_id=package.id,
        study_id=package.study_id,
        status=package.status,
        package_checksum=package.package_checksum,
        manifest=package.manifest,
    )


@router.get(
    "/{package_id}/download",
    summary="Download submission package as zip",
)
async def download_submission_package(
    package_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download eCTD folder structure as .zip. Admin only."""
    svc = SubmissionService(db)
    zip_bytes = await svc.build_zip_bytes(package_id, current_user)

    audit = AuditService(db)
    await audit.log(
        action=AuditAction.SUBMISSION_PACKAGE_EXPORTED,
        resource_type="submission_package",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_id=package_id,
        after_state={"format": "zip"},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="submission_{package_id}.zip"'
        },
    )
