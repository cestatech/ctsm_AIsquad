"""RawDataset, RawField, and FieldMappingVersion models — Phase 2 data layer.

One UploadedFile → many RawDatasets (sheets) → many RawFields (columns).
Mapping progresses: UNMAPPED → PENDING_APPROVAL → APPROVED / REJECTED.
All mutations produce FieldMappingVersion audit snapshots.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.upload import UploadedFile
    from app.models.user import User


class RawDataset(UUIDMixin, TimestampMixin, Base):
    """
    One sheet (XLSX) or the entire file (CSV) within an UploadedFile.

    Relationships:
        - uploaded_file: parent UploadedFile
        - fields: parsed RawField columns
    """

    __tablename__ = "raw_datasets"

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
    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_name: Mapped[str] = mapped_column(String(500), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parse_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    uploaded_file: Mapped["UploadedFile"] = relationship(
        "UploadedFile", back_populates="datasets"
    )
    fields: Mapped[list["RawField"]] = relationship(
        "RawField", back_populates="raw_dataset", order_by="RawField.column_index"
    )


class RawField(UUIDMixin, TimestampMixin, Base):
    """
    One column in a RawDataset, with profiling stats and optional mapping to
    eCRF/SDTM identifiers.

    mapping_status lifecycle: UNMAPPED → PENDING_APPROVAL → APPROVED / REJECTED
    Every change to a mapping creates a FieldMappingVersion snapshot.

    Relationships:
        - raw_dataset: parent RawDataset
        - mapping_versions: ordered history of mapping changes
    """

    __tablename__ = "raw_fields"

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
    raw_dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_name: Mapped[str] = mapped_column(String(500), nullable=False)
    column_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inferred_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="string"
    )
    sample_values: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distinct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Mapping state
    mapped_ecrf_field_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    mapped_sdtm_variable_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    mapping_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="UNMAPPED"
    )
    mapping_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    raw_dataset: Mapped["RawDataset"] = relationship(
        "RawDataset", back_populates="fields"
    )
    mapping_versions: Mapped[list["FieldMappingVersion"]] = relationship(
        "FieldMappingVersion",
        back_populates="raw_field",
        order_by="FieldMappingVersion.version_number",
    )


class FieldMappingVersion(UUIDMixin, Base):
    """
    Immutable snapshot of a RawField mapping at a specific version.

    Append-only — never updated or deleted. Provides a complete audit
    trail of every mapping change and approval decision.

    Relationships:
        - raw_field: the RawField this version belongs to
        - changed_by: the user who made the change
        - approved_by: the user who approved (if applicable)
    """

    __tablename__ = "field_mapping_versions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    mapped_ecrf_field_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    mapped_sdtm_variable_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    mapping_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    raw_field: Mapped["RawField"] = relationship(
        "RawField", back_populates="mapping_versions"
    )
    changed_by: Mapped["User"] = relationship(
        "User", foreign_keys=[changed_by_id]
    )
    approved_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[approved_by_id]
    )
