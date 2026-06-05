"""Repository for uploaded file metadata."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.upload import UploadedFile


class UploadRepository:
    """Database access for uploaded file metadata. All queries filter by organization_id."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(
        self, file_id: UUID, organization_id: UUID
    ) -> UploadedFile | None:
        """Return a single file by ID, scoped to the org."""
        result = await self._db.execute(
            select(UploadedFile).where(
                UploadedFile.id == file_id,
                UploadedFile.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def update(self, record: UploadedFile) -> UploadedFile:
        await self._db.flush()
        await self._db.refresh(record)
        return record

    async def create(self, **kwargs: object) -> UploadedFile:
        """Insert a new file metadata record."""
        record = UploadedFile(**kwargs)
        self._db.add(record)
        await self._db.flush()
        return record

    async def list_for_study(
        self,
        study_id: UUID,
        organization_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[UploadedFile], int]:
        """Return paginated file metadata for a study."""
        filters = [
            UploadedFile.study_id == study_id,
            UploadedFile.organization_id == organization_id,
        ]
        count_result = await self._db.execute(
            select(func.count()).select_from(UploadedFile).where(*filters)
        )
        total = count_result.scalar_one()

        result = await self._db.execute(
            select(UploadedFile)
            .where(*filters)
            .order_by(UploadedFile.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total
