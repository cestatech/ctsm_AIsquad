"""User management service — invite, deactivate, activate, update."""

from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status

from app.core.permissions import Permission, check_permission
from app.core.security import hash_password
from app.models.audit import AuditAction
from app.models.user import User
from app.services.audit_service import AuditService


def _temp_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class UserService:
    """Business logic for user management within an organization."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._audit = AuditService(db)

    async def invite(
        self,
        organization_id: UUID,
        actor: User,
        email: str,
        full_name: str,
        is_admin: bool = False,
    ) -> tuple[User, str]:
        """
        Create a new organization member.

        Returns (user, temporary_password). The caller is responsible for
        communicating credentials until the email service is configured.
        """
        check_permission(actor, Permission.USER_MANAGE)

        existing = await self._db.execute(
            select(User).where(
                User.organization_id == organization_id,
                User.email == email.lower(),
                User.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "DUPLICATE_EMAIL",
                    "message": f"A user with email {email} already exists.",
                },
            )

        temp_pw = _temp_password()
        user = User(
            organization_id=organization_id,
            email=email.lower(),
            full_name=full_name,
            hashed_password=hash_password(temp_pw),
            is_active=True,
            is_system_admin=is_admin,
        )
        self._db.add(user)
        await self._db.flush()

        await self._audit.log(
            action=AuditAction.USER_CREATED,
            resource_type="user",
            organization_id=organization_id,
            actor_user_id=actor.id,
            resource_id=user.id,
            after_state=user.to_audit_dict(),
        )

        return user, temp_pw

    async def deactivate(
        self,
        user_id: UUID,
        organization_id: UUID,
        actor: User,
    ) -> User:
        """Deactivate a user account. Admin only."""
        check_permission(actor, Permission.USER_MANAGE)

        user = await self._get(user_id, organization_id)
        if user.id == actor.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "SELF_DEACTIVATION",
                    "message": "You cannot deactivate your own account.",
                },
            )

        before = user.to_audit_dict()
        user.is_active = False
        user.updated_at = datetime.now(UTC)

        await self._audit.log(
            action=AuditAction.USER_DEACTIVATED,
            resource_type="user",
            organization_id=organization_id,
            actor_user_id=actor.id,
            resource_id=user.id,
            before_state=before,
            after_state=user.to_audit_dict(),
        )
        return user

    async def activate(
        self,
        user_id: UUID,
        organization_id: UUID,
        actor: User,
    ) -> User:
        """Re-activate a deactivated user account. Admin only."""
        check_permission(actor, Permission.USER_MANAGE)

        user = await self._get(user_id, organization_id)
        before = user.to_audit_dict()
        user.is_active = True
        user.updated_at = datetime.now(UTC)

        await self._audit.log(
            action=AuditAction.USER_UPDATED,
            resource_type="user",
            organization_id=organization_id,
            actor_user_id=actor.id,
            resource_id=user.id,
            before_state=before,
            after_state=user.to_audit_dict(),
        )
        return user

    async def _get(self, user_id: UUID, organization_id: UUID) -> User:
        result = await self._db.execute(
            select(User).where(
                User.id == user_id,
                User.organization_id == organization_id,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "User not found."},
            )
        return user
