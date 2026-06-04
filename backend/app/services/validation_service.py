"""Validation service — trigger and track CDISC validation runs."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, check_permission
from app.models.audit import AuditAction
from app.models.user import User
from app.models.validation import ValidationRun, ValidationStatus
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.validation_repository import ValidationRepository
from app.schemas.validation import ValidationRunCreate
from app.services.audit_service import AuditService


class ValidationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = ValidationRepository(db)
        self._artifact_repo = ArtifactRepository(db)
        self._audit = AuditService(db)

    async def trigger(
        self,
        body: ValidationRunCreate,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ValidationRun:
        check_permission(actor, Permission.VALIDATION_RUN)
        await self._artifact_repo.get_by_id(body.artifact_id, actor.organization_id)

        run = await self._repo.create(
            organization_id=actor.organization_id,
            artifact_id=body.artifact_id,
            artifact_version_id=body.artifact_version_id,
            engine=body.engine,
            rule_set_version=body.rule_set_version,
            status=ValidationStatus.PENDING,
            triggered_by_id=actor.id,
            created_at=datetime.now(UTC),
        )
        await self._audit.log(
            action=AuditAction.VALIDATION_RUN_STARTED,
            resource_type="validation_run",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            resource_id=run.id,
            after_state={"artifact_id": str(body.artifact_id), "engine": body.engine},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return run

    async def get(self, run_id: UUID, organization_id: UUID) -> ValidationRun:
        return await self._repo.get_by_id(run_id, organization_id)

    async def list(
        self,
        organization_id: UUID,
        artifact_id: UUID | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[ValidationRun], int]:
        offset = (page - 1) * page_size
        return await self._repo.list(
            organization_id=organization_id,
            artifact_id=artifact_id,
            limit=page_size,
            offset=offset,
        )
