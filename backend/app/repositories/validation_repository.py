"""Repository for validation run read/write access."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.validation import ValidationRun


class ValidationRepository:
    """Database access for validation runs. All queries filter by organization_id."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, run_id: UUID, organization_id: UUID) -> ValidationRun:
        result = await self._db.execute(
            select(ValidationRun).where(
                ValidationRun.id == run_id,
                ValidationRun.organization_id == organization_id,
            )
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Validation run not found."},
            )
        return run

    async def list(
        self,
        organization_id: UUID,
        artifact_id: UUID | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[ValidationRun], int]:
        filters = [ValidationRun.organization_id == organization_id]
        if artifact_id:
            filters.append(ValidationRun.artifact_id == artifact_id)

        count_result = await self._db.execute(
            select(func.count()).select_from(ValidationRun).where(*filters)
        )
        total = count_result.scalar_one()

        result = await self._db.execute(
            select(ValidationRun)
            .where(*filters)
            .order_by(ValidationRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def create(self, **kwargs: object) -> ValidationRun:
        run = ValidationRun(**kwargs)
        self._db.add(run)
        await self._db.flush()
        return run
