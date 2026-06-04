"""
Validation executor — picks up a PENDING ValidationRun and runs the internal
CDISC rules engine against the artifact's current content.

Called as a FastAPI BackgroundTask immediately after a ValidationRun is created.
Opens its own database session so it outlives the HTTP request transaction.

When engine == "internal": the built-in CDISC rules engine is used.
When engine == "pinnacle21": a stub is written to the run record (external integration TBD).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.artifact import ArtifactVersion
from app.models.validation import ValidationRun, ValidationStatus
from app.services.cdisc_validation_engine import run_cdisc_validation

log = logging.getLogger(__name__)


async def execute_validation_run(run_id: UUID, organization_id: UUID) -> None:
    """
    Background task entry point.

    Opens a fresh database session, loads the ValidationRun and the artifact
    version content, runs the appropriate engine, and persists results.

    Failures are written to the run record — they do not crash the worker.
    """
    async with async_session_factory() as db:
        try:
            # Load the validation run
            result = await db.execute(
                select(ValidationRun).where(
                    ValidationRun.id == run_id,
                    ValidationRun.organization_id == organization_id,
                )
            )
            run = result.scalar_one_or_none()
            if run is None:
                log.error("execute_validation_run: run %s not found", run_id)
                return

            if run.status != ValidationStatus.PENDING:
                log.warning(
                    "execute_validation_run: run %s already in status %s",
                    run_id, run.status,
                )
                return

            # Mark running
            run.status = ValidationStatus.RUNNING
            run.started_at = datetime.now(UTC)
            await db.flush()

            # Load artifact version content
            version_result = await db.execute(
                select(ArtifactVersion).where(
                    ArtifactVersion.id == run.artifact_version_id
                )
            )
            version = version_result.scalar_one_or_none()
            if version is None:
                run.status = ValidationStatus.ERROR
                run.completed_at = datetime.now(UTC)
                run.results = {"error": f"Artifact version {run.artifact_version_id} not found"}
                await db.commit()
                return

            # Dispatch by engine
            if run.engine == "internal":
                # Determine artifact type from the artifact relationship
                from app.models.artifact import Artifact
                artifact_result = await db.execute(
                    select(Artifact).where(Artifact.id == run.artifact_id)
                )
                artifact = artifact_result.scalar_one_or_none()
                artifact_type = artifact.artifact_type.value if artifact else "OTHER"

                engine_results = run_cdisc_validation(
                    content=version.content or {},
                    artifact_type=artifact_type,
                )
                has_errors = engine_results.get("error_count", 0) > 0

                run.total_checks = engine_results.get("total_checks", 0)
                run.passed_checks = engine_results.get("passed_checks", 0)
                run.failed_checks = engine_results.get("failed_checks", 0)
                run.warnings = engine_results.get("warning_count", 0)
                run.results = engine_results
                run.status = ValidationStatus.FAILED if has_errors else ValidationStatus.PASSED

            elif run.engine == "pinnacle21":
                # External integration — stub result
                run.results = {
                    "message": "Pinnacle 21 integration is not yet configured.",
                    "engine": "pinnacle21",
                    "rule_set": run.rule_set_version or "CE 3.1",
                }
                run.total_checks = 0
                run.passed_checks = 0
                run.failed_checks = 0
                run.warnings = 0
                run.status = ValidationStatus.ERROR

            else:
                run.results = {"error": f"Unknown engine: {run.engine}"}
                run.status = ValidationStatus.ERROR

            run.completed_at = datetime.now(UTC)
            await db.commit()
            log.info(
                "execute_validation_run: run %s completed with status %s (%s/%s checks passed)",
                run_id, run.status, run.passed_checks, run.total_checks,
            )

        except Exception:
            log.exception("execute_validation_run: unhandled error for run %s", run_id)
            try:
                async with async_session_factory() as error_db:
                    err_result = await error_db.execute(
                        select(ValidationRun).where(ValidationRun.id == run_id)
                    )
                    failed_run = err_result.scalar_one_or_none()
                    if failed_run and failed_run.status == ValidationStatus.RUNNING:
                        failed_run.status = ValidationStatus.ERROR
                        failed_run.completed_at = datetime.now(UTC)
                        failed_run.results = {
                            "error": "Internal executor error — check server logs"
                        }
                        await error_db.commit()
            except Exception:
                log.exception(
                    "execute_validation_run: could not write ERROR status for run %s", run_id
                )
