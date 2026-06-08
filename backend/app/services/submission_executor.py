"""Background executor for submission package assembly."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.submission import SubmissionPackage
from app.services.submission_service import SubmissionService

log = logging.getLogger(__name__)


async def execute_submission_assembly(
    package_id: UUID,
    organization_id: UUID,
) -> None:
    """
    Background task entry point.

    Opens a fresh database session and assembles the submission package
    on disk, transitioning status DRAFT -> PACKAGING -> READY.
    """
    async with async_session_factory() as db:
        try:
            svc = SubmissionService(db)
            await svc.assemble_submission_package(
                package_id=package_id,
                organization_id=organization_id,
            )
            await db.commit()
        except Exception:
            log.exception(
                "execute_submission_assembly failed for package %s", package_id
            )
            await db.rollback()
            async with async_session_factory() as error_db:
                result = await error_db.execute(
                    select(SubmissionPackage).where(
                        SubmissionPackage.id == package_id,
                        SubmissionPackage.organization_id == organization_id,
                    )
                )
                package = result.scalar_one_or_none()
                if package is not None:
                    package.error_message = "Background assembly failed"
                    await error_db.commit()
