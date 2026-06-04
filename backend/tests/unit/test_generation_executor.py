"""Unit tests for execute_generation_job.

The executor opens its own DB session via async_session_factory.
All external dependencies (session factory, generator classes) are mocked.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.artifact import ArtifactType
from app.models.generation import GenerationJobStatus
from app.services.generation_executor import execute_generation_job


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job(
    *,
    status=GenerationJobStatus.PENDING,
    artifact_type=ArtifactType.PROTOCOL,
    triggered_by_id=None,
    org_id=None,
):
    job = MagicMock()
    job.id = uuid4()
    job.organization_id = org_id or uuid4()
    job.status = status
    job.artifact_type = artifact_type
    job.triggered_by_id = triggered_by_id or uuid4()
    job.error_message = None
    return job


def _make_actor():
    actor = MagicMock()
    actor.id = uuid4()
    return actor


def _make_db(job=None, actor=None):
    """Return a mock session where scalar_one_or_none() alternates job then actor."""
    db = AsyncMock()
    db.commit = AsyncMock()

    results = []
    if job is not None:
        r1 = MagicMock()
        r1.scalar_one_or_none = MagicMock(return_value=job)
        results.append(r1)
    if actor is not None:
        r2 = MagicMock()
        r2.scalar_one_or_none = MagicMock(return_value=actor)
        results.append(r2)

    db.execute = AsyncMock(side_effect=results if results else [MagicMock()])
    return db


@asynccontextmanager
async def _ctx(db):
    yield db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestExecuteGenerationJob:
    async def test_job_not_found_returns_silently(self):
        """When the job row doesn't exist, executor logs and returns without error."""
        db = _make_db(job=None)
        job_id = uuid4()
        org_id = uuid4()

        r = MagicMock()
        r.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=r)

        with patch(
            "app.services.generation_executor.async_session_factory",
            return_value=_ctx(db),
        ):
            await execute_generation_job(job_id, org_id)

        db.commit.assert_not_called()

    async def test_job_not_pending_returns_silently(self):
        """A job already RUNNING or COMPLETED is skipped without touching the DB."""
        job = _make_job(status=GenerationJobStatus.RUNNING)
        db = _make_db(job=job)

        with patch(
            "app.services.generation_executor.async_session_factory",
            return_value=_ctx(db),
        ):
            await execute_generation_job(job.id, job.organization_id)

        db.commit.assert_not_called()

    async def test_actor_not_found_returns_silently(self):
        """Missing actor (user deleted after job was queued) → silent return, no commit."""
        job = _make_job()
        db = _make_db(job=job, actor=None)

        # First execute → returns job; second execute → returns None for actor
        r_job = MagicMock()
        r_job.scalar_one_or_none = MagicMock(return_value=job)
        r_actor = MagicMock()
        r_actor.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(side_effect=[r_job, r_actor])

        with patch(
            "app.services.generation_executor.async_session_factory",
            return_value=_ctx(db),
        ):
            await execute_generation_job(job.id, job.organization_id)

        db.commit.assert_not_called()

    async def test_unknown_artifact_type_marks_failed(self):
        """Artifact type not in _GENERATOR_MAP → job.status set to FAILED + commit."""
        job = _make_job()
        actor = _make_actor()

        r_job = MagicMock()
        r_job.scalar_one_or_none = MagicMock(return_value=job)
        r_actor = MagicMock()
        r_actor.scalar_one_or_none = MagicMock(return_value=actor)
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[r_job, r_actor])
        db.commit = AsyncMock()

        with patch(
            "app.services.generation_executor.async_session_factory",
            return_value=_ctx(db),
        ):
            with patch(
                "app.services.generation_executor._GENERATOR_MAP",
                {},  # empty map → every type is unknown
            ):
                await execute_generation_job(job.id, job.organization_id)

        assert job.status == GenerationJobStatus.FAILED
        assert job.error_message is not None
        db.commit.assert_called_once()

    async def test_successful_dispatch_calls_generator_run_and_commits(self):
        """Happy path: correct generator is instantiated, run() is called, then commit."""
        job = _make_job(artifact_type=ArtifactType.PROTOCOL)
        actor = _make_actor()

        r_job = MagicMock()
        r_job.scalar_one_or_none = MagicMock(return_value=job)
        r_actor = MagicMock()
        r_actor.scalar_one_or_none = MagicMock(return_value=actor)
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[r_job, r_actor])
        db.commit = AsyncMock()

        mock_generator_instance = AsyncMock()
        mock_generator_cls = MagicMock(return_value=mock_generator_instance)

        with patch(
            "app.services.generation_executor.async_session_factory",
            return_value=_ctx(db),
        ):
            with patch.dict(
                "app.services.generation_executor._GENERATOR_MAP",
                {ArtifactType.PROTOCOL: mock_generator_cls},
            ):
                await execute_generation_job(job.id, job.organization_id)

        mock_generator_cls.assert_called_once_with(db)
        mock_generator_instance.run.assert_called_once_with(job=job, actor=actor)
        db.commit.assert_called_once()

    async def test_unhandled_exception_writes_failed_via_second_session(self):
        """If generator.run() raises, the executor catches it and writes FAILED
        via a new independent session so the original session's error doesn't prevent it."""
        # Job is PENDING when the executor fetches it; generator.run() then raises.
        job = _make_job(
            artifact_type=ArtifactType.PROTOCOL, status=GenerationJobStatus.PENDING
        )
        actor = _make_actor()

        r_job = MagicMock()
        r_job.scalar_one_or_none = MagicMock(return_value=job)
        r_actor = MagicMock()
        r_actor.scalar_one_or_none = MagicMock(return_value=actor)
        primary_db = AsyncMock()
        primary_db.execute = AsyncMock(side_effect=[r_job, r_actor])
        primary_db.commit = AsyncMock()

        mock_generator_instance = AsyncMock()
        mock_generator_instance.run = AsyncMock(
            side_effect=RuntimeError("claude is down")
        )
        mock_generator_cls = MagicMock(return_value=mock_generator_instance)

        # Error session: the executor re-fetches the job (now RUNNING from base_generator)
        # and marks it FAILED.
        failed_job = _make_job(status=GenerationJobStatus.RUNNING)
        r_failed = MagicMock()
        r_failed.scalar_one_or_none = MagicMock(return_value=failed_job)
        error_db = AsyncMock()
        error_db.execute = AsyncMock(return_value=r_failed)
        error_db.commit = AsyncMock()

        sessions = [primary_db, error_db]
        session_idx = 0

        @asynccontextmanager
        async def _factory():
            nonlocal session_idx
            db = sessions[session_idx]
            session_idx += 1
            yield db

        with patch(
            "app.services.generation_executor.async_session_factory",
            new=_factory,
        ):
            with patch.dict(
                "app.services.generation_executor._GENERATOR_MAP",
                {ArtifactType.PROTOCOL: mock_generator_cls},
            ):
                await execute_generation_job(job.id, job.organization_id)

        assert failed_job.status == GenerationJobStatus.FAILED
        error_db.commit.assert_called_once()
