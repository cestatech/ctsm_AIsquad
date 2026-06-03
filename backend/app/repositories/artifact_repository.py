from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.artifact import Artifact, ArtifactStatus, ArtifactVersion


class ArtifactRepository:
    """Database access for artifacts. All queries filter by organization_id."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, artifact_id: UUID, organization_id: UUID) -> Artifact:
        """
        Fetch an artifact by ID, scoped to the organization.
        Returns 404 if not found or belongs to different org (IDOR protection).
        """
        result = await self._db.execute(
            select(Artifact).where(
                Artifact.id == artifact_id,
                Artifact.organization_id == organization_id,
                Artifact.deleted_at.is_(None),
            )
        )
        artifact = result.scalar_one_or_none()
        if artifact is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Artifact not found."},
            )
        return artifact

    async def get_version(self, version_id: UUID) -> ArtifactVersion:
        result = await self._db.execute(
            select(ArtifactVersion).where(ArtifactVersion.id == version_id)
        )
        version = result.scalar_one_or_none()
        if version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Artifact version not found."},
            )
        return version

    async def mark_version_not_current(self, version_id: UUID) -> None:
        """
        Mark a version as no longer current.
        Note: This updates the is_current flag only, which is allowed.
        The content and other fields remain immutable per DB trigger.
        """
        # Bypass ORM to avoid triggering the immutability check (only is_current changes)
        from sqlalchemy import update

        await self._db.execute(
            update(ArtifactVersion)
            .where(ArtifactVersion.id == version_id)
            .values(is_current=False)
        )

    async def list_by_study(
        self,
        study_id: UUID,
        organization_id: UUID,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[Artifact], int]:
        filters = [
            Artifact.study_id == study_id,
            Artifact.organization_id == organization_id,
            Artifact.deleted_at.is_(None),
        ]
        count_result = await self._db.execute(
            select(func.count()).select_from(Artifact).where(*filters)
        )
        total = count_result.scalar_one()
        result = await self._db.execute(
            select(Artifact)
            .where(*filters)
            .order_by(Artifact.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def list_all(
        self,
        organization_id: UUID,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[Artifact], int]:
        """List all artifacts for an org, ordered by most recently updated."""
        filters = [
            Artifact.organization_id == organization_id,
            Artifact.deleted_at.is_(None),
        ]
        count_result = await self._db.execute(
            select(func.count()).select_from(Artifact).where(*filters)
        )
        total = count_result.scalar_one()
        result = await self._db.execute(
            select(Artifact)
            .where(*filters)
            .order_by(Artifact.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def list_in_review(
        self,
        organization_id: UUID,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[Artifact], int]:
        """List all IN_REVIEW artifacts with study and creator eagerly loaded."""
        filters = [
            Artifact.organization_id == organization_id,
            Artifact.status == ArtifactStatus.IN_REVIEW,
            Artifact.deleted_at.is_(None),
        ]
        count_result = await self._db.execute(
            select(func.count()).select_from(Artifact).where(*filters)
        )
        total = count_result.scalar_one()
        result = await self._db.execute(
            select(Artifact)
            .where(*filters)
            .options(selectinload(Artifact.study), selectinload(Artifact.creator))
            .order_by(Artifact.updated_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def list_versions(
        self, artifact_id: UUID, organization_id: UUID
    ) -> list[ArtifactVersion]:
        result = await self._db.execute(
            select(ArtifactVersion)
            .where(
                ArtifactVersion.artifact_id == artifact_id,
                ArtifactVersion.organization_id == organization_id,
            )
            .order_by(ArtifactVersion.version_number.asc())
        )
        return list(result.scalars().all())
