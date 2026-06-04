"""Pydantic schemas for the Validation API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.validation import ValidationStatus


class ValidationRunCreate(BaseModel):
    artifact_id: UUID
    artifact_version_id: UUID
    engine: str = Field(default="internal", max_length=100)
    rule_set_version: str | None = Field(default=None, max_length=50)


class ValidationRunResponse(BaseModel):
    id: UUID
    organization_id: UUID
    artifact_id: UUID
    artifact_version_id: UUID
    engine: str
    status: ValidationStatus
    rule_set_version: str | None
    total_checks: int | None
    passed_checks: int | None
    failed_checks: int | None
    warnings: int | None
    results: dict | None
    report_path: str | None
    started_at: datetime | None
    completed_at: datetime | None
    triggered_by_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ValidationRunListResponse(BaseModel):
    items: list[ValidationRunResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
