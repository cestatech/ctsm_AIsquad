from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.artifact import Artifact, ArtifactVersion
    from app.models.user import User


class ApprovalDecision(str, enum.Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Approval(UUIDMixin, Base):
    """
    Immutable approval chain record.

    Each approve/reject action creates one record.
    No updates or deletes permitted after creation.

    The electronic_signature field captures 21 CFR Part 11 requirements:
    full name, date/time, role, and meaning of signature.

    Relationships:
        - artifact: the Artifact this decision applies to
        - artifact_version: the specific version that was approved/rejected
        - approver: the User who made the decision
    """

    __tablename__ = "approvals"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifact_versions.id"),
        nullable=False,
    )
    approver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    decision: Mapped[ApprovalDecision] = mapped_column(
        Enum(ApprovalDecision, name="approval_decision"), nullable=False
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    electronic_signature: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NO updated_at — immutable once created

    artifact: Mapped["Artifact"] = relationship("Artifact", back_populates="approvals")
    artifact_version: Mapped["ArtifactVersion"] = relationship("ArtifactVersion")
    approver: Mapped["User"] = relationship("User")
