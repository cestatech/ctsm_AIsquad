from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.artifact import Artifact
    from app.models.user import User


class TraceabilityLink(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """
    Traceability chain link.

    Captures the regulatory traceability requirement:
    Objective → Endpoint → eCRF → SDTM → ADaM → TLF → CSR

    Each link connects a specific element in a source artifact to a specific
    element in a target artifact, with a typed relationship.

    link_type values: 'derives_from', 'implements', 'validates', 'references'
    """

    __tablename__ = "traceability_links"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studies.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id"),
        nullable=False,
    )
    source_element_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    target_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id"),
        nullable=False,
    )
    target_element_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    source_artifact: Mapped["Artifact"] = relationship(
        "Artifact", foreign_keys=[source_artifact_id]
    )
    target_artifact: Mapped["Artifact"] = relationship(
        "Artifact", foreign_keys=[target_artifact_id]
    )
    created_by: Mapped["User"] = relationship("User")
