"""Pydantic schemas for the Artifact resource."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.artifact import ArtifactStatus, ArtifactType


class ArtifactCreate(BaseModel):
    """Request body for creating a new artifact."""

    study_id: UUID
    artifact_type: ArtifactType
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    tags: list[str] | None = None
    content: dict | None = None
    change_summary: str | None = None


class ArtifactResponse(BaseModel):
    """Full artifact representation returned by API endpoints."""

    id: UUID
    organization_id: UUID
    study_id: UUID
    artifact_type: ArtifactType
    name: str
    description: str | None
    status: ArtifactStatus
    current_version_id: UUID | None
    current_version_number: int
    locked_at: datetime | None
    tags: list[str] | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ArtifactUpdate(BaseModel):
    """Request body for updating artifact content (DRAFT or REJECTED only)."""

    content: dict
    change_summary: str | None = None


class ArtifactVersionCreator(BaseModel):
    """Minimal creator info embedded in version responses."""

    id: UUID
    full_name: str
    email: str

    model_config = {"from_attributes": True}


class ArtifactVersionResponse(BaseModel):
    """Single artifact version snapshot."""

    id: UUID
    artifact_id: UUID
    organization_id: UUID
    version_number: int
    is_current: bool
    content: dict
    content_hash: str
    content_diff: dict | None
    file_path: str | None
    file_size_bytes: int | None
    file_mime_type: str | None
    change_summary: str | None
    status_at_creation: ArtifactStatus
    created_by_id: UUID
    creator: ArtifactVersionCreator | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ArtifactListResponse(BaseModel):
    items: list[ArtifactResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
