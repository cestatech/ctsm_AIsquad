"""Audit Log API — read-only access to the immutable audit trail.

Permissions:
  - Read: Admin, Reviewer (org-scoped)
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.permissions import Permission, check_permission
from app.models.audit import AuditAction
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import AuditLogListResponse, AuditLogResponse

router = APIRouter()


@router.get("", response_model=AuditLogListResponse, summary="List audit logs")
async def list_audit_logs(
    actor_user_id: UUID | None = Query(None),
    action: AuditAction | None = Query(None),
    resource_type: str | None = Query(None),
    resource_id: UUID | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """List audit log entries for the authenticated org. Admin and Reviewer only."""
    check_permission(current_user, Permission.AUDIT_READ)
    repo = AuditRepository(db)
    items, total = await repo.list(
        organization_id=current_user.organization_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        from_date=from_date,
        to_date=to_date,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
    )
