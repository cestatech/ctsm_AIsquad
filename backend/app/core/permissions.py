"""
RBAC permission model. Authoritative source for all role-based access rules.

SECURITY-CRITICAL: Changes require review by rbac-agent + architect-agent.
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from app.models.user import User


class Role(str, Enum):
    ADMIN = "ADMIN"
    CONTRIBUTOR = "CONTRIBUTOR"
    REVIEWER = "REVIEWER"


class Permission(str, Enum):
    ARTIFACT_CREATE = "artifact:create"
    ARTIFACT_EDIT = "artifact:edit"
    ARTIFACT_SUBMIT = "artifact:submit"
    ARTIFACT_APPROVE = "artifact:approve"
    ARTIFACT_REJECT = "artifact:reject"
    ARTIFACT_LOCK = "artifact:lock"
    ARTIFACT_AMEND = "artifact:amend"
    ARTIFACT_DELETE_DRAFT = "artifact:delete_draft"
    STUDY_CREATE = "study:create"
    STUDY_ARCHIVE = "study:archive"
    STUDY_MANAGE_MEMBERS = "study:manage_members"
    USER_MANAGE = "user:manage"
    ORG_MANAGE_SETTINGS = "org:manage_settings"
    AUDIT_READ = "audit:read"
    VALIDATION_RUN = "validation:run"
    AI_GENERATION_TRIGGER = "ai:generation_trigger"


PERMISSION_MATRIX: dict[Permission, list[Role]] = {
    Permission.ARTIFACT_CREATE:       [Role.ADMIN, Role.CONTRIBUTOR],
    Permission.ARTIFACT_EDIT:         [Role.ADMIN, Role.CONTRIBUTOR],
    Permission.ARTIFACT_SUBMIT:       [Role.ADMIN, Role.CONTRIBUTOR],
    Permission.ARTIFACT_APPROVE:      [Role.ADMIN, Role.REVIEWER],
    Permission.ARTIFACT_REJECT:       [Role.ADMIN, Role.REVIEWER],
    Permission.ARTIFACT_LOCK:         [Role.ADMIN],
    Permission.ARTIFACT_AMEND:        [Role.ADMIN],
    Permission.ARTIFACT_DELETE_DRAFT: [Role.ADMIN, Role.CONTRIBUTOR],
    Permission.STUDY_CREATE:          [Role.ADMIN],
    Permission.STUDY_ARCHIVE:         [Role.ADMIN],
    Permission.STUDY_MANAGE_MEMBERS:  [Role.ADMIN],
    Permission.USER_MANAGE:           [Role.ADMIN],
    Permission.ORG_MANAGE_SETTINGS:   [Role.ADMIN],
    Permission.AUDIT_READ:            [Role.ADMIN, Role.REVIEWER],
    Permission.VALIDATION_RUN:        [Role.ADMIN, Role.CONTRIBUTOR, Role.REVIEWER],
    Permission.AI_GENERATION_TRIGGER: [Role.ADMIN, Role.CONTRIBUTOR],
}


def has_permission(role: Role, permission: Permission) -> bool:
    """Check if a role has a given permission."""
    return role in PERMISSION_MATRIX.get(permission, [])


def check_permission(user: "User", permission: Permission, study_role: Role | None = None) -> None:
    """
    Enforce a permission check. Raises HTTP 403 if unauthorized.

    Uses study_role when available (study-scoped operations).
    Falls back to user's organization-level role.

    Call this as the FIRST operation in any service method that modifies data.
    """
    effective_role = study_role or user.effective_role
    if not has_permission(effective_role, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PERMISSION_DENIED",
                "message": f"Role {effective_role} does not have permission: {permission}",
            },
        )


def require_admin(user: "User") -> None:
    """Convenience: require Admin role. Raises 403 otherwise."""
    check_permission(user, Permission.USER_MANAGE)
