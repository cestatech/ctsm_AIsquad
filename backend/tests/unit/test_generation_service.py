"""Unit tests for generation service cancel behaviour."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.generation import GenerationJobStatus
from app.models.user import Role
from app.services.generation_service import GenerationService


def _make_actor(role: Role = Role.CONTRIBUTOR):
    actor = MagicMock()
    actor.id = uuid4()
    actor.organization_id = uuid4()
    actor.effective_role = role
    return actor


def _make_job(status: GenerationJobStatus):
    job = MagicMock()
    job.id = uuid4()
    job.organization_id = uuid4()
    job.status = status
    job.artifact_type = MagicMock(value="PROTOCOL")
    job.error_message = None
    job.completed_at = None
    return job


@pytest.mark.asyncio
class TestGenerationServiceCancel:
    async def test_cancel_pending_job(self):
        svc = GenerationService(MagicMock())
        actor = _make_actor()
        job = _make_job(GenerationJobStatus.PENDING)

        svc._repo.get_by_id = AsyncMock(return_value=job)
        svc._audit.log = AsyncMock()

        result = await svc.cancel_job(job.id, actor)

        assert result.status == GenerationJobStatus.CANCELLED
        assert result.error_message == "Cancelled by user"
        assert result.completed_at is not None
        svc._audit.log.assert_called_once()

    async def test_cancel_running_job(self):
        svc = GenerationService(MagicMock())
        actor = _make_actor()
        job = _make_job(GenerationJobStatus.RUNNING)

        svc._repo.get_by_id = AsyncMock(return_value=job)
        svc._audit.log = AsyncMock()

        result = await svc.cancel_job(job.id, actor)

        assert result.status == GenerationJobStatus.CANCELLED

    async def test_cannot_cancel_completed_job(self):
        svc = GenerationService(MagicMock())
        actor = _make_actor()
        job = _make_job(GenerationJobStatus.COMPLETED)

        svc._repo.get_by_id = AsyncMock(return_value=job)

        with pytest.raises(HTTPException) as exc:
            await svc.cancel_job(job.id, actor)

        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "JOB_NOT_CANCELLABLE"
