from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.study import Study
    from app.models.comment import Comment
    from app.models.approval import Approval
    from app.models.validation import ValidationRun


class ArtifactStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    LOCKED = "LOCKED"
    AMENDED = "AMENDED"
    SUPERSEDED = "SUPERSEDED"


class ArtifactType(str, enum.Enum):
    PROTOCOL = "PROTOCOL"
    ICF = "ICF"
    SAP = "SAP"
    EDC_CRF = "EDC_CRF"
    TRACEABILITY_MATRIX = "TRACEABILITY_MATRIX"
    SDTM_DATASET = "SDTM_DATASET"
    ADAM_DATASET = "ADAM_DATASET"
    TLF = "TLF"
    VALIDATION_REPORT = "VALIDATION_REPORT"
    CSR = "CSR"
    SUBMISSION_PACKAGE = "SUBMISSION_PACKAGE"
    OTHER = "OTHER"


# Valid workflow transitions: (from_status, to_status) → minimum_role
VALID_TRANSITIONS: dict[tuple[ArtifactStatus, ArtifactStatus], str] = {
    (ArtifactStatus.DRAFT, ArtifactStatus.IN_REVIEW): "CONTRIBUTOR",
    (ArtifactStatus.IN_REVIEW, ArtifactStatus.APPROVED): "REVIEWER",
    (ArtifactStatus.IN_REVIEW, ArtifactStatus.REJECTED): "REVIEWER",
    (ArtifactStatus.REJECTED, ArtifactStatus.DRAFT): "CONTRIBUTOR",
    (ArtifactStatus.APPROVED, ArtifactStatus.LOCKED): "ADMIN",
    (ArtifactStatus.LOCKED, ArtifactStatus.AMENDED): "ADMIN",
    (ArtifactStatus.APPROVED, ArtifactStatus.SUPERSEDED): "SYSTEM",
    (ArtifactStatus.LOCKED, ArtifactStatus.SUPERSEDED): "SYSTEM",
}


class Artifact(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """
    Core content object representing a clinical trial artifact.

    Examples: Protocol, ICF, SAP, SDTM dataset, ADaM dataset, TLF, CSR.

    All content changes create a new ArtifactVersion record.
    The current content is always in the latest version.

    Relationships:
        - study: parent Study
        - versions: append-only ArtifactVersion history
        - approvals: Approval records (approve/reject actions)
        - comments: review Comments
        - validation_runs: ValidationRun results
        - amendment_of: if this is an amendment, the LOCKED artifact it amends
    """

    __tablename__ = "artifacts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studies.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(
        Enum(ArtifactType, name="artifact_type"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ArtifactStatus] = mapped_column(
        Enum(ArtifactStatus, name="artifact_status"),
        nullable=False,
        default=ArtifactStatus.DRAFT,
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "artifact_versions.id", use_alter=True, name="fk_artifacts_current_version"
        ),
        nullable=True,
    )
    current_version_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    amendment_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=True
    )
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=True
    )
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)), nullable=True)
    extra_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    study: Mapped["Study"] = relationship("Study", back_populates="artifacts")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    locker: Mapped["User | None"] = relationship("User", foreign_keys=[locked_by_id])
    versions: Mapped[list["ArtifactVersion"]] = relationship(
        "ArtifactVersion",
        foreign_keys="ArtifactVersion.artifact_id",
        back_populates="artifact",
        order_by="ArtifactVersion.version_number",
    )
    approvals: Mapped[list["Approval"]] = relationship(
        "Approval", back_populates="artifact"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="artifact"
    )
    validation_runs: Mapped[list["ValidationRun"]] = relationship(
        "ValidationRun", back_populates="artifact"
    )

    def is_locked(self) -> bool:
        return self.status == ArtifactStatus.LOCKED

    def can_transition_to(self, new_status: ArtifactStatus) -> bool:
        return (self.status, new_status) in VALID_TRANSITIONS

    def to_audit_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "artifact_type": self.artifact_type,
            "status": self.status,
            "current_version_number": self.current_version_number,
        }


class ArtifactVersion(UUIDMixin, Base):
    """
    Append-only version snapshot for an artifact.

    Every content change creates a new row. No updates or deletes permitted.
    Database trigger enforces immutability at the DB level.

    Relationships:
        - artifact: parent Artifact
        - creator: User who created this version
    """

    __tablename__ = "artifact_versions"

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_diff: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_at_creation: Mapped[ArtifactStatus] = mapped_column(
        Enum(ArtifactStatus, name="artifact_status"), nullable=False
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    artifact: Mapped["Artifact"] = relationship(
        "Artifact",
        foreign_keys=[artifact_id],
        back_populates="versions",
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
