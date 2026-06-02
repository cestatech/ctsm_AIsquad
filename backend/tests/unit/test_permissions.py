"""
Unit tests for the RBAC permission model.

These tests are the authoritative verification that the permission matrix
is correctly implemented. All role × permission combinations must be tested.
"""
import pytest

from app.core.permissions import (
    Permission,
    Role,
    check_permission,
    has_permission,
)


class TestPermissionMatrix:
    """Verify every cell in the permission matrix."""

    @pytest.mark.parametrize("permission", list(Permission))
    def test_admin_has_all_permissions(self, permission: Permission):
        assert has_permission(Role.ADMIN, permission) is True

    @pytest.mark.parametrize("permission,expected", [
        (Permission.ARTIFACT_CREATE, True),
        (Permission.ARTIFACT_EDIT, True),
        (Permission.ARTIFACT_SUBMIT, True),
        (Permission.ARTIFACT_APPROVE, False),
        (Permission.ARTIFACT_REJECT, False),
        (Permission.ARTIFACT_LOCK, False),
        (Permission.ARTIFACT_AMEND, False),
        (Permission.ARTIFACT_DELETE_DRAFT, True),
        (Permission.STUDY_CREATE, False),
        (Permission.STUDY_ARCHIVE, False),
        (Permission.STUDY_MANAGE_MEMBERS, False),
        (Permission.USER_MANAGE, False),
        (Permission.ORG_MANAGE_SETTINGS, False),
        (Permission.AUDIT_READ, False),
        (Permission.VALIDATION_RUN, True),
        (Permission.AI_GENERATION_TRIGGER, True),
    ])
    def test_contributor_permissions(self, permission: Permission, expected: bool):
        assert has_permission(Role.CONTRIBUTOR, permission) is expected

    @pytest.mark.parametrize("permission,expected", [
        (Permission.ARTIFACT_CREATE, False),
        (Permission.ARTIFACT_EDIT, False),
        (Permission.ARTIFACT_SUBMIT, False),
        (Permission.ARTIFACT_APPROVE, True),
        (Permission.ARTIFACT_REJECT, True),
        (Permission.ARTIFACT_LOCK, False),
        (Permission.ARTIFACT_AMEND, False),
        (Permission.ARTIFACT_DELETE_DRAFT, False),
        (Permission.STUDY_CREATE, False),
        (Permission.STUDY_ARCHIVE, False),
        (Permission.STUDY_MANAGE_MEMBERS, False),
        (Permission.USER_MANAGE, False),
        (Permission.ORG_MANAGE_SETTINGS, False),
        (Permission.AUDIT_READ, True),
        (Permission.VALIDATION_RUN, True),
        (Permission.AI_GENERATION_TRIGGER, False),
    ])
    def test_reviewer_permissions(self, permission: Permission, expected: bool):
        assert has_permission(Role.REVIEWER, permission) is expected


class TestCheckPermission:
    """Verify check_permission raises correctly."""

    def test_raises_403_for_unauthorized_role(self, mocker):
        user = mocker.MagicMock()
        user.effective_role = Role.CONTRIBUTOR

        with pytest.raises(Exception) as exc_info:
            check_permission(user, Permission.ARTIFACT_APPROVE)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "PERMISSION_DENIED"

    def test_passes_for_authorized_role(self, mocker):
        user = mocker.MagicMock()
        user.effective_role = Role.REVIEWER

        check_permission(user, Permission.ARTIFACT_APPROVE)

    def test_uses_study_role_when_provided(self, mocker):
        user = mocker.MagicMock()
        user.effective_role = Role.CONTRIBUTOR

        # User is Contributor org-wide, but Reviewer on this study
        check_permission(user, Permission.ARTIFACT_APPROVE, study_role=Role.REVIEWER)
