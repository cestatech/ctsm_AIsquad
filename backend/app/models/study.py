from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.permissions import Role
from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.artifact import Artifact
    from app.models.organization import Organization
    from app.models.user import User


class StudyPhase(str, enum.Enum):
    PHASE_1 = "PHASE_1"
    PHASE_1_2 = "PHASE_1_2"
    PHASE_2 = "PHASE_2"
    PHASE_2_3 = "PHASE_2_3"
    PHASE_3 = "PHASE_3"
    PHASE_3_4 = "PHASE_3_4"
    PHASE_4 = "PHASE_4"
    OBSERVATIONAL = "OBSERVATIONAL"
    OTHER = "OTHER"


class StudyStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"
    TERMINATED = "TERMINATED"


class Study(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """
    Clinical trial study. Container for all artifacts and member assignments.

    Protocol number is unique per organization.
    Archived studies are read-only — no new artifacts can be created.

    Relationships:
        - organization: parent Organization
        - created_by: User who created this study
        - members: StudyMember records with per-user role assignments
        - artifacts: all Artifact records belonging to this study
    """

    __tablename__ = "studies"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    protocol_number: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    indication: Mapped[str | None] = mapped_column(String(500), nullable=True)
    therapeutic_area: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phase: Mapped[StudyPhase | None] = mapped_column(
        Enum(StudyPhase, name="study_phase"), nullable=True
    )
    status: Mapped[StudyStatus] = mapped_column(
        Enum(StudyStatus, name="study_status"),
        nullable=False,
        default=StudyStatus.DRAFT,
    )
    sponsor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    regulatory_region: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)), nullable=True
    )
    start_date = mapped_column(Date, nullable=True)
    end_date = mapped_column(Date, nullable=True)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="studies")
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    members: Mapped[list["StudyMember"]] = relationship("StudyMember", back_populates="study")
    artifacts: Mapped[list["Artifact"]] = relationship("Artifact", back_populates="study")

    def is_editable(self) -> bool:
        return self.status not in (StudyStatus.ARCHIVED, StudyStatus.TERMINATED)

    def to_audit_dict(self) -> dict:
        return {
            "id": str(self.id),
            "protocol_number": self.protocol_number,
            "name": self.name,
            "status": self.status,
            "phase": self.phase,
        }


class StudyMember(UUIDMixin, TimestampMixin, Base):
    """
    Role assignment for a user within a specific study.

    A user can have different roles on different studies.
    Organization-level Admin role supersedes study-level role for org Admin users.
    """

    __tablename__ = "study_members"

    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studies.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), nullable=False)
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    study: Mapped["Study"] = relationship("Study", back_populates="members")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    invited_by: Mapped["User | None"] = relationship("User", foreign_keys=[invited_by_id])
