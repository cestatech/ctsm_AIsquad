from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import RefreshToken, User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_email(self, organization_id: UUID, email: str) -> User | None:
        result = await self._db.execute(
            select(User).where(
                User.organization_id == organization_id,
                User.email == email,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email_any_org(self, email: str) -> User | None:
        result = await self._db.execute(
            select(User).where(
                User.email == email,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._db.execute(
            select(User).where(
                User.id == user_id,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs: object) -> User:
        user = User(**kwargs)
        self._db.add(user)
        await self._db.flush()
        return user

    async def increment_failed_login(self, user: User) -> None:
        user.failed_login_count += 1
        self._db.add(user)

    async def reset_failed_login(self, user: User) -> None:
        user.failed_login_count = 0
        user.locked_until = None
        self._db.add(user)

    async def update_last_login(self, user: User) -> None:
        user.last_login_at = datetime.now(UTC)
        self._db.add(user)

    async def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        result = await self._db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def create_refresh_token(self, **kwargs: object) -> RefreshToken:
        token = RefreshToken(**kwargs)
        self._db.add(token)
        await self._db.flush()
        return token

    async def revoke_refresh_token(self, token: RefreshToken) -> None:
        token.is_revoked = True
        token.revoked_at = datetime.now(UTC)
        self._db.add(token)
