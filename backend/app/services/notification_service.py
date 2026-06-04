"""In-platform notification service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType


class NotificationService:
    """Create and manage per-user notifications."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        organization_id: UUID,
        recipient_id: UUID,
        notification_type: NotificationType,
        title: str,
        body: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> Notification:
        """Create a notification record for a user."""
        n = Notification(
            organization_id=organization_id,
            recipient_id=recipient_id,
            type=notification_type,
            title=title,
            body=body,
            resource_type=resource_type,
            resource_id=resource_id,
            is_read=False,
            created_at=datetime.now(UTC),
        )
        self._db.add(n)
        await self._db.flush()
        return n

    async def list_for_user(
        self,
        user_id: UUID,
        organization_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Notification], int]:
        """Return paginated notifications for a user."""
        filters = [
            Notification.recipient_id == user_id,
            Notification.organization_id == organization_id,
        ]
        if unread_only:
            filters.append(Notification.is_read.is_(False))

        count_result = await self._db.execute(
            select(func.count()).select_from(Notification).where(*filters)
        )
        total = count_result.scalar_one()

        result = await self._db.execute(
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def mark_read(
        self,
        notification_id: UUID,
        user_id: UUID,
        organization_id: UUID,
    ) -> Notification | None:
        """Mark a single notification as read. Returns None if not found."""
        result = await self._db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.recipient_id == user_id,
                Notification.organization_id == organization_id,
            )
        )
        n = result.scalar_one_or_none()
        if n is None:
            return None
        if not n.is_read:
            n.is_read = True
            n.read_at = datetime.now(UTC)
        return n

    async def mark_all_read(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> int:
        """Mark all unread notifications for a user as read. Returns count updated."""
        now = datetime.now(UTC)
        result = await self._db.execute(
            update(Notification)
            .where(
                Notification.recipient_id == user_id,
                Notification.organization_id == organization_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=now)
        )
        return result.rowcount

    async def unread_count(self, user_id: UUID, organization_id: UUID) -> int:
        """Return the count of unread notifications for a user."""
        result = await self._db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_id == user_id,
                Notification.organization_id == organization_id,
                Notification.is_read.is_(False),
            )
        )
        return result.scalar_one()
