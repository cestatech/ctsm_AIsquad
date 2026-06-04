"""Comment service — CRUD for artifact review comments with full audit trail."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.models.audit import AuditAction
from app.models.comment import Comment
from app.models.user import User
from app.repositories.comment_repository import CommentRepository
from app.schemas.comment import CommentCreate, CommentUpdate
from app.services.audit_service import AuditService


class CommentService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = CommentRepository(db)
        self._audit = AuditService(db)

    async def list(
        self,
        artifact_id: UUID,
        organization_id: UUID,
        include_resolved: bool = True,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[Comment], int]:
        offset = (page - 1) * page_size
        return await self._repo.list_by_artifact(
            artifact_id=artifact_id,
            organization_id=organization_id,
            include_resolved=include_resolved,
            limit=page_size,
            offset=offset,
        )

    async def create(
        self,
        body: CommentCreate,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Comment:
        if body.parent_id:
            parent = await self._repo.get_by_id(body.parent_id, actor.organization_id)
            if parent.artifact_id != body.artifact_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "PARENT_ARTIFACT_MISMATCH",
                        "message": "Parent comment belongs to a different artifact.",
                    },
                )

        comment = await self._repo.create(
            organization_id=actor.organization_id,
            artifact_id=body.artifact_id,
            artifact_version_id=body.artifact_version_id,
            parent_id=body.parent_id,
            author_id=actor.id,
            body=body.body,
        )
        await self._audit.log(
            action=AuditAction.COMMENT_CREATED,
            resource_type="comment",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=comment.id,
            after_state={"artifact_id": str(body.artifact_id), "body_length": len(body.body)},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return comment

    async def update(
        self,
        comment_id: UUID,
        body: CommentUpdate,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Comment:
        comment = await self._repo.get_by_id(comment_id, actor.organization_id)

        if comment.author_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PERMISSION_DENIED",
                    "message": "Only the comment author can edit this comment.",
                },
            )
        if comment.is_resolved:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "COMMENT_RESOLVED",
                    "message": "Resolved comments cannot be edited.",
                },
            )

        before = {"body": comment.body}
        comment.body = body.body

        await self._audit.log(
            action=AuditAction.COMMENT_UPDATED,
            resource_type="comment",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=comment.id,
            before_state=before,
            after_state={"body": body.body},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return comment

    async def resolve(
        self,
        comment_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Comment:
        comment = await self._repo.get_by_id(comment_id, actor.organization_id)
        if comment.is_resolved:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "ALREADY_RESOLVED", "message": "Comment is already resolved."},
            )

        comment.is_resolved = True
        comment.resolved_at = datetime.now(UTC)
        comment.resolved_by_id = actor.id

        await self._audit.log(
            action=AuditAction.COMMENT_RESOLVED,
            resource_type="comment",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=comment.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return comment

    async def delete(
        self,
        comment_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        comment = await self._repo.get_by_id(comment_id, actor.organization_id)

        is_author = comment.author_id == actor.id
        is_admin = actor.effective_role == Role.ADMIN

        if not is_author and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PERMISSION_DENIED",
                    "message": "Only the author or an Admin can delete this comment.",
                },
            )

        comment.is_deleted = True
        comment.deleted_at = datetime.now(UTC)

        await self._audit.log(
            action=AuditAction.COMMENT_DELETED,
            resource_type="comment",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=comment.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
