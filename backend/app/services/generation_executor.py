"""
Generation executor — picks up a queued job and runs the right generator.

Called as a FastAPI BackgroundTask immediately after a GenerationJob is created.
Opens its own database session so it outlives the HTTP request transaction.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.artifact import ArtifactType
from app.models.generation import GenerationJob, GenerationJobStatus
from app.models.user import User
from app.services.generators.adam_deriver import ADaMDerivationGenerator
from app.services.generators.base_generator import BaseGenerator
from app.services.generators.csr_generator import CSRGenerator
from app.services.generators.icf_generator import ICFGenerator
from app.services.generators.protocol_generator import ProtocolGenerator
from app.services.generators.sap_generator import SAPGenerator
from app.services.generators.sdtm_mapper import SDTMMappingGenerator
from app.services.generators.tlf_assembler import TLFAssembler

log = logging.getLogger(__name__)

_GENERATOR_MAP: dict[ArtifactType, type[BaseGenerator]] = {
    ArtifactType.PROTOCOL: ProtocolGenerator,
    ArtifactType.ICF: ICFGenerator,
    ArtifactType.SAP: SAPGenerator,
    ArtifactType.SDTM_DATASET: SDTMMappingGenerator,
    ArtifactType.ADAM_DATASET: ADaMDerivationGenerator,
    ArtifactType.TLF: TLFAssembler,
    ArtifactType.CSR: CSRGenerator,
}


async def execute_generation_job(job_id: UUID, organization_id: UUID) -> None:
    """
    Background task entry point.

    Opens a fresh database session, loads the job and the triggering user,
    dispatches to the appropriate generator, and commits on success.

    Failures are caught, logged, and written to the job record so the UI
    can surface them — they do not crash the worker.
    """
    async with async_session_factory() as db:
        try:
            # Load job
            result = await db.execute(
                select(GenerationJob).where(
                    GenerationJob.id == job_id,
                    GenerationJob.organization_id == organization_id,
                )
            )
            job = result.scalar_one_or_none()
            if job is None:
                log.error("execute_generation_job: job %s not found", job_id)
                return

            if job.status != GenerationJobStatus.PENDING:
                log.warning(
                    "execute_generation_job: job %s already in status %s",
                    job_id,
                    job.status,
                )
                return

            # Load the actor (user who triggered the job)
            user_result = await db.execute(
                select(User).where(User.id == job.triggered_by_id)
            )
            actor = user_result.scalar_one_or_none()
            if actor is None:
                log.error(
                    "execute_generation_job: actor user %s not found",
                    job.triggered_by_id,
                )
                return

            # Dispatch to the correct generator
            generator_cls = _GENERATOR_MAP.get(job.artifact_type)
            if generator_cls is None:
                job.status = GenerationJobStatus.FAILED
                job.error_message = (
                    f"No generator available for artifact type: {job.artifact_type}"
                )
                await db.commit()
                return

            generator = generator_cls(db)
            await generator.run(job=job, actor=actor)
            await db.commit()

        except Exception:
            log.exception("execute_generation_job: unhandled error for job %s", job_id)
            # attempt to persist FAILED status
            try:
                async with async_session_factory() as error_db:
                    err_result = await error_db.execute(
                        select(GenerationJob).where(GenerationJob.id == job_id)
                    )
                    failed_job = err_result.scalar_one_or_none()
                    if failed_job and failed_job.status == GenerationJobStatus.RUNNING:
                        failed_job.status = GenerationJobStatus.FAILED
                        failed_job.error_message = (
                            "Internal executor error — check server logs"
                        )
                        await error_db.commit()
            except Exception:
                log.exception(
                    "execute_generation_job: could not write FAILED status for job %s",
                    job_id,
                )
