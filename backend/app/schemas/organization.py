"""Pydantic schemas for the Organizations API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OrgSettingsUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    logo_url: str | None = None
    settings: dict | None = None


class OrgResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    logo_url: str | None
    settings: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
