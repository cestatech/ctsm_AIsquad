"""Submission package model — eCTD Module 5 regulatory bundle assembly."""

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


class SubmissionPackageStatus(str, enum.Enum):
    """Lifecycle status for a regulatory submission package."""

    DRAFT = "DRAFT"
    PACKAGING = "PACKAGING"
    READY = "READY"
    SUBMITTED = "SUBMITTED"


class SubmissionPackage(UUIDMixin, Base):
    """
    Assembled eCTD submission package for a study.

    Bundles approved SDTM, ADaM, TLF, CSR artifacts with define.xml and
    manifest checksums under org-scoped storage.
    """

    __tablename__ = "submission_packages"

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
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[SubmissionPackageStatus] = mapped_column(
        Enum(SubmissionPackageStatus, name="submission_package_status"),
        nullable=False,
        default=SubmissionPackageStatus.DRAFT,
        index=True,
    )
    artifact_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    local_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    package_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization: Mapped["Organization"] = relationship(
        "Organization", foreign_keys=[organization_id], lazy="raise"
    )
    study: Mapped["Study"] = relationship(
        "Study", foreign_keys=[study_id], lazy="raise"
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_id], lazy="raise"
    )
