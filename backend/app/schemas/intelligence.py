"""Pydantic schemas for AI Decision, Human Override, Lineage, and Validation Evidence APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.intelligence import (
    AIDecisionStatus,
    DataLineageType,
    ValidationEvidenceStatus,
)


# ---------------------------------------------------------------------------
# AI Decision schemas
# ---------------------------------------------------------------------------


class AIDecisionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID | None
    agent_name: str
    agent_version: str | None
    decision_type: str
    module: str | None
    model_id: str | None
    model_provider: str | None
    prompt_hash: str | None
    confidence: float | None
    input_context: dict
    reasoning: str | None
    output: dict
    status: AIDecisionStatus
    reviewed_by_id: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class AIDecisionListResponse(BaseModel):
    items: list[AIDecisionResponse]
    total: int
    page: int
    page_size: int


class ReviewDecisionRequest(BaseModel):
    notes: str | None = None


class RejectDecisionRequest(BaseModel):
    notes: str = Field(min_length=1, description="Required justification for rejection")


# ---------------------------------------------------------------------------
# Human Override schemas
# ---------------------------------------------------------------------------


class HumanOverrideResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID | None
    ai_decision_id: UUID | None
    context_type: str
    context_id: UUID | None
    field_path: str | None
    original_value: dict | None
    new_value: dict | None
    reason: str
    override_type: str
    actor_user_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class HumanOverrideListResponse(BaseModel):
    items: list[HumanOverrideResponse]
    total: int
    page: int
    page_size: int


class CreateOverrideRequest(BaseModel):
    context_type: str = Field(max_length=128)
    override_type: str = Field(max_length=64)
    reason: str = Field(min_length=1)
    study_id: UUID | None = None
    ai_decision_id: UUID | None = None
    context_id: UUID | None = None
    field_path: str | None = Field(None, max_length=512)
    original_value: dict | None = None
    new_value: dict | None = None
    graph_node_id: UUID | None = None


# ---------------------------------------------------------------------------
# Data Lineage schemas
# ---------------------------------------------------------------------------


class DataLineageResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID | None
    lineage_type: DataLineageType
    source_type: str
    source_id: UUID | None
    source_field: str | None
    source_domain: str | None
    target_type: str
    target_id: UUID | None
    target_field: str | None
    target_domain: str | None
    transformation_logic: str | None
    is_ai_generated: bool
    ai_decision_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ArtifactLineageResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID | None
    source_artifact_id: UUID
    source_version_id: UUID | None
    target_artifact_id: UUID
    target_version_id: UUID | None
    relationship_type: str
    derivation_notes: str | None
    is_ai_generated: bool
    ai_decision_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LineageChainResponse(BaseModel):
    upstream: list[DataLineageResponse]
    downstream: list[DataLineageResponse]


# ---------------------------------------------------------------------------
# Validation Evidence schemas
# ---------------------------------------------------------------------------


class ValidationEvidenceResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID | None
    validation_run_id: UUID | None
    rule_id: str | None
    rule_name: str | None
    rule_category: str | None
    cdisc_standard: str | None
    subject_type: str
    subject_field: str | None
    status: ValidationEvidenceStatus
    finding_severity: str | None
    finding_message: str | None
    finding_details: dict
    source: str = "INTERNAL"
    is_ai_evaluated: bool
    ai_decision_id: UUID | None
    waived_by_id: UUID | None
    waiver_reason: str | None
    waived_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ValidationEvidenceListResponse(BaseModel):
    items: list[ValidationEvidenceResponse]
    total: int
    page: int
    page_size: int


class WaiveFindingRequest(BaseModel):
    reason: str = Field(
        min_length=1, description="Required justification for the waiver"
    )


# ---------------------------------------------------------------------------
# Synthetic Data schemas
# ---------------------------------------------------------------------------


class SyntheticDataRunResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID
    run_name: str
    description: str | None
    target_n: int | None
    configuration: dict
    random_seed: int | None
    status: str
    records_generated: int | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    ai_decision_id: UUID | None
    output_artifact_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SyntheticDataRunListResponse(BaseModel):
    items: list[SyntheticDataRunResponse]
    total: int
    page: int
    page_size: int
