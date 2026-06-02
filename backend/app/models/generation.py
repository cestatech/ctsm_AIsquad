from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.artifact import ArtifactType

if TYPE_CHECKING:
    from app.models.artifact import Artifact
    from app.models.study import Study
    from app.models.user import User


class GenerationJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GenerationJob(UUIDMixin, TimestampMixin, Base):
    """
    AI generation job record.

    All inputs are logged for reproducibility.
    Output is always a DRAFT artifact — never auto-approved.

    The input_context_hash and prompt_template_hash allow exact reproduction
    of a generation given the same model version.
    """

    __tablename__ = "generation_jobs"

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
    status: Mapped[GenerationJobStatus] = mapped_column(
        Enum(GenerationJobStatus, name="generation_job_status"),
        nullable=False,
        default=GenerationJobStatus.PENDING,
    )
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt_template_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_template_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input_context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    triggered_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    study: Mapped["Study"] = relationship("Study")
    output_artifact: Mapped["Artifact | None"] = relationship("Artifact")
    triggered_by: Mapped["User"] = relationship("User")
