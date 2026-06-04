"""Repository for comment read/write access."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment


class CommentRepository:
    """Database access for comments. All queries filter by organization_id."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, comment_id: UUID, organization_id: UUID) -> Comment:
        result = await self._db.execute(
            select(Comment)
            .where(
                Comment.id == comment_id,
                Comment.organization_id == organization_id,
                Comment.is_deleted.is_(False),
            )
            .options(selectinload(Comment.author))
        )
        comment = result.scalar_one_or_none()
        if comment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Comment not found."},
            )
        return comment

    async def list_by_artifact(
        self,
        artifact_id: UUID,
        organization_id: UUID,
        include_resolved: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Comment], int]:
        filters = [
            Comment.artifact_id == artifact_id,
            Comment.organization_id == organization_id,
            Comment.is_deleted.is_(False),
            Comment.parent_id.is_(None),
        ]
        if not include_resolved:
            filters.append(Comment.is_resolved.is_(False))

        count_result = await self._db.execute(
            select(func.count()).select_from(Comment).where(*filters)
        )
        total = count_result.scalar_one()

        result = await self._db.execute(
            select(Comment)
            .where(*filters)
            .options(
                selectinload(Comment.author),
                selectinload(Comment.replies).selectinload(Comment.author),
            )
            .order_by(Comment.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def create(self, **kwargs: object) -> Comment:
        comment = Comment(**kwargs)
        self._db.add(comment)
        await self._db.flush()
        await self._db.refresh(comment, ["author"])
        return comment
