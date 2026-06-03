"""Repository for Study and StudyMember records.

All queries are scoped to organization_id from the caller's JWT.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.models.study import Study, StudyMember, StudyStatus


class StudyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Studies
    # ------------------------------------------------------------------

    async def get(self, study_id: UUID, organization_id: UUID) -> Study:
        result = await self._db.execute(
            select(Study).where(
                Study.id == study_id,
                Study.organization_id == organization_id,
                Study.deleted_at.is_(None),
            )
        )
        study = result.scalar_one_or_none()
        if study is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Study not found."},
            )
        return study

    async def get_by_protocol_number(
        self, protocol_number: str, organization_id: UUID
    ) -> Study | None:
        result = await self._db.execute(
            select(Study).where(
                Study.protocol_number == protocol_number,
                Study.organization_id == organization_id,
                Study.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        organization_id: UUID,
        status_filter: StudyStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Study], int]:
        filters = [
            Study.organization_id == organization_id,
            Study.deleted_at.is_(None),
        ]
        if status_filter is not None:
            filters.append(Study.status == status_filter)

        total_result = await self._db.execute(
            select(func.count()).select_from(Study).where(and_(*filters))
        )
        total = total_result.scalar_one()

        result = await self._db.execute(
            select(Study)
            .where(and_(*filters))
            .order_by(Study.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def create(self, study: Study) -> Study:
        self._db.add(study)
        await self._db.flush()
        await self._db.refresh(study)
        return study

    async def update(self, study: Study) -> Study:
        await self._db.flush()
        await self._db.refresh(study)
        return study

    # ------------------------------------------------------------------
    # Members
    # ------------------------------------------------------------------

    async def get_member(
        self, study_id: UUID, user_id: UUID, organization_id: UUID
    ) -> StudyMember | None:
        result = await self._db.execute(
            select(StudyMember).where(
                StudyMember.study_id == study_id,
                StudyMember.user_id == user_id,
                StudyMember.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_members(
        self, study_id: UUID, organization_id: UUID
    ) -> list[StudyMember]:
        from sqlalchemy.orm import selectinload

        result = await self._db.execute(
            select(StudyMember)
            .where(
                StudyMember.study_id == study_id,
                StudyMember.organization_id == organization_id,
            )
            .options(selectinload(StudyMember.user))
            .order_by(StudyMember.created_at.asc())
        )
        return list(result.scalars().all())

    async def add_member(self, member: StudyMember) -> StudyMember:
        self._db.add(member)
        await self._db.flush()
        await self._db.refresh(member)
        return member

    async def remove_member(self, member: StudyMember) -> None:
        await self._db.delete(member)
        await self._db.flush()

    async def get_member_role(
        self, study_id: UUID, user_id: UUID, organization_id: UUID
    ) -> Role | None:
        member = await self.get_member(study_id, user_id, organization_id)
        return member.role if member else None
