"""Schemas for the sponsor intake / questioning system."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.intake import IntakeStatus, SponsorIntake


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

    @model_validator(mode="before")
    @classmethod
    def filter_hidden_messages(cls, data: object) -> object:
        """Exclude hidden trigger messages without mutating ORM relationships."""
        if isinstance(data, SponsorIntake):
            visible = [m for m in data.messages if not m.is_hidden]
            return {
                "id": data.id,
                "organization_id": data.organization_id,
                "study_id": data.study_id,
                "created_by_id": data.created_by_id,
                "status": data.status,
                "domains_completed": data.domains_completed,
                "ready_to_compile": data.ready_to_compile,
                "messages": visible,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        return data


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
