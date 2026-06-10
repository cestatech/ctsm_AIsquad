"""
Artifact lifecycle service. Enforces workflow transitions and versioning.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ArtifactLockedError, WorkflowError
from app.core.permissions import Permission, check_permission
from app.models.artifact import Artifact, ArtifactStatus, ArtifactType, ArtifactVersion
from app.models.audit import AuditAction
from app.models.user import Role, User
from app.models.notification import NotificationType
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.study_repository import StudyRepository
from app.services.audit_service import AuditService
from app.services.context_graph_service import ContextGraphService
from app.services.export.artifact_export_service import (
    ArtifactExportService,
    ExportResult,
)
from app.services.notification_service import NotificationService


class ArtifactService:
    """Business logic for artifact lifecycle management."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = ArtifactRepository(db)
        self._study_repo = StudyRepository(db)
        self._audit = AuditService(db)
        self._graph = ContextGraphService(db)
        self._notify = NotificationService(db)

    async def create_artifact(
        self,
        organization_id: UUID,
        study_id: UUID,
        user: User,
        artifact_type: ArtifactType,
        name: str,
        description: str | None = None,
        content: dict | None = None,
        change_summary: str | None = None,
        metadata: dict | None = None,
    ) -> Artifact:
        """Create a new artifact at version 1 in DRAFT status."""
        check_permission(user, Permission.ARTIFACT_CREATE)

        content = content or {}
        content_hash = self._hash_content(content)

        artifact = Artifact(
            organization_id=organization_id,
            study_id=study_id,
            artifact_type=artifact_type,
            name=name,
            description=description,
            status=ArtifactStatus.DRAFT,
            created_by_id=user.id,
            extra_data=metadata or {},
        )
        self._db.add(artifact)
        await self._db.flush()  # get artifact.id

        version = ArtifactVersion(
            artifact_id=artifact.id,
            organization_id=organization_id,
            version_number=1,
            is_current=True,
            content=content,
            content_hash=content_hash,
            content_diff=None,
            status_at_creation=ArtifactStatus.DRAFT,
            change_summary=change_summary or "Initial version",
            created_by_id=user.id,
            created_at=datetime.now(UTC),
        )
        self._db.add(version)
        await self._db.flush()

        artifact.current_version_id = version.id
        artifact.current_version_number = 1

        await self._audit.log(
            action=AuditAction.ARTIFACT_CREATED,
            resource_type="artifact",
            organization_id=organization_id,
            actor_user_id=user.id,
            resource_id=artifact.id,
            after_state=artifact.to_audit_dict(),
        )

        return artifact

    async def update_artifact_content(
        self,
        artifact_id: UUID,
        organization_id: UUID,
        user: User,
        content: dict,
        change_summary: str | None = None,
    ) -> Artifact:
        """Update artifact content, creating a new version snapshot."""
        check_permission(user, Permission.ARTIFACT_EDIT)

        artifact = await self._repo.get_by_id(artifact_id, organization_id)
        if artifact.is_locked():
            raise ArtifactLockedError()

        if artifact.status not in (ArtifactStatus.DRAFT, ArtifactStatus.REJECTED):
            raise WorkflowError(
                f"Cannot edit artifact in status {artifact.status}. "
                "Only DRAFT or REJECTED artifacts can be edited."
            )

        before_state = artifact.to_audit_dict()
        prev_content = {}
        if artifact.current_version_id:
            current_version = await self._repo.get_version(artifact.current_version_id)
            prev_content = current_version.content
            # Mark previous version as not current
            await self._repo.mark_version_not_current(artifact.current_version_id)

        content_hash = self._hash_content(content)
        diff = self._compute_diff(prev_content, content)
        new_version_number = (artifact.current_version_number or 0) + 1

        version = ArtifactVersion(
            artifact_id=artifact.id,
            organization_id=organization_id,
            version_number=new_version_number,
            is_current=True,
            content=content,
            content_hash=content_hash,
            content_diff=diff,
            status_at_creation=artifact.status,
            change_summary=change_summary,
            created_by_id=user.id,
            created_at=datetime.now(UTC),
        )
        self._db.add(version)
        await self._db.flush()

        artifact.current_version_id = version.id
        artifact.current_version_number = new_version_number

        await self._audit.log(
            action=AuditAction.ARTIFACT_UPDATED,
            resource_type="artifact",
            organization_id=organization_id,
            actor_user_id=user.id,
            resource_id=artifact.id,
            before_state=before_state,
            after_state=artifact.to_audit_dict(),
        )

        return artifact

    async def submit_for_review(
        self,
        artifact_id: UUID,
        organization_id: UUID,
        user: User,
    ) -> Artifact:
        """Transition artifact from DRAFT to IN_REVIEW."""
        check_permission(user, Permission.ARTIFACT_SUBMIT)
        artifact = await self._transition(
            artifact_id,
            organization_id,
            user,
            ArtifactStatus.IN_REVIEW,
            AuditAction.ARTIFACT_SUBMITTED,
        )
        await self._notify.create(
            organization_id=organization_id,
            recipient_id=artifact.created_by_id,
            notification_type=NotificationType.ARTIFACT_SUBMITTED,
            title="Artifact submitted for review",
            body=f'"{artifact.name}" has been submitted for review.',
            resource_type="artifact",
            resource_id=artifact.id,
        )
        return artifact

    async def approve(
        self,
        artifact_id: UUID,
        organization_id: UUID,
        user: User,
        comments: str | None = None,
    ) -> Artifact:
        """Transition artifact from IN_REVIEW to APPROVED."""
        check_permission(user, Permission.ARTIFACT_APPROVE)
        artifact = await self._transition(
            artifact_id,
            organization_id,
            user,
            ArtifactStatus.APPROVED,
            AuditAction.ARTIFACT_APPROVED,
            metadata={"comments": comments},
        )
        await self._create_approval_record(artifact, user, "APPROVED", comments)
        await self._notify.create(
            organization_id=organization_id,
            recipient_id=artifact.created_by_id,
            notification_type=NotificationType.ARTIFACT_APPROVED,
            title="Artifact approved",
            body=f'"{artifact.name}" has been approved by {user.full_name}.',
            resource_type="artifact",
            resource_id=artifact.id,
        )
        return artifact

    async def reject(
        self,
        artifact_id: UUID,
        organization_id: UUID,
        user: User,
        comments: str,
    ) -> Artifact:
        """Transition artifact from IN_REVIEW to REJECTED. Comment is required."""
        check_permission(user, Permission.ARTIFACT_REJECT)
        artifact = await self._transition(
            artifact_id,
            organization_id,
            user,
            ArtifactStatus.REJECTED,
            AuditAction.ARTIFACT_REJECTED,
            metadata={"comments": comments},
        )
        await self._create_approval_record(artifact, user, "REJECTED", comments)
        await self._notify.create(
            organization_id=organization_id,
            recipient_id=artifact.created_by_id,
            notification_type=NotificationType.ARTIFACT_REJECTED,
            title="Artifact rejected",
            body=f'"{artifact.name}" was rejected by {user.full_name}. Reason: {comments}',
            resource_type="artifact",
            resource_id=artifact.id,
        )
        return artifact

    async def revise(
        self,
        artifact_id: UUID,
        organization_id: UUID,
        user: User,
    ) -> Artifact:
        """Transition artifact from REJECTED to DRAFT for revision."""
        check_permission(user, Permission.ARTIFACT_EDIT)
        return await self._transition(
            artifact_id,
            organization_id,
            user,
            ArtifactStatus.DRAFT,
            AuditAction.ARTIFACT_UPDATED,
            metadata={"action": "revise"},
        )

    async def amend(
        self,
        artifact_id: UUID,
        organization_id: UUID,
        user: User,
    ) -> Artifact:
        """Begin amendment of a LOCKED artifact. Admin only."""
        check_permission(user, Permission.ARTIFACT_LOCK)
        return await self._transition(
            artifact_id,
            organization_id,
            user,
            ArtifactStatus.AMENDED,
            AuditAction.ARTIFACT_AMENDED,
        )

    async def lock(
        self,
        artifact_id: UUID,
        organization_id: UUID,
        user: User,
    ) -> Artifact:
        """Lock an APPROVED artifact, making it permanently immutable."""
        check_permission(user, Permission.ARTIFACT_LOCK)
        artifact = await self._transition(
            artifact_id,
            organization_id,
            user,
            ArtifactStatus.LOCKED,
            AuditAction.ARTIFACT_LOCKED,
        )
        artifact.locked_at = datetime.now(UTC)
        artifact.locked_by_id = user.id
        return artifact

    async def delete_artifact(
        self,
        artifact_id: UUID,
        organization_id: UUID,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Soft-delete a DRAFT artifact. Contributors may delete only their own."""
        check_permission(user, Permission.ARTIFACT_DELETE_DRAFT)

        artifact = await self._repo.get_by_id(artifact_id, organization_id)

        if artifact.status != ArtifactStatus.DRAFT:
            raise WorkflowError(
                f"Cannot delete artifact in status {artifact.status}. "
                "Only DRAFT artifacts can be removed from a study."
            )

        if user.effective_role != Role.ADMIN and artifact.created_by_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PERMISSION_DENIED",
                    "message": "Only the creator or an Admin can delete this artifact.",
                },
            )

        before_state = artifact.to_audit_dict()
        artifact.deleted_at = datetime.now(UTC)

        await self._audit.log(
            action=AuditAction.ARTIFACT_DELETED,
            resource_type="artifact",
            organization_id=organization_id,
            actor_user_id=user.id,
            resource_id=artifact.id,
            before_state=before_state,
            after_state={"deleted_at": artifact.deleted_at.isoformat()},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def get_artifact_export(
        self,
        artifact_id: UUID,
        organization_id: UUID,
    ) -> tuple[Artifact, dict]:
        """Return artifact metadata and current version content for download."""
        artifact = await self._repo.get_by_id(artifact_id, organization_id)
        if artifact.current_version_id is None:
            return artifact, {}
        version = await self._repo.get_version(artifact.current_version_id)
        return artifact, version.content or {}

    async def get_artifact_csv_export(
        self,
        artifact_id: UUID,
        organization_id: UUID,
    ) -> tuple[str, str]:
        """Return CSV filename and body for synthetic/tabular artifacts."""
        from fastapi import HTTPException, status

        from app.services.synthetic_data_service import SyntheticDataService

        artifact, content = await self.get_artifact_export(artifact_id, organization_id)
        try:
            return SyntheticDataService.csv_from_content(content, artifact.name)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "CSV_NOT_AVAILABLE",
                    "message": str(exc),
                },
            ) from exc

    async def export_artifact_file(
        self,
        artifact_id: UUID,
        organization_id: UUID,
        user: User,
        export_format: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ExportResult:
        """Generate a formatted artifact download and record audit trail."""
        artifact, content = await self.get_artifact_export(artifact_id, organization_id)
        if not content:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "NO_CONTENT",
                    "message": "Artifact has no version content to export.",
                },
            )

        study = await self._study_repo.get(artifact.study_id, organization_id)
        study_slug = study.short_name or study.protocol_number or study.name
        study_name = study.name

        try:
            result = ArtifactExportService.export_artifact(
                artifact,
                content,
                study_name=study_name,
                study_slug=study_slug,
                export_format=export_format,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "EXPORT_NOT_AVAILABLE",
                    "message": str(exc),
                },
            ) from exc

        version_id = artifact.current_version_id
        await self._audit.log(
            action=AuditAction.ARTIFACT_EXPORTED,
            resource_type="artifact",
            organization_id=organization_id,
            actor_user_id=user.id,
            resource_id=artifact.id,
            after_state={
                "artifact_id": str(artifact.id),
                "artifact_version_id": str(version_id) if version_id else None,
                "artifact_type": artifact.artifact_type.value,
                "format": export_format,
                "filename": result.filename,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self._graph.emit_event(
            organization_id=organization_id,
            study_id=artifact.study_id,
            event_type="ARTIFACT_EXPORTED",
            payload={
                "entity_type": "artifact",
                "entity_id": str(artifact.id),
                "artifact_type": artifact.artifact_type.value,
                "format": export_format,
                "filename": result.filename,
                "artifact_version_id": str(version_id) if version_id else None,
            },
            actor_user_id=user.id,
        )
        return result

    async def _transition(
        self,
        artifact_id: UUID,
        organization_id: UUID,
        user: User,
        new_status: ArtifactStatus,
        audit_action: AuditAction,
        metadata: dict | None = None,
    ) -> Artifact:
        artifact = await self._repo.get_by_id(artifact_id, organization_id)
        before_state = artifact.to_audit_dict()

        if not artifact.can_transition_to(new_status):
            raise WorkflowError(
                f"Cannot transition artifact from {artifact.status} to {new_status}."
            )

        artifact.status = new_status
        # Keep updated_at in-instance so async response serialization does not
        # lazy-load a server-generated column (MissingGreenlet on validate).
        artifact.updated_at = datetime.now(UTC)

        await self._audit.log(
            action=audit_action,
            resource_type="artifact",
            organization_id=organization_id,
            actor_user_id=user.id,
            resource_id=artifact.id,
            before_state=before_state,
            after_state=artifact.to_audit_dict(),
            extra_data=metadata or {},
        )

        return artifact

    async def _create_approval_record(
        self,
        artifact: Artifact,
        user: User,
        decision: str,
        comments: str | None,
    ) -> None:
        from app.models.approval import Approval, ApprovalDecision

        approval = Approval(
            organization_id=artifact.organization_id,
            artifact_id=artifact.id,
            artifact_version_id=artifact.current_version_id,
            approver_id=user.id,
            decision=ApprovalDecision(decision),
            comments=comments,
            electronic_signature={
                "full_name": user.full_name,
                "email": user.email,
                "role": user.effective_role.value,
                "timestamp": datetime.now(UTC).isoformat(),
                "meaning": f"I have reviewed and {decision.lower()} this artifact.",
            },
            created_at=datetime.now(UTC),
        )
        self._db.add(approval)

    @staticmethod
    def _hash_content(content: dict) -> str:
        serialized = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    @staticmethod
    def _compute_diff(old: dict, new: dict) -> list[dict] | None:
        """
        Compute JSON Patch (RFC 6902) between old and new content.
        Returns None if there is no meaningful diff.
        """
        try:
            import jsonpatch

            patch = jsonpatch.make_patch(old, new)
            patch_list = list(patch)
            return patch_list if patch_list else None
        except ImportError:
            return None
