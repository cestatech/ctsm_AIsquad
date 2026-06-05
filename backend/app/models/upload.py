"""UploadedFile model — stores metadata for files uploaded to a study."""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.study import Study


class UploadedFile(UUIDMixin, TimestampMixin, Base):
    """
    Metadata record for a file uploaded to a study.

    Stores the original filename, path in local/S3 storage, MIME type, size,
    and an optional extracted metadata blob (column headers, row count, etc.).
    Append-only — files are never deleted, only soft-archived.

    Relationships:
        - study: parent Study
        - uploaded_by: User who uploaded the file
    """

    __tablename__ = "uploaded_files"

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
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    study: Mapped["Study"] = relationship("Study")
    uploaded_by: Mapped["User"] = relationship("User", foreign_keys=[uploaded_by_id])
