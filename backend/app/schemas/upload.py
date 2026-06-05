"""Pydantic schemas for the file upload API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadedFileListResponse(BaseModel):
    items: list[UploadedFileResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
