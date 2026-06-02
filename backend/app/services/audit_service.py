"""
Audit log ingestion service. Every data-modifying operation must call this.

COMPLIANCE-CRITICAL: Changes require review by audit-compliance-agent + architect-agent.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditAction, AuditLog


class AuditService:
    """
    Writes immutable audit log records.

    Call log() as part of every operation that creates, modifies, or deletes
    tenant data. The call must happen within the same database transaction
    as the operation itself, so that either both succeed or both fail.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def log(
        self,
        action: AuditAction,
        resource_type: str,
        organization_id: UUID | None = None,
        actor_user_id: UUID | None = None,
        resource_id: UUID | None = None,
        before_state: dict | None = None,
        after_state: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        """
        Create an immutable audit log record.

        This method must be called within the same transaction as the operation
        being audited. Do not commit separately.
        """
        entry = AuditLog(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=before_state,
            after_state=after_state,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            metadata=metadata or {},
            created_at=datetime.now(UTC),
        )
        self._db.add(entry)
        return entry
