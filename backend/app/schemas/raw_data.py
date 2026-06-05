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
    fields: list[RawFieldResponse] = []

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


class MappingValidationResult(BaseModel):
    total_fields: int
    mapped_fields: int
    approved_fields: int
    pending_fields: int
    unmapped_fields: int
    coverage_pct: float
    issues: list[str]
