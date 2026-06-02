from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.organization import Organization


class AuditAction(str, enum.Enum):
    # Authentication
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_LOGIN_FAILED = "user.login_failed"
    USER_TOKEN_REFRESHED = "user.token_refreshed"

    # User management
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DEACTIVATED = "user.deactivated"
    USER_ROLE_CHANGED = "user.role_changed"
    USER_PASSWORD_CHANGED = "user.password_changed"

    # Organization
    ORG_CREATED = "org.created"
    ORG_SETTINGS_CHANGED = "org.settings_changed"
    ORG_MEMBER_ADDED = "org.member_added"
    ORG_MEMBER_REMOVED = "org.member_removed"

    # Study
    STUDY_CREATED = "study.created"
    STUDY_UPDATED = "study.updated"
    STUDY_ARCHIVED = "study.archived"
    STUDY_MEMBER_ADDED = "study.member_added"
    STUDY_MEMBER_REMOVED = "study.member_removed"
    STUDY_MEMBER_ROLE_CHANGED = "study.member_role_changed"

    # Artifact
    ARTIFACT_CREATED = "artifact.created"
    ARTIFACT_UPDATED = "artifact.updated"
    ARTIFACT_SUBMITTED = "artifact.submitted"
    ARTIFACT_APPROVED = "artifact.approved"
    ARTIFACT_REJECTED = "artifact.rejected"
    ARTIFACT_LOCKED = "artifact.locked"
    ARTIFACT_AMENDED = "artifact.amended"
    ARTIFACT_SUPERSEDED = "artifact.superseded"
    ARTIFACT_DELETED = "artifact.deleted"

    # Versions
    ARTIFACT_VERSION_CREATED = "artifact_version.created"

    # Comments
    COMMENT_CREATED = "comment.created"
    COMMENT_UPDATED = "comment.updated"
    COMMENT_DELETED = "comment.deleted"
    COMMENT_RESOLVED = "comment.resolved"

    # Validation
    VALIDATION_RUN_STARTED = "validation.run_started"
    VALIDATION_RUN_COMPLETED = "validation.run_completed"
    VALIDATION_RUN_FAILED = "validation.run_failed"

    # AI
    AI_GENERATION_STARTED = "ai.generation_started"
    AI_GENERATION_COMPLETED = "ai.generation_completed"
    AI_GENERATION_FAILED = "ai.generation_failed"

    # Data
    DATA_FILE_UPLOADED = "data.file_uploaded"
    DATA_FILE_DELETED = "data.file_deleted"

    # Submission
    SUBMISSION_PACKAGE_CREATED = "submission.package_created"
    SUBMISSION_PACKAGE_EXPORTED = "submission.package_exported"


class AuditLog(UUIDMixin, Base):
    """
    Immutable audit trail record. Append-only.

    Database triggers prevent UPDATE and DELETE on this table.
    Application DB role has INSERT-only grant.

    Minimum retention: 15 years (21 CFR Part 11 / ICH E6).

    Relationships:
        - organization: the tenant this event belongs to
        - actor: the user who performed the action
    """

    __tablename__ = "audit_logs"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action"), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NO updated_at — append-only table

    organization: Mapped["Organization | None"] = relationship("Organization")
    actor: Mapped["User | None"] = relationship("User")
