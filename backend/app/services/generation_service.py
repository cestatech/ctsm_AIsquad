"""AI Generation service — create and track AI artifact generation jobs.

Every job creation logs an AIDecision record per CIP mandatory rules.
Actual generation execution runs as an async background task (not yet wired).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, check_permission
from app.models.artifact import ArtifactType
from app.models.audit import AuditAction
from app.models.generation import GenerationJob, GenerationJobStatus
from app.models.intake import StudyBrief
from app.models.user import User
from app.repositories.generation_repository import GenerationRepository
from app.schemas.generation import GenerationJobCreate
from app.services.audit_service import AuditService
from app.services.intelligence_service import AIDecisionService


class GenerationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = GenerationRepository(db)
        self._audit = AuditService(db)
        self._ai_decision = AIDecisionService(db)

    async def create_job(
        self,
        body: GenerationJobCreate,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> GenerationJob:
        check_permission(actor, Permission.AI_GENERATION_TRIGGER)

        # CIP requirement: log AI decision before executing
        decision = await self._ai_decision.begin_decision(
            organization_id=actor.organization_id,
            agent_name="generation-service",
            decision_type="ARTIFACT_GENERATION",
            input_context={
                "study_id": str(body.study_id),
                "artifact_type": body.artifact_type,
                "model_id": body.model_id,
                "prompt_template_id": body.prompt_template_id,
            },
        )

        job = await self._repo.create(
            organization_id=actor.organization_id,
            study_id=body.study_id,
            artifact_type=body.artifact_type,
            status=GenerationJobStatus.PENDING,
            model_id=body.model_id,
            prompt_template_id=body.prompt_template_id,
            input_context=body.input_context,
            triggered_by_id=actor.id,
        )

        await self._ai_decision.complete_decision(
            decision=decision,
            output={"generation_job_id": str(job.id)},
        )
        await self._audit.log(
            action=AuditAction.AI_GENERATION_STARTED,
            resource_type="generation_job",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=job.id,
            after_state={
                "study_id": str(body.study_id),
                "artifact_type": body.artifact_type,
                "model_id": body.model_id,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return job

    async def create_job_from_brief(
        self,
        brief_id: UUID,
        artifact_type: ArtifactType,
        model_id: str,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> GenerationJob:
        """Trigger artifact generation pre-populated with a compiled Study Brief."""
        result = await self._db.execute(
            select(StudyBrief).where(
                StudyBrief.id == brief_id,
                StudyBrief.organization_id == actor.organization_id,
            )
        )
        brief = result.scalar_one_or_none()
        if brief is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Study brief not found."},
            )

        body = GenerationJobCreate(
            study_id=brief.study_id,
            artifact_type=artifact_type,
            model_id=model_id,
            input_context={"brief_id": str(brief_id), "brief_content": brief.content},
        )
        return await self.create_job(body, actor, ip_address, user_agent)

    async def get(self, job_id: UUID, organization_id: UUID) -> GenerationJob:
        return await self._repo.get_by_id(job_id, organization_id)

    async def list(
        self,
        organization_id: UUID,
        study_id: UUID | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[GenerationJob], int]:
        offset = (page - 1) * page_size
        return await self._repo.list(
            organization_id=organization_id,
            study_id=study_id,
            limit=page_size,
            offset=offset,
        )

    async def retry_job(
        self,
        job_id: UUID,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> GenerationJob:
        """Reset a PENDING or FAILED job so the executor can run again."""
        check_permission(actor, Permission.AI_GENERATION_TRIGGER)
        job = await self._repo.get_by_id(job_id, actor.organization_id)
        if job.status not in (
            GenerationJobStatus.PENDING,
            GenerationJobStatus.FAILED,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "JOB_NOT_RETRYABLE",
                    "message": f"Job status {job.status.value} cannot be retried.",
                },
            )
        job.status = GenerationJobStatus.PENDING
        job.error_message = None
        job.started_at = None
        job.completed_at = None
        await self._audit.log(
            action=AuditAction.AI_GENERATION_STARTED,
            resource_type="generation_job",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=job.id,
            after_state={"action": "retry", "artifact_type": job.artifact_type.value},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return job

    async def list_stale_pending(
        self, organization_id: UUID, *, limit: int = 20
    ) -> list[GenerationJob]:
        """Return PENDING jobs for background recovery."""
        return await self._repo.list_pending(organization_id, limit=limit)
