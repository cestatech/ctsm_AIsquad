"""Pydantic schemas for submission packaging API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.submission import SubmissionPackageStatus


class SubmissionReadinessResponse(BaseModel):
    study_id: UUID
    ready: bool
    issues: list[str]
    required_artifacts: dict[str, str | None] = Field(default_factory=dict)


class SubmissionPackageResponse(BaseModel):
    id: UUID
    study_id: UUID
    organization_id: UUID
    status: SubmissionPackageStatus
    artifact_ids: list[str]
    local_path: str | None
    package_checksum: str | None
    error_message: str | None = None
    created_by_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubmissionPackageListResponse(BaseModel):
    items: list[SubmissionPackageResponse]
    total: int


class SubmissionCreateResponse(BaseModel):
    package_id: UUID
    status: SubmissionPackageStatus
    artifact_ids: list[str]
    issues: list[str] = Field(default_factory=list)


class SubmissionManifestResponse(BaseModel):
    package_id: UUID
    study_id: UUID
    status: SubmissionPackageStatus
    package_checksum: str | None
    error_message: str | None = None
    data_classification: str | None = None
    manifest: dict


class ECTDExportResponse(BaseModel):
    """Binary eCTD backbone export payload (index.xml + index-md5.txt zip)."""

    filename: str
    media_type: str = "application/zip"
    content: bytes
