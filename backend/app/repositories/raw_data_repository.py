"""Repositories for RawDataset, RawField, and FieldMappingVersion."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.raw_data import FieldMappingVersion, RawDataset, RawField


class RawDatasetRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, **kwargs: object) -> RawDataset:
        record = RawDataset(**kwargs)
        self._db.add(record)
        await self._db.flush()
        return record

    async def get(self, dataset_id: UUID, organization_id: UUID) -> RawDataset | None:
        result = await self._db.execute(
            select(RawDataset).where(
                RawDataset.id == dataset_id,
                RawDataset.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_file(
        self, uploaded_file_id: UUID, organization_id: UUID
    ) -> list[RawDataset]:
        result = await self._db.execute(
            select(RawDataset)
            .where(
                RawDataset.uploaded_file_id == uploaded_file_id,
                RawDataset.organization_id == organization_id,
            )
            .order_by(RawDataset.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_study(
        self, study_id: UUID, organization_id: UUID
    ) -> list[RawDataset]:
        """All parsed datasets across every upload in a study."""
        result = await self._db.execute(
            select(RawDataset)
            .where(
                RawDataset.study_id == study_id,
                RawDataset.organization_id == organization_id,
            )
            .order_by(RawDataset.created_at.asc())
        )
        return list(result.scalars().all())

    async def update(self, dataset: RawDataset) -> RawDataset:
        await self._db.flush()
        await self._db.refresh(dataset)
        return dataset


class RawFieldRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, **kwargs: object) -> RawField:
        record = RawField(**kwargs)
        self._db.add(record)
        await self._db.flush()
        return record

    async def get(self, field_id: UUID, organization_id: UUID) -> RawField | None:
        result = await self._db.execute(
            select(RawField).where(
                RawField.id == field_id,
                RawField.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_dataset(
        self, dataset_id: UUID, organization_id: UUID
    ) -> list[RawField]:
        result = await self._db.execute(
            select(RawField)
            .where(
                RawField.raw_dataset_id == dataset_id,
                RawField.organization_id == organization_id,
            )
            .order_by(RawField.column_index.asc())
        )
        return list(result.scalars().all())

    async def count_for_dataset(self, dataset_id: UUID, organization_id: UUID) -> int:
        result = await self._db.execute(
            select(func.count())
            .select_from(RawField)
            .where(
                RawField.raw_dataset_id == dataset_id,
                RawField.organization_id == organization_id,
            )
        )
        return result.scalar_one()

    async def update(self, field: RawField) -> RawField:
        await self._db.flush()
        await self._db.refresh(field)
        return field


class FieldMappingVersionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, **kwargs: object) -> FieldMappingVersion:
        record = FieldMappingVersion(**kwargs)
        self._db.add(record)
        await self._db.flush()
        return record

    async def list_for_field(
        self, raw_field_id: UUID, organization_id: UUID
    ) -> list[FieldMappingVersion]:
        result = await self._db.execute(
            select(FieldMappingVersion)
            .where(
                FieldMappingVersion.raw_field_id == raw_field_id,
                FieldMappingVersion.organization_id == organization_id,
            )
            .order_by(FieldMappingVersion.version_number.asc())
        )
        return list(result.scalars().all())
