from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.artifact import Artifact, ArtifactVersion
    from app.models.user import User


class Comment(UUIDMixin, TimestampMixin, Base):
    """
    Review comment on an artifact. Supports threaded replies via parent_id.

    Resolved comments are preserved — do not hard-delete.
    Soft-delete via is_deleted flag.
    """

    __tablename__ = "comments"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifact_versions.id"),
        nullable=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comments.id"),
        nullable=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_at = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at = mapped_column(DateTime(timezone=True), nullable=True)

    artifact: Mapped["Artifact"] = relationship("Artifact", back_populates="comments")
    artifact_version: Mapped["ArtifactVersion | None"] = relationship("ArtifactVersion")
    author: Mapped["User"] = relationship("User", foreign_keys=[author_id])
    resolver: Mapped["User | None"] = relationship(
        "User", foreign_keys=[resolved_by_id]
    )
    replies: Mapped[list["Comment"]] = relationship(
        "Comment", foreign_keys=[parent_id], back_populates="parent"
    )
    parent: Mapped["Comment | None"] = relationship(
        "Comment",
        foreign_keys=[parent_id],
        back_populates="replies",
        remote_side="Comment.id",
    )
