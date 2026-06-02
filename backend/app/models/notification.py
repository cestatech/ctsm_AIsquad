from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class NotificationType(str, enum.Enum):
    ARTIFACT_SUBMITTED = "ARTIFACT_SUBMITTED"
    ARTIFACT_APPROVED = "ARTIFACT_APPROVED"
    ARTIFACT_REJECTED = "ARTIFACT_REJECTED"
    ARTIFACT_LOCKED = "ARTIFACT_LOCKED"
    COMMENT_ADDED = "COMMENT_ADDED"
    MENTION = "MENTION"
    VALIDATION_COMPLETE = "VALIDATION_COMPLETE"


class Notification(UUIDMixin, Base):
    """
    In-platform notification for a user.

    Notifications are user-facing convenience — they do NOT replace audit logs.
    Notifications may be deleted; audit logs are permanent.
    """

    __tablename__ = "notifications"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    recipient: Mapped["User"] = relationship("User")
