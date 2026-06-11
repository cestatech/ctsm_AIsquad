"""Pydantic schemas for ADaM generation API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class StudyADAMReadinessResponse(BaseModel):
    study_id: UUID
    sdtm_artifact_count: int
    ready: bool
    issues: list[str]
    sdtm_artifacts: list[dict]


class ADAMGenerationResponse(BaseModel):
    artifact_id: UUID
    artifact_version_id: UUID
    ai_decision_id: UUID
    validation_run_id: UUID
    dataset_count: int
    study_id: UUID
    source_sdtm_artifact_ids: list[UUID] = Field(default_factory=list)


class ADaMDefineExportResponse(BaseModel):
    """Binary ADaM define.xml export payload."""

    filename: str
    media_type: str = "application/xml"
    content: bytes


class ADRGExportResponse(BaseModel):
    """Binary ADRG DOCX export payload."""

    filename: str
    media_type: str = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    content: bytes
