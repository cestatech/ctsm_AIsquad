"""Pydantic schemas for the Comments API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    artifact_id: UUID
    artifact_version_id: UUID | None = None
    parent_id: UUID | None = None
    body: str = Field(min_length=1, max_length=10000)


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class CommentAuthor(BaseModel):
    id: UUID
    full_name: str
    email: str

    model_config = {"from_attributes": True}


class CommentResponse(BaseModel):
    id: UUID
    organization_id: UUID
    artifact_id: UUID
    artifact_version_id: UUID | None
    parent_id: UUID | None
    author_id: UUID
    author: CommentAuthor
    body: str
    is_resolved: bool
    resolved_at: datetime | None
    resolved_by_id: UUID | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommentListResponse(BaseModel):
    items: list[CommentResponse]
    total: int
