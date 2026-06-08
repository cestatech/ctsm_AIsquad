"""Repository for AI generation job read/write access."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generation import GenerationJob, GenerationJobStatus


class GenerationRepository:
    """Database access for generation jobs. All queries filter by organization_id."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, job_id: UUID, organization_id: UUID) -> GenerationJob:
        result = await self._db.execute(
            select(GenerationJob).where(
                GenerationJob.id == job_id,
                GenerationJob.organization_id == organization_id,
            )
        )
        job = result.scalar_one_or_none()
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Generation job not found."},
            )
        return job

    async def list(
        self,
        organization_id: UUID,
        study_id: UUID | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[GenerationJob], int]:
        filters = [GenerationJob.organization_id == organization_id]
        if study_id:
            filters.append(GenerationJob.study_id == study_id)

        count_result = await self._db.execute(
            select(func.count()).select_from(GenerationJob).where(*filters)
        )
        total = count_result.scalar_one()

        result = await self._db.execute(
            select(GenerationJob)
            .where(*filters)
            .order_by(GenerationJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def create(self, **kwargs: object) -> GenerationJob:
        job = GenerationJob(**kwargs)
        self._db.add(job)
        await self._db.flush()
        return job

    async def list_pending(
        self, organization_id: UUID, *, limit: int = 20
    ) -> list[GenerationJob]:
        result = await self._db.execute(
            select(GenerationJob)
            .where(
                GenerationJob.organization_id == organization_id,
                GenerationJob.status == GenerationJobStatus.PENDING,
            )
            .order_by(GenerationJob.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
