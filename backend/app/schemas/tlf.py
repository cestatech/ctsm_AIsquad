"""Pydantic schemas for TLF generation API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class TLFGenerationResponse(BaseModel):
    artifact_id: UUID
    artifact_version_id: UUID
    ai_decision_id: UUID
    validation_run_id: UUID
    table_count: int
    study_id: UUID
    source_adam_artifact_ids: list[UUID] = Field(default_factory=list)
