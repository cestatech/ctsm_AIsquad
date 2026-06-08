"""Pydantic schemas for CSR generation API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class StudyCSRReadinessResponse(BaseModel):
    study_id: UUID
    tlf_artifact_count: int
    protocol_artifact_count: int
    sap_artifact_count: int
    ready: bool
    issues: list[str]
    tlf_artifacts: list[dict]


class CSRGenerationResponse(BaseModel):
    artifact_id: UUID
    artifact_version_id: UUID
    ai_decision_id: UUID
    validation_run_id: UUID
    section_count: int
    study_id: UUID
    source_tlf_artifact_ids: list[UUID] = Field(default_factory=list)
    source_study_artifact_ids: list[UUID] = Field(default_factory=list)
