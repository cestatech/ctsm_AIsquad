"""Repository for read-only audit log access."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditAction, AuditLog


class AuditRepository:
    """Read-only access to audit logs. Filtered strictly by organization_id."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list(
        self,
        organization_id: UUID,
        actor_user_id: UUID | None = None,
        action: AuditAction | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        filters = [AuditLog.organization_id == organization_id]
        if actor_user_id:
            filters.append(AuditLog.actor_user_id == actor_user_id)
        if action:
            filters.append(AuditLog.action == action)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)
        if resource_id:
            filters.append(AuditLog.resource_id == resource_id)
        if from_date:
            filters.append(AuditLog.created_at >= from_date)
        if to_date:
            filters.append(AuditLog.created_at <= to_date)

        count_result = await self._db.execute(
            select(func.count()).select_from(AuditLog).where(*filters)
        )
        total = count_result.scalar_one()

        result = await self._db.execute(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total
