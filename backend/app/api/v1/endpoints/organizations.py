"""Organizations API — read and update the authenticated user's organization.

Permissions:
  - Read: any authenticated user
  - Update settings: Admin only
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.permissions import Permission, check_permission
from app.models.audit import AuditAction
from app.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.organization import OrgResponse, OrgSettingsUpdate
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("/me", response_model=OrgResponse, summary="Get current organization")
async def get_my_organization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgResponse:
    """Return the organization that the authenticated user belongs to."""
    repo = OrganizationRepository(db)
    org = await repo.get_by_id(current_user.organization_id)
    return OrgResponse.model_validate(org)


@router.patch("/me", response_model=OrgResponse, summary="Update organization settings")
async def update_my_organization(
    body: OrgSettingsUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgResponse:
    """Update name, description, logo, or settings blob. Admin only."""
    check_permission(current_user, Permission.ORG_MANAGE_SETTINGS)

    repo = OrganizationRepository(db)
    audit = AuditService(db)

    org = await repo.get_by_id(current_user.organization_id)
    before = org.to_audit_dict()

    update_fields = body.model_dump(exclude_none=True)
    if update_fields.get("settings"):
        update_fields["settings"] = {**org.settings, **update_fields["settings"]}

    org = await repo.update(org, **update_fields)

    await audit.log(
        action=AuditAction.ORG_SETTINGS_CHANGED,
        resource_type="organization",
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        resource_id=org.id,
        before_state=before,
        after_state=org.to_audit_dict(),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return OrgResponse.model_validate(org)
