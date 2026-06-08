"""Dual-programmer statistical QC — primary vs independent QC R programs."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.study import Study
    from app.models.user import User


class StatisticalQCWorkflow(str, enum.Enum):
    """Pipeline step where dual-programmer R QC applies."""

    RAW_TO_SDTM = "RAW_TO_SDTM"
    SDTM_TO_ADAM = "SDTM_TO_ADAM"
    ADAM_TO_TLF = "ADAM_TO_TLF"


class StatisticalQCStatus(str, enum.Enum):
    """Outcome of a dual-programmer QC run."""

    PENDING = "PENDING"
    PROGRAMS_GENERATED = "PROGRAMS_GENERATED"
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    R_UNAVAILABLE = "R_UNAVAILABLE"


class StatisticalProgramQCRun(UUIDMixin, Base):
    """
    Append-only record of a dual-programmer R QC exercise.

    Primary and QC programmers each produce independent R code from the same
    input specification. Outputs are executed and compared when R is available.
    """

    __tablename__ = "statistical_program_qc_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_step: Mapped[StatisticalQCWorkflow] = mapped_column(
        Enum(StatisticalQCWorkflow, name="statistical_qc_workflow"),
        nullable=False,
    )
    status: Mapped[StatisticalQCStatus] = mapped_column(
        Enum(StatisticalQCStatus, name="statistical_qc_status"),
        nullable=False,
        default=StatisticalQCStatus.PENDING,
    )
    source_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    output_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    primary_ai_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    qc_ai_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    primary_r_program: Mapped[str] = mapped_column(Text, nullable=False, default="")
    qc_r_program: Mapped[str] = mapped_column(Text, nullable=False, default="")
    primary_program_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    qc_program_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comparison_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    organization: Mapped[Organization] = relationship("Organization")
    study: Mapped[Study] = relationship("Study")
    created_by: Mapped[User] = relationship("User")
