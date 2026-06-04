"""
Artifact lifecycle service. Enforces workflow transitions and versioning.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ArtifactLockedError, WorkflowError
from app.core.permissions import Permission, check_permission
from app.models.artifact import Artifact, ArtifactStatus, ArtifactType, ArtifactVersion
from app.models.audit import AuditAction
from app.models.user import User
from app.models.notification import NotificationType
from app.repositories.artifact_repository import ArtifactRepository
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService


class ArtifactService:
    """Business logic for artifact lifecycle management."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = ArtifactRepository(db)
        self._audit = AuditService(db)
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
