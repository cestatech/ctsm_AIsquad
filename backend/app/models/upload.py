"""UploadedFile model — stores metadata for files uploaded to a study."""

from __future__ import annotations

import uuid

from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.data_source import DataSourceType

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.study import Study
    from app.models.raw_data import RawDataset


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
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    upload_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="UPLOADED"
    )
    data_source_type: Mapped[DataSourceType] = mapped_column(
        Enum(DataSourceType, name="data_source_type"),
        nullable=False,
        default=DataSourceType.LIVE_FINAL,
    )
    data_cut_label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    data_cut_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    data_cut_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    study: Mapped["Study"] = relationship("Study")
    uploaded_by: Mapped["User"] = relationship("User", foreign_keys=[uploaded_by_id])
    datasets: Mapped[list["RawDataset"]] = relationship(
        "RawDataset", back_populates="uploaded_file", order_by="RawDataset.created_at"
    )
