"""Pydantic schemas for the raw data / mapping API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RawFieldResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID
    raw_dataset_id: UUID
    column_name: str
    column_index: int
    inferred_type: str
    sample_values: list
    missing_count: int
    distinct_count: int
    min_value: str | None
    max_value: str | None
    mapped_ecrf_field_id: str | None
    mapped_sdtm_variable_id: str | None
    mapping_status: str
    mapping_version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RawDatasetResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID
    uploaded_file_id: UUID
    dataset_name: str
    row_count: int
    column_count: int
    parse_status: str
    parse_error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RawDatasetListResponse(BaseModel):
    items: list[RawDatasetResponse]
    total: int


class FieldMappingVersionResponse(BaseModel):
    id: UUID
    raw_field_id: UUID
    version_number: int
    mapped_ecrf_field_id: str | None
    mapped_sdtm_variable_id: str | None
    mapping_status: str
    changed_by_id: UUID
    approved_by_id: UUID | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FieldMappingRequest(BaseModel):
    mapped_ecrf_field_id: str | None = Field(default=None, max_length=200)
    mapped_sdtm_variable_id: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)


class MappingApprovalRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)


class BulkApproveMappingsResponse(BaseModel):
    approved_count: int
    skipped_count: int
    fields: list[RawFieldResponse]


class BulkRejectMappingsRequest(BaseModel):
    mapping_ids: list[UUID] = Field(min_length=1)
    reason: str = Field(min_length=10, max_length=2000)


class BulkRejectMappingsResponse(BaseModel):
    rejected: int
    failed: int


class StudySDTMReadinessResponse(BaseModel):
    study_id: UUID
    dataset_count: int
    total_fields: int
    approved_fields: int
    ready: bool
    issues: list[str]
    datasets: list[dict]


class SDTMGenerationResponse(BaseModel):
    artifact_id: UUID
    artifact_version_id: UUID
    ai_decision_id: UUID
    validation_run_id: UUID
    domain_count: int
    study_id: UUID
    source_dataset_ids: list[UUID] = Field(default_factory=list)


class MappingValidationResult(BaseModel):
    total_fields: int
    mapped_fields: int
    approved_fields: int
    pending_fields: int
    unmapped_fields: int
    coverage_pct: float
    issues: list[str]


class FieldMappingSuggestion(BaseModel):
    field_id: UUID
    column_name: str
    mapped_ecrf_field_id: str | None
    mapped_sdtm_variable_id: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class SuggestMappingsResponse(BaseModel):
    ai_decision_id: UUID
    dataset_id: UUID
    suggestions: list[FieldMappingSuggestion]
    model_id: str

    model_config = {"protected_namespaces": ()}


class ApplyMappingSuggestionItem(BaseModel):
    field_id: UUID
    mapped_ecrf_field_id: str | None = Field(default=None, max_length=200)
    mapped_sdtm_variable_id: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)


class ApplyMappingSuggestionsRequest(BaseModel):
    ai_decision_id: UUID
    suggestions: list[ApplyMappingSuggestionItem] = Field(min_length=1)
