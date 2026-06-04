"""Unit tests for execute_validation_run.

Mirrors the generation executor test pattern:
- async_session_factory is mocked to avoid a real DB
- cdisc_validation_engine is mocked so executor logic is tested in isolation
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.validation import ValidationStatus
from app.services.validation_executor import execute_validation_run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(
    *,
    status=ValidationStatus.PENDING,
    engine="internal",
    artifact_type="PROTOCOL",
):
    run = MagicMock()
    run.id = uuid4()
    run.organization_id = uuid4()
    run.artifact_id = uuid4()
    run.artifact_version_id = uuid4()
    run.status = status
    run.engine = engine
    run.rule_set_version = None
    run.started_at = None
    run.completed_at = None
    run.results = None
    run.total_checks = 0
    run.passed_checks = 0
    run.failed_checks = 0
    run.warnings = 0
    return run


def _make_version(content=None):
    v = MagicMock()
    v.content = content or {"document_type": "PROTOCOL", "version": "1.0"}
    return v


def _make_artifact(artifact_type="PROTOCOL"):
    a = MagicMock()
    a.artifact_type = MagicMock()
    a.artifact_type.value = artifact_type
    return a


def _db_returning(*objects):
    """Build a mock db whose execute() returns successive scalar_one_or_none() values."""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    results = []
    for obj in objects:
        r = MagicMock()
        r.scalar_one_or_none = MagicMock(return_value=obj)
        results.append(r)
    db.execute = AsyncMock(side_effect=results)
    return db


@asynccontextmanager
async def _ctx(db):
    yield db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestExecuteValidationRun:
    async def test_run_not_found_returns_silently(self):
        db = _db_returning(None)
        with patch(
            "app.services.validation_executor.async_session_factory",
            new=lambda: _ctx(db),
        ):
            await execute_validation_run(uuid4(), uuid4())

        db.commit.assert_not_called()

    async def test_run_not_pending_returns_silently(self):
        run = _make_run(status=ValidationStatus.RUNNING)
        db = _db_returning(run)
        with patch(
            "app.services.validation_executor.async_session_factory",
            new=lambda: _ctx(db),
        ):
            await execute_validation_run(run.id, run.organization_id)

        db.commit.assert_not_called()

    async def test_artifact_version_not_found_sets_error(self):
        run = _make_run()
        # execute() returns: run, then None for version
        db = _db_returning(run, None)
        with patch(
            "app.services.validation_executor.async_session_factory",
            new=lambda: _ctx(db),
        ):
            await execute_validation_run(run.id, run.organization_id)

        assert run.status == ValidationStatus.ERROR
        db.commit.assert_called_once()

    async def test_internal_engine_calls_cdisc_and_sets_passed(self):
        run = _make_run(engine="internal")
        version = _make_version()
        artifact = _make_artifact("PROTOCOL")
        db = _db_returning(run, version, artifact)

        engine_result = {
            "total_checks": 5,
            "passed_checks": 5,
            "failed_checks": 0,
            "warning_count": 0,
            "error_count": 0,
            "findings": [],
            "rule_set": "CDISC-INTERNAL-1.0",
        }
        with patch(
            "app.services.validation_executor.async_session_factory",
            new=lambda: _ctx(db),
        ):
            with patch(
                "app.services.validation_executor.run_cdisc_validation",
                return_value=engine_result,
            ) as mock_engine:
                await execute_validation_run(run.id, run.organization_id)

        mock_engine.assert_called_once_with(
            content=version.content, artifact_type="PROTOCOL"
        )
        assert run.status == ValidationStatus.PASSED
        assert run.total_checks == 5
        assert run.passed_checks == 5
        assert run.failed_checks == 0
        db.commit.assert_called_once()

    async def test_internal_engine_sets_failed_when_errors(self):
        run = _make_run(engine="internal")
        version = _make_version()
        artifact = _make_artifact("PROTOCOL")
        db = _db_returning(run, version, artifact)

        engine_result = {
            "total_checks": 3,
            "passed_checks": 1,
            "failed_checks": 2,
            "warning_count": 0,
            "error_count": 2,
            "findings": [],
            "rule_set": "CDISC-INTERNAL-1.0",
        }
        with patch(
            "app.services.validation_executor.async_session_factory",
            new=lambda: _ctx(db),
        ):
            with patch(
                "app.services.validation_executor.run_cdisc_validation",
                return_value=engine_result,
            ):
                await execute_validation_run(run.id, run.organization_id)

        assert run.status == ValidationStatus.FAILED

    async def test_pinnacle21_engine_returns_error_stub(self):
        run = _make_run(engine="pinnacle21")
        version = _make_version()
        db = _db_returning(run, version)
        with patch(
            "app.services.validation_executor.async_session_factory",
            new=lambda: _ctx(db),
        ):
            await execute_validation_run(run.id, run.organization_id)

        assert run.status == ValidationStatus.ERROR
        assert "Pinnacle 21" in run.results["message"]

    async def test_unknown_engine_sets_error(self):
        run = _make_run(engine="mystery_engine")
        version = _make_version()
        db = _db_returning(run, version)
        with patch(
            "app.services.validation_executor.async_session_factory",
            new=lambda: _ctx(db),
        ):
            await execute_validation_run(run.id, run.organization_id)

        assert run.status == ValidationStatus.ERROR

    async def test_run_is_marked_running_before_engine_executes(self):
        """status must be RUNNING before the engine fires so the UI can show progress."""
        status_at_engine_call = []
        run = _make_run(engine="internal")
        version = _make_version()
        artifact = _make_artifact("PROTOCOL")
        db = _db_returning(run, version, artifact)

        def _capture_status(**kwargs):
            status_at_engine_call.append(run.status)
            return {
                "total_checks": 1,
                "passed_checks": 1,
                "failed_checks": 0,
                "warning_count": 0,
                "error_count": 0,
                "findings": [],
                "rule_set": "CDISC-INTERNAL-1.0",
            }

        with patch(
            "app.services.validation_executor.async_session_factory",
            new=lambda: _ctx(db),
        ):
            with patch(
                "app.services.validation_executor.run_cdisc_validation",
                side_effect=_capture_status,
            ):
                await execute_validation_run(run.id, run.organization_id)

        assert status_at_engine_call[0] == ValidationStatus.RUNNING

    async def test_unhandled_exception_writes_error_via_second_session(self):
        """If the engine raises, ERROR status is written via a fresh session."""
        run = _make_run(engine="internal")
        version = _make_version()
        artifact = _make_artifact("PROTOCOL")
        primary_db = _db_returning(run, version, artifact)

        # Error session: finds the run (now RUNNING after executor marks it) and sets ERROR
        error_run = _make_run(status=ValidationStatus.RUNNING)
        error_db = _db_returning(error_run)

        sessions = [primary_db, error_db]
        idx = 0

        @asynccontextmanager
        async def _factory():
            nonlocal idx
            db = sessions[idx]
            idx += 1
            yield db

        with patch(
            "app.services.validation_executor.async_session_factory",
            new=_factory,
        ):
            with patch(
                "app.services.validation_executor.run_cdisc_validation",
                side_effect=RuntimeError("engine crash"),
            ):
                await execute_validation_run(run.id, run.organization_id)

        assert error_run.status == ValidationStatus.ERROR
        error_db.commit.assert_called_once()
