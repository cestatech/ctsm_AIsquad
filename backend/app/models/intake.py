"""Sponsor intake models — conversational AI-driven study information gathering.

SponsorIntake tracks a session, IntakeMessage stores conversation turns,
and StudyBrief holds the compiled structured output that drives generation.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class IntakeStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    READY_TO_COMPILE = "READY_TO_COMPILE"
    COMPILED = "COMPILED"


class IntakeDomain(str, enum.Enum):
    STUDY_OVERVIEW = "STUDY_OVERVIEW"
    STUDY_DESIGN = "STUDY_DESIGN"
    POPULATION = "POPULATION"
    ENDPOINTS = "ENDPOINTS"
    DRUG_TREATMENT = "DRUG_TREATMENT"
    SAFETY = "SAFETY"
    REGULATORY = "REGULATORY"
    STATISTICAL = "STATISTICAL"
    SITES = "SITES"


ALL_DOMAINS = [d.value for d in IntakeDomain]


class SponsorIntake(UUIDMixin, TimestampMixin, Base):
    """
    An intake session for a study.

    One active session per study at a time. Status moves from IN_PROGRESS →
    READY_TO_COMPILE once Claude signals all domains are covered, then → COMPILED
    when the Study Brief is generated.
    """

    __tablename__ = "sponsor_intakes"

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
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    status: Mapped[IntakeStatus] = mapped_column(
        Enum(IntakeStatus, name="intake_status"),
        nullable=False,
        default=IntakeStatus.IN_PROGRESS,
    )
    domains_completed: Mapped[list] = mapped_column(
        ARRAY(String(50)), nullable=False, default=list
    )
    ready_to_compile: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    messages: Mapped[list["IntakeMessage"]] = relationship(
        "IntakeMessage",
        back_populates="intake",
        order_by="IntakeMessage.created_at",
    )
    brief: Mapped["StudyBrief | None"] = relationship(
        "StudyBrief", back_populates="intake", uselist=False
    )


class IntakeMessage(UUIDMixin, TimestampMixin, Base):
    """
    A single conversational turn in a sponsor intake session.

    is_hidden=True marks internal trigger messages that are sent to Claude
    but not displayed to the user.
    """

    __tablename__ = "intake_messages"

    intake_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sponsor_intakes.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    intake: Mapped["SponsorIntake"] = relationship(
        "SponsorIntake", back_populates="messages"
    )


class StudyBrief(UUIDMixin, TimestampMixin, Base):
    """
    Compiled structured Study Brief produced at the end of an intake session.

    This JSON document is the single source of truth that drives Protocol,
    ICF, SAP, and all downstream generation. One brief per intake session.
    """

    __tablename__ = "study_briefs"
    __table_args__ = (UniqueConstraint("intake_id", name="uq_study_briefs_intake"),)

    intake_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sponsor_intakes.id", ondelete="CASCADE"),
        nullable=False,
    )
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
    compiled_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)

    intake: Mapped["SponsorIntake"] = relationship(
        "SponsorIntake", back_populates="brief"
    )
