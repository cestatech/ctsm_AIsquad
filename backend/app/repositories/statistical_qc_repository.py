"""Repository for statistical_program_qc_runs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.statistical_qc import StatisticalProgramQCRun, StatisticalQCWorkflow


class StatisticalQCRepository:
    """Database access for dual-programmer QC runs."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, run: StatisticalProgramQCRun) -> StatisticalProgramQCRun:
        self._db.add(run)
        await self._db.flush()
        return run

    async def get(
        self, run_id: UUID, organization_id: UUID
    ) -> StatisticalProgramQCRun | None:
        result = await self._db.execute(
            select(StatisticalProgramQCRun).where(
                StatisticalProgramQCRun.id == run_id,
                StatisticalProgramQCRun.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_runs(
        self,
        organization_id: UUID,
        *,
        study_id: UUID | None = None,
        output_artifact_id: UUID | None = None,
        workflow_step: StatisticalQCWorkflow | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[StatisticalProgramQCRun], int]:
        filters = [StatisticalProgramQCRun.organization_id == organization_id]
        if study_id is not None:
            filters.append(StatisticalProgramQCRun.study_id == study_id)
        if output_artifact_id is not None:
            filters.append(
                StatisticalProgramQCRun.output_artifact_id == output_artifact_id
            )
        if workflow_step is not None:
            filters.append(StatisticalProgramQCRun.workflow_step == workflow_step)

        count_result = await self._db.execute(
            select(func.count()).select_from(StatisticalProgramQCRun).where(*filters)
        )
        total = count_result.scalar_one()

        result = await self._db.execute(
            select(StatisticalProgramQCRun)
            .where(*filters)
            .order_by(StatisticalProgramQCRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total
