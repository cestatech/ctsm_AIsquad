"""Schemas for the sponsor intake / questioning system."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.intake import IntakeStatus


class IntakeMessageResponse(BaseModel):
    id: UUID
    intake_id: UUID
    role: str
    content: str
    domain: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IntakeResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID
    created_by_id: UUID
    status: IntakeStatus
    domains_completed: list[str]
    ready_to_compile: bool
    messages: list[IntakeMessageResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IntakeRespondRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)


class StudyBriefResponse(BaseModel):
    id: UUID
    intake_id: UUID
    organization_id: UUID
    study_id: UUID
    compiled_by_id: UUID
    content: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class StartIntakeResponse(BaseModel):
    """Returned from POST /intake — includes session + first AI message."""

    intake: IntakeResponse
