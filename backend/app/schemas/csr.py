"""Pydantic schemas for CSR generation API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class CSRRequirementResponse(BaseModel):
    key: str
    label: str
    met: bool
    detail: str = ""


class StudyCSRReadinessResponse(BaseModel):
    study_id: UUID
    tlf_artifact_count: int
    protocol_artifact_count: int
    sap_artifact_count: int
    ready: bool
    issues: list[str]
    tlf_artifacts: list[dict]
    data_cut_id: UUID | None = None
    data_source_type: str | None = None
    data_cut_label: str | None = None
    csr_kind: str | None = None
    requirements: list[CSRRequirementResponse] = Field(default_factory=list)
    sdtm_artifact_id: UUID | None = None
    adam_artifact_id: UUID | None = None
    source_upload_id: UUID | None = None
    synthetic_data_run_id: UUID | None = None


class CSRGenerationRequest(BaseModel):
    data_cut_id: UUID | None = None
    generate_shell: bool = False


class CSRGenerationResponse(BaseModel):
    artifact_id: UUID
    artifact_version_id: UUID
    ai_decision_id: UUID
    validation_run_id: UUID
    section_count: int
    study_id: UUID
    source_tlf_artifact_ids: list[UUID] = Field(default_factory=list)
    source_study_artifact_ids: list[UUID] = Field(default_factory=list)


class ReviewersGuideResponse(BaseModel):
    """Binary Reviewer's Guide (SDRG) PDF export payload."""

    filename: str
    media_type: str = "application/pdf"
    content: bytes


class CSRSectionRegenerateRequest(BaseModel):
    instructions: str | None = None


class CSRSectionProseResponse(BaseModel):
    section_id: str
    prose: str
    ai_decision_id: UUID
