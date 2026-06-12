"""Unit tests for artifact service delete and export."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.exceptions import WorkflowError
from app.models.artifact import ArtifactStatus
from app.models.audit import AuditAction
from app.models.user import Role
from app.services.artifact_service import ArtifactService


def _make_user(role: Role, user_id=None, org_id=None):
    user = MagicMock()
    user.id = user_id or uuid4()
    user.organization_id = org_id or uuid4()
    user.effective_role = role
    return user


def _make_artifact(status=ArtifactStatus.DRAFT, created_by_id=None, org_id=None):
    artifact = MagicMock()
    artifact.id = uuid4()
    artifact.organization_id = org_id or uuid4()
    artifact.status = status
    artifact.created_by_id = created_by_id or uuid4()
    artifact.current_version_id = uuid4()
    artifact.current_version_number = 1
    artifact.to_audit_dict.return_value = {"id": str(artifact.id), "status": status.value}
    return artifact


@pytest.mark.asyncio
class TestArtifactServiceDelete:
    async def test_admin_can_delete_draft(self):
        db = MagicMock()
        svc = ArtifactService(db)
        org_id = uuid4()
        admin = _make_user(Role.ADMIN, org_id=org_id)
        artifact = _make_artifact(created_by_id=uuid4(), org_id=org_id)

        svc._repo.get_by_id = AsyncMock(return_value=artifact)
        svc._audit.log = AsyncMock()

        await svc.delete_artifact(artifact.id, org_id, admin)

        assert artifact.deleted_at is not None
        svc._audit.log.assert_called_once()
        assert svc._audit.log.call_args.kwargs["action"] == AuditAction.ARTIFACT_DELETED

    async def test_contributor_can_delete_own_draft(self):
        db = MagicMock()
        svc = ArtifactService(db)
        org_id = uuid4()
        contributor = _make_user(Role.CONTRIBUTOR, org_id=org_id)
        artifact = _make_artifact(created_by_id=contributor.id, org_id=org_id)

        svc._repo.get_by_id = AsyncMock(return_value=artifact)
        svc._audit.log = AsyncMock()

        await svc.delete_artifact(artifact.id, org_id, contributor)

        assert artifact.deleted_at is not None

    async def test_contributor_cannot_delete_others_draft(self):
        db = MagicMock()
        svc = ArtifactService(db)
        org_id = uuid4()
        contributor = _make_user(Role.CONTRIBUTOR, org_id=org_id)
        artifact = _make_artifact(created_by_id=uuid4(), org_id=org_id)

        svc._repo.get_by_id = AsyncMock(return_value=artifact)

        with pytest.raises(HTTPException) as exc:
            await svc.delete_artifact(artifact.id, org_id, contributor)

        assert exc.value.status_code == 403

    async def test_cannot_delete_non_draft(self):
        db = MagicMock()
        svc = ArtifactService(db)
        org_id = uuid4()
        admin = _make_user(Role.ADMIN, org_id=org_id)
        artifact = _make_artifact(
            status=ArtifactStatus.APPROVED, created_by_id=admin.id, org_id=org_id
        )

        svc._repo.get_by_id = AsyncMock(return_value=artifact)

        with pytest.raises(WorkflowError):
            await svc.delete_artifact(artifact.id, org_id, admin)


@pytest.mark.asyncio
class TestArtifactServiceSubmit:
    async def test_transition_sets_updated_at_for_response_serialization(self):
        db = MagicMock()
        svc = ArtifactService(db)
        org_id = uuid4()
        contributor = _make_user(Role.CONTRIBUTOR, org_id=org_id)
        artifact = _make_artifact(org_id=org_id)
        artifact.can_transition_to = MagicMock(return_value=True)

        svc._repo.get_by_id = AsyncMock(return_value=artifact)
        svc._audit.log = AsyncMock()
        svc._notify.create = AsyncMock()

        before = datetime.now(UTC)
        result = await svc.submit_for_review(artifact.id, org_id, contributor)

        assert result.status == ArtifactStatus.IN_REVIEW
        assert artifact.updated_at >= before
        svc._notify.create.assert_called_once()


@pytest.mark.asyncio
class TestArtifactServiceExport:
    async def test_get_artifact_export_returns_content(self):
        db = MagicMock()
        svc = ArtifactService(db)
        org_id = uuid4()
        artifact = _make_artifact(org_id=org_id)
        version = MagicMock()
        version.content = {"title": "Exported"}

        svc._repo.get_by_id = AsyncMock(return_value=artifact)
        svc._repo.get_version = AsyncMock(return_value=version)

        result_artifact, content = await svc.get_artifact_export(artifact.id, org_id)

        assert result_artifact is artifact
        assert content == {"title": "Exported"}
