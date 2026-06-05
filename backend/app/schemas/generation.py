"""Pydantic schemas for the AI Generation API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.artifact import ArtifactType
from app.models.generation import GenerationJobStatus


class GenerationJobCreate(BaseModel):
    model_config = {"protected_namespaces": ()}

    study_id: UUID
    artifact_type: ArtifactType
    model_id: str = Field(default="claude-sonnet-4-6", max_length=100)
    prompt_template_id: str | None = Field(default=None, max_length=100)
    input_context: dict = Field(default_factory=dict)


class GenerationFromBriefRequest(BaseModel):
    """Request body for triggering generation directly from a compiled Study Brief."""

    model_config = {"protected_namespaces": ()}

    brief_id: UUID
    artifact_type: ArtifactType
    model_id: str = Field(default="claude-sonnet-4-6", max_length=100)


class GenerationJobResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID
    artifact_type: ArtifactType
    status: GenerationJobStatus
    model_id: str
    model_version: str | None
    prompt_template_id: str | None
    input_context: dict
    output_artifact_id: UUID | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    triggered_by_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class GenerationJobListResponse(BaseModel):
    items: list[GenerationJobResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
