"""Unit tests for study termination."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.permissions import Role
from app.models.study import StudyStatus
from app.services.study_service import StudyService


@pytest.mark.asyncio
async def test_terminate_sets_status_and_end_date():
    svc = StudyService(AsyncMock())
    study = MagicMock()
    study.id = uuid4()
    study.status = StudyStatus.ACTIVE
    study.end_date = None
    study.to_audit_dict.return_value = {"status": "ACTIVE"}

    svc._repo = AsyncMock()
    svc._repo.get.return_value = study
    svc._repo.update = AsyncMock(side_effect=lambda s: s)
    svc._audit = AsyncMock()
    svc._graph = AsyncMock()

    actor = MagicMock()
    actor.id = uuid4()
    actor.organization_id = uuid4()
    actor.effective_role = Role.ADMIN

    result = await svc.terminate(study.id, actor)

    assert result.status == StudyStatus.TERMINATED
    assert result.end_date == date.today()
    svc._audit.log.assert_awaited_once()


@pytest.mark.asyncio
async def test_terminate_rejects_already_terminated():
    svc = StudyService(AsyncMock())
    study = MagicMock()
    study.status = StudyStatus.TERMINATED
    svc._repo = AsyncMock()
    svc._repo.get.return_value = study

    actor = MagicMock()
    actor.id = uuid4()
    actor.organization_id = uuid4()
    actor.effective_role = Role.ADMIN

    with pytest.raises(HTTPException) as exc:
        await svc.terminate(study.id, actor)
    assert exc.value.status_code == 422
