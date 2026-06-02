from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.artifact import Artifact, ArtifactVersion
    from app.models.user import User


class ValidationStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"


class ValidationRun(UUIDMixin, Base):
    """
    Validation job record. Results are preserved as regulatory evidence.

    Supports internal validation and Pinnacle 21 integration.
    """

    __tablename__ = "validation_runs"

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
    engine: Mapped[str] = mapped_column(String(100), nullable=False, default="internal")
    status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, name="validation_status"),
        nullable=False,
        default=ValidationStatus.PENDING,
    )
    rule_set_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_checks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed_checks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed_checks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    triggered_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    artifact: Mapped["Artifact"] = relationship(
        "Artifact", back_populates="validation_runs"
    )
    artifact_version: Mapped["ArtifactVersion"] = relationship("ArtifactVersion")
    triggered_by: Mapped["User"] = relationship("User")
