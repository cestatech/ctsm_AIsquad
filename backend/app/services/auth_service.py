from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, RateLimitError
from app.core.security import (
    create_access_token,
    create_refresh_token_value,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.audit import AuditAction
from app.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest
from app.services.audit_service import AuditService

settings = get_settings()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._users = UserRepository(db)
        self._orgs = OrganizationRepository(db)
        self._audit = AuditService(db)

    async def register(
        self,
        req: RegisterRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        """Create a new organization and its first admin user."""
        if await self._orgs.get_by_slug(req.organization_slug):
            raise AuthenticationError("Organization slug is already taken.")

        org = await self._orgs.create(
            name=req.organization_name,
            slug=req.organization_slug,
        )
        user = await self._users.create(
            organization_id=org.id,
            email=req.email.lower(),
            full_name=req.full_name,
            hashed_password=hash_password(req.password),
            is_system_admin=True,
            email_verified=False,
        )

        await self._audit.log(
            action=AuditAction.USER_CREATED,
            resource_type="user",
            organization_id=org.id,
            actor_user_id=user.id,
            resource_id=user.id,
            after_state=user.to_audit_dict(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        access_token = create_access_token(user.id, org.id, user.email)
        refresh_token = await self._issue_refresh_token(user, ip_address, user_agent)
        return user, access_token, refresh_token

    async def login(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        """Verify credentials and issue tokens."""
        user = await self._users.get_by_email_any_org(email.lower())

        if user is None:
            raise AuthenticationError("Invalid email or password.")

        if user.locked_until and user.locked_until > datetime.now(UTC):
            remaining = int((user.locked_until - datetime.now(UTC)).total_seconds())
            raise RateLimitError(retry_after_seconds=remaining)

        if not verify_password(password, user.hashed_password):
            await self._users.increment_failed_login(user)
            if user.failed_login_count >= settings.AUTH_MAX_FAILED_ATTEMPTS:
                user.locked_until = datetime.now(UTC) + timedelta(
                    minutes=settings.AUTH_LOCKOUT_MINUTES
                )
                self._db.add(user)
            await self._audit.log(
                action=AuditAction.USER_LOGIN_FAILED,
                resource_type="user",
                organization_id=user.organization_id,
                resource_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise AuthenticationError("Invalid email or password.")

        if not user.is_active:
            raise AuthenticationError("This account has been deactivated.")

        await self._users.reset_failed_login(user)
        await self._users.update_last_login(user)
        await self._audit.log(
            action=AuditAction.USER_LOGIN,
            resource_type="user",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            resource_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        access_token = create_access_token(user.id, user.organization_id, user.email)
        refresh_token = await self._issue_refresh_token(user, ip_address, user_agent)
        return user, access_token, refresh_token

    async def refresh(
        self,
        token_value: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str]:
        """Rotate refresh token and issue new access token."""
        token = await self._users.get_refresh_token(hash_token(token_value))

        if token is None or token.expires_at < datetime.now(UTC):
            raise AuthenticationError("Invalid or expired refresh token.")

        await self._users.revoke_refresh_token(token)

        user = await self._users.get_by_id(token.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("User not found or deactivated.")

        await self._audit.log(
            action=AuditAction.USER_TOKEN_REFRESHED,
            resource_type="user",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            resource_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        new_access = create_access_token(user.id, user.organization_id, user.email)
        new_refresh = await self._issue_refresh_token(user, ip_address, user_agent)
        return new_access, new_refresh

    async def change_password(
        self,
        actor: User,
        current_password: str,
        new_password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Verify the current password and update to the new password."""
        from app.core.exceptions import AuthenticationError

        if not verify_password(current_password, actor.hashed_password):
            raise AuthenticationError("Current password is incorrect.")

        actor.hashed_password = hash_password(new_password)
        self._db.add(actor)

        await self._audit.log(
            action=AuditAction.USER_UPDATED,
            resource_type="user",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=actor.id,
            after_state={"password_changed": True},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self._db.commit()

    async def logout(self, token_value: str) -> None:
        """Revoke a refresh token."""
        token = await self._users.get_refresh_token(hash_token(token_value))
        if token:
            await self._users.revoke_refresh_token(token)

    async def _issue_refresh_token(
        self,
        user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> str:
        value = create_refresh_token_value()
        await self._users.create_refresh_token(
            user_id=user.id,
            token_hash=hash_token(value),
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            is_revoked=False,
            created_at=datetime.now(UTC),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return value
