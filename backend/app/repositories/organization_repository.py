from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization


class OrganizationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self._db.execute(
            select(Organization).where(
                Organization.slug == slug,
                Organization.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, org_id: UUID) -> Organization | None:
        result = await self._db.execute(
            select(Organization).where(
                Organization.id == org_id,
                Organization.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs: object) -> Organization:
        org = Organization(**kwargs)
        self._db.add(org)
        await self._db.flush()
        return org

    async def update(self, org: Organization, **fields: object) -> Organization:
        for key, value in fields.items():
            if value is not None:
                setattr(org, key, value)
        await self._db.flush()
        return org
