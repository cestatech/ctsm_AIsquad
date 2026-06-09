"""Pydantic schemas for the file upload API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.data_source import DataSourceType


class UploadedFileResponse(BaseModel):
    """Response schema for an uploaded file record."""

    id: UUID
    organization_id: UUID
    study_id: UUID
    uploaded_by_id: UUID
    original_filename: str
    stored_filename: str
    file_size_bytes: int
    mime_type: str
    description: str | None
    extracted_metadata: dict
    file_hash: str | None
    upload_status: str
    data_source_type: DataSourceType
    data_cut_label: str | None
    data_cut_date: date | None
    is_synthetic: bool
    data_cut_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LiveDataUploadRequest(BaseModel):
    """Optional metadata for live clinical data uploads."""

    data_source_type: DataSourceType = Field(
        default=DataSourceType.LIVE_FINAL,
        description="LIVE_INTERIM or LIVE_FINAL for uploaded clinical data.",
    )
    data_cut_label: str | None = Field(
        default=None,
        max_length=256,
        description="Human-readable data cut label, e.g. Week 8 Interim Data Cut.",
    )
    data_cut_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class UploadedFileListResponse(BaseModel):
    items: list[UploadedFileResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
