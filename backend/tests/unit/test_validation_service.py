"""Unit tests for ValidationService.

All three roles can trigger validation (VALIDATION_RUN permission).
Tests verify: run creation, audit logging, artifact ownership check.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.permissions import Role
from app.models.validation import ValidationRun, ValidationStatus
from app.schemas.validation import ValidationRunCreate
from app.services.validation_service import ValidationService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def svc(mock_db):
    s = ValidationService(mock_db)
    s._repo = AsyncMock()
    s._artifact_repo = AsyncMock()
    s._audit = AsyncMock()
    return s


def _make_actor(role: Role):
    u = MagicMock()
    u.id = uuid4()
    u.organization_id = uuid4()
    u.effective_role = role
    return u


def _make_run(**kwargs):
    run = MagicMock(spec=ValidationRun)
    run.id = uuid4()
    run.status = ValidationStatus.PENDING
    for k, v in kwargs.items():
        setattr(run, k, v)
    return run


# ---------------------------------------------------------------------------
# trigger
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestTrigger:
    async def test_admin_can_trigger(self, svc):
        actor = _make_actor(Role.ADMIN)
        artifact_id, version_id = uuid4(), uuid4()
        svc._artifact_repo.get_by_id = AsyncMock(return_value=MagicMock())
        svc._repo.create = AsyncMock(return_value=_make_run(artifact_id=artifact_id))

        body = ValidationRunCreate(artifact_id=artifact_id, artifact_version_id=version_id)
        result = await svc.trigger(body=body, actor=actor)

        svc._repo.create.assert_called_once()
        svc._audit.log.assert_called_once()
        assert result is not None

    async def test_contributor_can_trigger(self, svc):
        actor = _make_actor(Role.CONTRIBUTOR)
        artifact_id, version_id = uuid4(), uuid4()
        svc._artifact_repo.get_by_id = AsyncMock(return_value=MagicMock())
        svc._repo.create = AsyncMock(return_value=_make_run(artifact_id=artifact_id))

        body = ValidationRunCreate(artifact_id=artifact_id, artifact_version_id=version_id)
        result = await svc.trigger(body=body, actor=actor)

        assert result is not None
        svc._audit.log.assert_called_once()

    async def test_reviewer_can_trigger(self, svc):
        """REVIEWER also has VALIDATION_RUN permission."""
        actor = _make_actor(Role.REVIEWER)
        artifact_id, version_id = uuid4(), uuid4()
        svc._artifact_repo.get_by_id = AsyncMock(return_value=MagicMock())
        svc._repo.create = AsyncMock(return_value=_make_run(artifact_id=artifact_id))

        body = ValidationRunCreate(artifact_id=artifact_id, artifact_version_id=version_id)
        result = await svc.trigger(body=body, actor=actor)

        assert result is not None

    async def test_artifact_ownership_checked(self, svc):
        """get_by_id is called to verify artifact exists in org."""
        actor = _make_actor(Role.ADMIN)
        artifact_id, version_id = uuid4(), uuid4()
        svc._artifact_repo.get_by_id = AsyncMock(return_value=MagicMock())
        svc._repo.create = AsyncMock(return_value=_make_run(artifact_id=artifact_id))

        body = ValidationRunCreate(artifact_id=artifact_id, artifact_version_id=version_id)
        await svc.trigger(body=body, actor=actor)

        svc._artifact_repo.get_by_id.assert_called_once_with(artifact_id, actor.organization_id)

    async def test_run_created_with_pending_status(self, svc):
        actor = _make_actor(Role.ADMIN)
        artifact_id, version_id = uuid4(), uuid4()
        svc._artifact_repo.get_by_id = AsyncMock(return_value=MagicMock())
        svc._repo.create = AsyncMock(return_value=_make_run(status=ValidationStatus.PENDING))

        body = ValidationRunCreate(artifact_id=artifact_id, artifact_version_id=version_id)
        await svc.trigger(body=body, actor=actor)

        call_kwargs = svc._repo.create.call_args.kwargs
        assert call_kwargs["status"] == ValidationStatus.PENDING


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGet:
    async def test_returns_run_by_id(self, svc):
        run_id, org_id = uuid4(), uuid4()
        expected = _make_run()
        svc._repo.get_by_id = AsyncMock(return_value=expected)

        result = await svc.get(run_id, org_id)

        svc._repo.get_by_id.assert_called_once_with(run_id, org_id)
        assert result is expected


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestList:
    async def test_list_returns_paginated(self, svc):
        runs = [_make_run() for _ in range(3)]
        svc._repo.list = AsyncMock(return_value=(runs, 3))

        items, total = await svc.list(organization_id=uuid4(), page=1, page_size=25)

        assert len(items) == 3
        assert total == 3

    async def test_list_passes_artifact_filter(self, svc):
        artifact_id = uuid4()
        svc._repo.list = AsyncMock(return_value=([], 0))

        await svc.list(organization_id=uuid4(), artifact_id=artifact_id)

        call_kwargs = svc._repo.list.call_args.kwargs
        assert call_kwargs["artifact_id"] == artifact_id

    async def test_pagination_offset_computed(self, svc):
        svc._repo.list = AsyncMock(return_value=([], 0))

        await svc.list(organization_id=uuid4(), page=3, page_size=10)

        call_kwargs = svc._repo.list.call_args.kwargs
        assert call_kwargs["offset"] == 20  # (3-1)*10
        assert call_kwargs["limit"] == 10
