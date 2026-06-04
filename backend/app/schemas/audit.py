"""Pydantic schemas for the Audit Log API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.audit import AuditAction


class AuditLogResponse(BaseModel):
    id: UUID
    organization_id: UUID | None
    actor_user_id: UUID | None
    action: AuditAction
    resource_type: str
    resource_id: UUID | None
    before_state: dict | None
    after_state: dict | None
    extra_data: dict
    ip_address: str | None
    user_agent: str | None
    session_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
