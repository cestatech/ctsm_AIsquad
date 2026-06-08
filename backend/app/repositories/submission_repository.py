"""Repository for submission package records."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.submission import SubmissionPackage


class SubmissionRepository:
    """Database access for submission packages. All queries filter by organization."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(
        self, package_id: UUID, organization_id: UUID
    ) -> SubmissionPackage:
        result = await self._db.execute(
            select(SubmissionPackage).where(
                SubmissionPackage.id == package_id,
                SubmissionPackage.organization_id == organization_id,
            )
        )
        package = result.scalar_one_or_none()
        if package is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "NOT_FOUND",
                    "message": "Submission package not found.",
                },
            )
        return package

    async def list_for_study(
        self,
        study_id: UUID,
        organization_id: UUID,
        *,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[SubmissionPackage], int]:
        filters = [
            SubmissionPackage.study_id == study_id,
            SubmissionPackage.organization_id == organization_id,
        ]
        count_result = await self._db.execute(
            select(func.count()).select_from(SubmissionPackage).where(*filters)
        )
        total = count_result.scalar_one()
        result = await self._db.execute(
            select(SubmissionPackage)
            .where(*filters)
            .order_by(SubmissionPackage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def create(self, **kwargs: object) -> SubmissionPackage:
        package = SubmissionPackage(**kwargs)
        self._db.add(package)
        await self._db.flush()
        return package

    async def update(self, package: SubmissionPackage) -> SubmissionPackage:
        await self._db.flush()
        return package
