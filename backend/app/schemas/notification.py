"""Pydantic schemas for the Notification resource."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.notification import NotificationType


class NotificationResponse(BaseModel):
    """Single notification returned by the API."""

    id: UUID
    organization_id: UUID
    recipient_id: UUID
    type: NotificationType
    title: str
    body: str
    resource_type: str | None
    resource_id: UUID | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
