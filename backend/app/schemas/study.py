"""Pydantic schemas for Studies and StudyMembers API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.study import StudyPhase, StudyStatus


class StudyCreate(BaseModel):
    protocol_number: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=500)
    short_name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    indication: str | None = Field(default=None, max_length=500)
    therapeutic_area: str | None = Field(default=None, max_length=255)
    phase: StudyPhase | None = None
    sponsor: str | None = Field(default=None, max_length=255)
    regulatory_region: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("regulatory_region")
    @classmethod
    def validate_regions(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) > 20:
            raise ValueError("regulatory_region may not exceed 20 entries")
        return v


class StudyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    short_name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    indication: str | None = Field(default=None, max_length=500)
    therapeutic_area: str | None = Field(default=None, max_length=255)
    phase: StudyPhase | None = None
    sponsor: str | None = Field(default=None, max_length=255)
    regulatory_region: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None


class UserBrief(BaseModel):
    id: UUID
    full_name: str
    email: str
    title: str | None

    model_config = {"from_attributes": True}


class StudyMemberResponse(BaseModel):
    id: UUID
    study_id: UUID
    user_id: UUID
    organization_id: UUID
    role: str
    user: UserBrief
    invited_by_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StudyResponse(BaseModel):
    id: UUID
    organization_id: UUID
    protocol_number: str
    name: str
    short_name: str | None
    description: str | None
    indication: str | None
    therapeutic_area: str | None
    phase: StudyPhase | None
    status: StudyStatus
    sponsor: str | None
    regulatory_region: list[str] | None
    start_date: date | None
    end_date: date | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StudyListResponse(BaseModel):
    items: list[StudyResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class AddMemberRequest(BaseModel):
    user_id: UUID
    role: str = Field(pattern="^(ADMIN|CONTRIBUTOR|REVIEWER)$")


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(pattern="^(ADMIN|CONTRIBUTOR|REVIEWER)$")
