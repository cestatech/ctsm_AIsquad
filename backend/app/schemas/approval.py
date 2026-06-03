"""Pydantic schemas for the Approval resource."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.approval import ApprovalDecision
from app.models.artifact import ArtifactType


class CreatorBrief(BaseModel):
    id: UUID
    full_name: str
    email: str

    model_config = {"from_attributes": True}


class ApprovalQueueItem(BaseModel):
    """One artifact awaiting review in the approval queue."""

    artifact_id: UUID
    artifact_version_id: UUID | None
    artifact_name: str
    artifact_type: ArtifactType
    study_id: UUID
    study_name: str
    protocol_number: str
    version_number: int
    submitted_by: CreatorBrief
    submitted_at: datetime


class ApprovalQueueResponse(BaseModel):
    items: list[ApprovalQueueItem]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class CreateApprovalRequest(BaseModel):
    """Request body for submitting an approval decision."""

    artifact_id: UUID
    artifact_version_id: UUID
    decision: ApprovalDecision
    comments: str | None = None


class ApprovalResponse(BaseModel):
    id: UUID
    artifact_id: UUID
    artifact_version_id: UUID
    approver_id: UUID
    decision: ApprovalDecision
    comments: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
