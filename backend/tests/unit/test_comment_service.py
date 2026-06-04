"""Unit tests for CommentService.

Tests service-layer logic only — DB and audit service are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.permissions import Role
from app.models.comment import Comment
from app.schemas.comment import CommentCreate, CommentUpdate
from app.services.comment_service import CommentService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def svc(mock_db):
    s = CommentService(mock_db)
    s._repo = AsyncMock()
    s._audit = AsyncMock()
    return s


@pytest.fixture
def contributor():
    u = MagicMock()
    u.id = uuid4()
    u.organization_id = uuid4()
    u.effective_role = Role.CONTRIBUTOR
    return u


@pytest.fixture
def admin():
    u = MagicMock()
    u.id = uuid4()
    u.organization_id = uuid4()
    u.effective_role = Role.ADMIN
    return u


def _make_comment(author_id, artifact_id, is_resolved=False):
    c = MagicMock(spec=Comment)
    c.id = uuid4()
    c.artifact_id = artifact_id
    c.author_id = author_id
    c.body = "Original body"
    c.is_resolved = is_resolved
    c.is_deleted = False
    return c


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreate:
    async def test_creates_without_parent(self, svc, contributor):
        artifact_id = uuid4()
        svc._repo.create = AsyncMock(
            return_value=MagicMock(id=uuid4(), artifact_id=artifact_id)
        )

        body = CommentCreate(artifact_id=artifact_id, body="Hello")
        result = await svc.create(body=body, actor=contributor)

        svc._repo.create.assert_called_once()
        svc._audit.log.assert_called_once()
        assert result is not None

    async def test_creates_with_matching_parent(self, svc, contributor):
        artifact_id = uuid4()
        parent = MagicMock()
        parent.artifact_id = artifact_id
        svc._repo.get_by_id = AsyncMock(return_value=parent)
        svc._repo.create = AsyncMock(
            return_value=MagicMock(id=uuid4(), artifact_id=artifact_id)
        )

        body = CommentCreate(artifact_id=artifact_id, body="Reply", parent_id=uuid4())
        await svc.create(body=body, actor=contributor)
        svc._repo.create.assert_called_once()

    async def test_raises_422_on_parent_artifact_mismatch(self, svc, contributor):
        parent = MagicMock()
        parent.artifact_id = uuid4()  # different artifact
        svc._repo.get_by_id = AsyncMock(return_value=parent)

        body = CommentCreate(artifact_id=uuid4(), body="Reply", parent_id=uuid4())
        with pytest.raises(HTTPException) as exc:
            await svc.create(body=body, actor=contributor)

        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "PARENT_ARTIFACT_MISMATCH"

    async def test_audit_log_recorded(self, svc, contributor):
        artifact_id = uuid4()
        svc._repo.create = AsyncMock(
            return_value=MagicMock(id=uuid4(), artifact_id=artifact_id)
        )

        body = CommentCreate(artifact_id=artifact_id, body="Audit test")
        await svc.create(body=body, actor=contributor)

        svc._audit.log.assert_called_once()


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestUpdate:
    async def test_author_can_update(self, svc, contributor):
        comment = _make_comment(contributor.id, uuid4())
        svc._repo.get_by_id = AsyncMock(return_value=comment)

        body = CommentUpdate(body="Edited body")
        result = await svc.update(comment.id, body, contributor)

        assert result.body == "Edited body"
        svc._audit.log.assert_called_once()

    async def test_non_author_raises_403(self, svc, contributor):
        comment = _make_comment(uuid4(), uuid4())  # different author
        svc._repo.get_by_id = AsyncMock(return_value=comment)

        with pytest.raises(HTTPException) as exc:
            await svc.update(comment.id, CommentUpdate(body="hack"), contributor)

        assert exc.value.status_code == 403
        assert exc.value.detail["code"] == "PERMISSION_DENIED"

    async def test_resolved_comment_raises_422(self, svc, contributor):
        comment = _make_comment(contributor.id, uuid4(), is_resolved=True)
        svc._repo.get_by_id = AsyncMock(return_value=comment)

        with pytest.raises(HTTPException) as exc:
            await svc.update(
                comment.id, CommentUpdate(body="edit resolved"), contributor
            )

        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "COMMENT_RESOLVED"


# ---------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestResolve:
    async def test_resolve_sets_flag(self, svc, contributor):
        comment = _make_comment(contributor.id, uuid4())
        svc._repo.get_by_id = AsyncMock(return_value=comment)

        result = await svc.resolve(comment.id, contributor)

        assert result.is_resolved is True
        assert result.resolved_by_id == contributor.id
        svc._audit.log.assert_called_once()

    async def test_already_resolved_raises_422(self, svc, contributor):
        comment = _make_comment(contributor.id, uuid4(), is_resolved=True)
        svc._repo.get_by_id = AsyncMock(return_value=comment)

        with pytest.raises(HTTPException) as exc:
            await svc.resolve(comment.id, contributor)

        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "ALREADY_RESOLVED"


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDelete:
    async def test_author_can_delete(self, svc, contributor):
        comment = _make_comment(contributor.id, uuid4())
        svc._repo.get_by_id = AsyncMock(return_value=comment)

        await svc.delete(comment.id, contributor)

        assert comment.is_deleted is True
        svc._audit.log.assert_called_once()

    async def test_admin_can_delete_any_comment(self, svc, admin):
        comment = _make_comment(uuid4(), uuid4())  # different author
        svc._repo.get_by_id = AsyncMock(return_value=comment)

        await svc.delete(comment.id, admin)

        assert comment.is_deleted is True

    async def test_non_author_non_admin_raises_403(self, svc, contributor):
        comment = _make_comment(uuid4(), uuid4())  # different author, CONTRIBUTOR role
        svc._repo.get_by_id = AsyncMock(return_value=comment)

        with pytest.raises(HTTPException) as exc:
            await svc.delete(comment.id, contributor)

        assert exc.value.status_code == 403
        assert exc.value.detail["code"] == "PERMISSION_DENIED"
