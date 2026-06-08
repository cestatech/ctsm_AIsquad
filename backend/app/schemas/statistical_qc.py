"""Schemas for dual-programmer statistical QC API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StatisticalQCRunResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID
    workflow_step: str
    status: str
    source_artifact_id: UUID | None
    output_artifact_id: UUID | None
    primary_ai_decision_id: UUID | None
    qc_ai_decision_id: UUID | None
    primary_r_program: str
    qc_r_program: str
    primary_program_hash: str | None
    qc_program_hash: str | None
    comparison_result: dict | None
    created_by_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class StatisticalQCRunListResponse(BaseModel):
    items: list[StatisticalQCRunResponse]
    total: int
    page: int
    page_size: int
