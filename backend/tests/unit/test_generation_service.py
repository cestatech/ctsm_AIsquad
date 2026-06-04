"""Unit tests for GenerationService.

Key RBAC rule: AI_GENERATION_TRIGGER requires ADMIN or CONTRIBUTOR.
REVIEWER role must receive HTTP 403.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.permissions import Role
from app.models.artifact import ArtifactType
from app.models.generation import GenerationJob, GenerationJobStatus
from app.schemas.generation import GenerationJobCreate
from app.services.generation_service import GenerationService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def svc(mock_db):
    s = GenerationService(mock_db)
    s._repo = AsyncMock()
    s._audit = AsyncMock()
    s._ai_decision = AsyncMock()
    # begin_decision returns a mock decision object
    s._ai_decision.begin_decision = AsyncMock(return_value=MagicMock(id=uuid4()))
    s._ai_decision.complete_decision = AsyncMock()
    return s


def _make_actor(role: Role, org_id=None):
    u = MagicMock()
    u.id = uuid4()
    u.organization_id = org_id or uuid4()
    u.effective_role = role
    return u


def _make_job(**kwargs):
    job = MagicMock(spec=GenerationJob)
    job.id = uuid4()
    job.status = GenerationJobStatus.PENDING
    for k, v in kwargs.items():
        setattr(job, k, v)
    return job


def _create_body(study_id=None):
    return GenerationJobCreate(
        study_id=study_id or uuid4(),
        artifact_type=ArtifactType.PROTOCOL,
        model_id="claude-sonnet-4-6",
    )


# ---------------------------------------------------------------------------
# create_job — RBAC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateJobRBAC:
    async def test_admin_can_create_job(self, svc):
        actor = _make_actor(Role.ADMIN)
        svc._repo.create = AsyncMock(
            return_value=_make_job(organization_id=actor.organization_id)
        )

        result = await svc.create_job(body=_create_body(), actor=actor)

        assert result is not None

    async def test_contributor_can_create_job(self, svc):
        actor = _make_actor(Role.CONTRIBUTOR)
        svc._repo.create = AsyncMock(
            return_value=_make_job(organization_id=actor.organization_id)
        )

        result = await svc.create_job(body=_create_body(), actor=actor)

        assert result is not None

    async def test_reviewer_cannot_create_job(self, svc):
        """REVIEWER does not have AI_GENERATION_TRIGGER permission."""
        actor = _make_actor(Role.REVIEWER)

        with pytest.raises(HTTPException) as exc:
            await svc.create_job(body=_create_body(), actor=actor)

        assert exc.value.status_code == 403
        assert exc.value.detail["code"] == "PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# create_job — CIP compliance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateJobCIP:
    async def test_begin_decision_called_before_repo_create(self, svc):
        """CIP: begin_decision must fire before any DB writes."""
        actor = _make_actor(Role.ADMIN)
        call_order = []

        async def begin(*a, **kw):
            call_order.append("begin")
            return MagicMock(id=uuid4())

        async def create(**kw):
            call_order.append("create")
            return _make_job()

        svc._ai_decision.begin_decision = begin
        svc._repo.create = create

        await svc.create_job(body=_create_body(), actor=actor)

        assert call_order.index("begin") < call_order.index("create")

    async def test_complete_decision_called_after_repo_create(self, svc):
        actor = _make_actor(Role.ADMIN)
        call_order = []

        svc._repo.create = AsyncMock(
            side_effect=lambda **kw: (call_order.append("create"), _make_job())[1]
        )
        svc._ai_decision.complete_decision = AsyncMock(
            side_effect=lambda **kw: call_order.append("complete")
        )

        await svc.create_job(body=_create_body(), actor=actor)

        assert call_order.index("create") < call_order.index("complete")

    async def test_audit_log_recorded(self, svc):
        actor = _make_actor(Role.ADMIN)
        svc._repo.create = AsyncMock(return_value=_make_job())

        await svc.create_job(body=_create_body(), actor=actor)

        svc._audit.log.assert_called_once()

    async def test_job_organization_id_from_actor(self, svc):
        """organization_id must come from the actor JWT, not the request body."""
        actor = _make_actor(Role.ADMIN)
        svc._repo.create = AsyncMock(return_value=_make_job())

        await svc.create_job(body=_create_body(), actor=actor)

        call_kwargs = svc._repo.create.call_args.kwargs
        assert call_kwargs["organization_id"] == actor.organization_id


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGet:
    async def test_delegates_to_repo(self, svc):
        job = _make_job()
        svc._repo.get_by_id = AsyncMock(return_value=job)

        result = await svc.get(job.id, uuid4())

        assert result is job


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestList:
    async def test_list_returns_paginated(self, svc):
        jobs = [_make_job() for _ in range(5)]
        svc._repo.list = AsyncMock(return_value=(jobs, 5))

        items, total = await svc.list(organization_id=uuid4(), page=1, page_size=25)

        assert len(items) == 5
        assert total == 5

    async def test_pagination_offset(self, svc):
        svc._repo.list = AsyncMock(return_value=([], 0))

        await svc.list(organization_id=uuid4(), page=2, page_size=10)

        call_kwargs = svc._repo.list.call_args.kwargs
        assert call_kwargs["offset"] == 10
        assert call_kwargs["limit"] == 10

    async def test_study_id_filter_passed_through(self, svc):
        study_id = uuid4()
        svc._repo.list = AsyncMock(return_value=([], 0))

        await svc.list(organization_id=uuid4(), study_id=study_id)

        call_kwargs = svc._repo.list.call_args.kwargs
        assert call_kwargs["study_id"] == study_id
