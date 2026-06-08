"""Artifacts API — artifact lifecycle management.

Permissions (enforced in service layer):
  - List / Get: any authenticated user (org-scoped)
  - Create: Admin, Contributor
  - Submit for review: Admin, Contributor
  - Approve / Reject: Admin, Reviewer (via /approvals)
  - Lock: Admin
  - Amend: Admin
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.artifact_repository import ArtifactRepository
from app.schemas.artifact import (
    ArtifactCreate,
    ArtifactListResponse,
    ArtifactResponse,
    ArtifactUpdate,
    ArtifactVersionResponse,
)
from app.services.artifact_service import ArtifactService
from app.services.sdtm_define_service import build_define_xml

router = APIRouter()


@router.get("", response_model=ArtifactListResponse, summary="List artifacts")
async def list_artifacts(
    study_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactListResponse:
    """List artifacts for the org, optionally filtered by study."""
    repo = ArtifactRepository(db)
    offset = (page - 1) * page_size
    if study_id:
        items, total = await repo.list_by_study(
            study_id, current_user.organization_id, limit=page_size, offset=offset
        )
    else:
        items, total = await repo.list_all(
            current_user.organization_id, limit=page_size, offset=offset
        )
    return ArtifactListResponse(
        items=[ArtifactResponse.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
    )


@router.post(
    "",
    response_model=ArtifactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create artifact",
)
async def create_artifact(
    body: ArtifactCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Create a new artifact in DRAFT status. Contributor or Admin."""
    svc = ArtifactService(db)
    artifact = await svc.create_artifact(
        organization_id=current_user.organization_id,
        study_id=body.study_id,
        user=current_user,
        artifact_type=body.artifact_type,
        name=body.name,
        description=body.description,
        content=body.content or {},
        change_summary=body.change_summary,
    )
    return ArtifactResponse.model_validate(artifact)


@router.get("/{artifact_id}", response_model=ArtifactResponse, summary="Get artifact")
async def get_artifact(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Fetch a single artifact by ID, scoped to the authenticated org."""
    repo = ArtifactRepository(db)
    artifact = await repo.get_by_id(artifact_id, current_user.organization_id)
    return ArtifactResponse.model_validate(artifact)


@router.patch(
    "/{artifact_id}",
    response_model=ArtifactResponse,
    summary="Update artifact content",
)
async def update_artifact_content(
    artifact_id: UUID,
    body: ArtifactUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Update content of a DRAFT or REJECTED artifact, creating a new version. Contributor or Admin."""
    svc = ArtifactService(db)
    artifact = await svc.update_artifact_content(
        artifact_id=artifact_id,
        organization_id=current_user.organization_id,
        user=current_user,
        content=body.content,
        change_summary=body.change_summary,
    )
    return ArtifactResponse.model_validate(artifact)


@router.get(
    "/{artifact_id}/download",
    summary="Download artifact content as JSON",
    response_class=Response,
)
async def download_artifact(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export artifact metadata and current version content as a JSON file."""
    svc = ArtifactService(db)
    artifact, content = await svc.get_artifact_export(
        artifact_id, current_user.organization_id
    )
    payload = {
        "artifact": ArtifactResponse.model_validate(artifact).model_dump(mode="json"),
        "version_number": artifact.current_version_number,
        "content": content,
        "exported_at": datetime.now(UTC).isoformat(),
    }
    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in artifact.name
    )
    return Response(
        content=json.dumps(payload, indent=2, default=str),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}.json"'
        },
    )


@router.get(
    "/{artifact_id}/download-csv",
    summary="Download synthetic artifact as CSV",
    response_class=Response,
)
async def download_artifact_csv(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export synthetic patient-level data as a CSV file."""
    svc = ArtifactService(db)
    filename, csv_body = await svc.get_artifact_csv_export(
        artifact_id, current_user.organization_id
    )
    return Response(
        content=csv_body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete(
    "/{artifact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove artifact from study",
)
async def delete_artifact(
    artifact_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Soft-delete a DRAFT artifact. Creator or Admin only."""
    svc = ArtifactService(db)
    await svc.delete_artifact(
        artifact_id=artifact_id,
        organization_id=current_user.organization_id,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{artifact_id}/define-xml",
    summary="Export define.xml for SDTM dataset artifact",
    response_class=Response,
)
async def export_define_xml(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Build a minimal CDISC define.xml 2.1 document from SDTM artifact content."""
    repo = ArtifactRepository(db)
    artifact = await repo.get_by_id(artifact_id, current_user.organization_id)
    version = await repo.get_version(artifact.current_version_id)
    xml_content = build_define_xml(version.content or {})
    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in artifact.name
    )
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_define.xml"'
        },
    )


@router.get(
    "/{artifact_id}/versions",
    response_model=list[ArtifactVersionResponse],
    summary="List artifact versions",
)
async def list_artifact_versions(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ArtifactVersionResponse]:
    """Return all version snapshots for an artifact, oldest first."""
    repo = ArtifactRepository(db)
    versions = await repo.list_versions(artifact_id, current_user.organization_id)
    return [ArtifactVersionResponse.model_validate(v) for v in versions]


@router.post(
    "/{artifact_id}/submit",
    response_model=ArtifactResponse,
    summary="Submit for review",
)
async def submit_for_review(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Transition artifact from DRAFT → IN_REVIEW. Contributor or Admin."""
    svc = ArtifactService(db)
    artifact = await svc.submit_for_review(
        artifact_id, current_user.organization_id, current_user
    )
    return ArtifactResponse.model_validate(artifact)


@router.post(
    "/{artifact_id}/lock",
    response_model=ArtifactResponse,
    summary="Lock artifact",
)
async def lock_artifact(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Lock an APPROVED artifact permanently. Admin only."""
    svc = ArtifactService(db)
    artifact = await svc.lock(artifact_id, current_user.organization_id, current_user)
    return ArtifactResponse.model_validate(artifact)


@router.post(
    "/{artifact_id}/amend",
    response_model=ArtifactResponse,
    summary="Amend locked artifact",
)
async def amend_artifact(
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Begin amendment of a LOCKED artifact. Admin only."""
    svc = ArtifactService(db)
    artifact = await svc.amend(artifact_id, current_user.organization_id, current_user)
    return ArtifactResponse.model_validate(artifact)
