"""Context Graph models — the intelligence layer of the CIP platform.

Every entity, relationship, and event in the clinical trial lifecycle is
recorded here. The graph is the system of record for traceability,
explainability, and lineage. It never replaces domain tables — it indexes them.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.study import Study
    from app.models.user import User


class GraphNodeType(str, enum.Enum):
    """Every entity type that can appear as a node in the Context Graph."""

    # Study entities
    STUDY = "STUDY"
    PROTOCOL = "PROTOCOL"
    PROTOCOL_SECTION = "PROTOCOL_SECTION"
    OBJECTIVE = "OBJECTIVE"
    ENDPOINT = "ENDPOINT"
    ELIGIBILITY_CRITERION = "ELIGIBILITY_CRITERION"
    VISIT = "VISIT"
    ASSESSMENT = "ASSESSMENT"

    # EDC / Data Collection
    ECR_FORM = "ECR_FORM"
    ECR_FIELD = "ECR_FIELD"
    EDIT_CHECK = "EDIT_CHECK"
    RAW_DATA_FIELD = "RAW_DATA_FIELD"
    VALIDATION_RULE = "VALIDATION_RULE"

    # Uploaded file ingestion (Phase 2)
    UPLOADED_FILE = "UPLOADED_FILE"
    RAW_DATASET = "RAW_DATASET"

    # SDTM
    SDTM_DOMAIN = "SDTM_DOMAIN"
    SDTM_VARIABLE = "SDTM_VARIABLE"

    # ADaM
    ADAM_DATASET = "ADAM_DATASET"
    ADAM_VARIABLE = "ADAM_VARIABLE"

    # Outputs
    TLF = "TLF"
    TLF_CELL = "TLF_CELL"
    CSR_SECTION = "CSR_SECTION"

    # People / Governance
    USER = "USER"
    ROLE = "ROLE"
    REVIEWER = "REVIEWER"
    APPROVAL = "APPROVAL"

    # AI
    AI_AGENT = "AI_AGENT"
    AI_RECOMMENDATION = "AI_RECOMMENDATION"
    AI_DECISION = "AI_DECISION"

    # Human actions
    HUMAN_OVERRIDE = "HUMAN_OVERRIDE"

    # Validation
    VALIDATION_RUN = "VALIDATION_RUN"
    PINNACLE21_FINDING = "PINNACLE21_FINDING"

    # Synthetic data
    SYNTHETIC_DATA_RUN = "SYNTHETIC_DATA_RUN"
    SIMULATION_ASSUMPTION = "SIMULATION_ASSUMPTION"

    # External
    EXTERNAL_SOURCE = "EXTERNAL_SOURCE"
    SITE = "SITE"
    SITE_FEASIBILITY_ASSESSMENT = "SITE_FEASIBILITY_ASSESSMENT"
    PUBLICATION = "PUBLICATION"

    # Regulatory
    REGULATORY_SUBMISSION = "REGULATORY_SUBMISSION"
    SUBMISSION_PACKAGE = "SUBMISSION_PACKAGE"
    AUDIT_EVENT = "AUDIT_EVENT"

    # Generic artifact (maps to existing Artifact model)
    ARTIFACT = "ARTIFACT"

    # Intake pipeline
    INTAKE_SESSION = "INTAKE_SESSION"
    STUDY_BRIEF = "STUDY_BRIEF"


class GraphEdgeType(str, enum.Enum):
    """Every relationship type between graph nodes."""

    CREATED_BY = "CREATED_BY"
    UPDATED_BY = "UPDATED_BY"
    REVIEWED_BY = "REVIEWED_BY"
    APPROVED_BY = "APPROVED_BY"
    REJECTED_BY = "REJECTED_BY"

    DERIVED_FROM = "DERIVED_FROM"
    GENERATED_FROM = "GENERATED_FROM"
    MAPS_TO = "MAPS_TO"
    VALIDATES = "VALIDATES"
    FAILS_VALIDATION = "FAILS_VALIDATION"
    FIXED_BY = "FIXED_BY"

    SUPPORTS = "SUPPORTS"
    CITED_IN = "CITED_IN"
    USED_IN = "USED_IN"
    DEPENDS_ON = "DEPENDS_ON"

    SUPERSEDES = "SUPERSEDES"
    AMENDS = "AMENDS"

    ACCEPTED_BY = "ACCEPTED_BY"
    OVERRIDDEN_BY = "OVERRIDDEN_BY"

    EXPLAINS = "EXPLAINS"
    CROSS_CHECKED_BY = "CROSS_CHECKED_BY"

    # Lineage chain links
    OBJECTIVE_TO_ENDPOINT = "OBJECTIVE_TO_ENDPOINT"
    ENDPOINT_TO_ECR = "ENDPOINT_TO_ECR"
    ECR_TO_SDTM = "ECR_TO_SDTM"
    SDTM_TO_ADAM = "SDTM_TO_ADAM"
    ADAM_TO_TLF = "ADAM_TO_TLF"
    TLF_TO_CSR = "TLF_TO_CSR"

    PART_OF = "PART_OF"
    HAS_MEMBER = "HAS_MEMBER"
    INCLUDES = "INCLUDES"


class GraphNode(UUIDMixin, Base):
    """
    A node in the Context Graph. Represents any entity in the clinical
    trial lifecycle. Nodes are lightweight index entries that point back
    to the canonical record in the domain tables via external_id.
    """

    __tablename__ = "graph_nodes"

    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    study_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("studies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    node_type: Mapped[GraphNodeType] = mapped_column(
        Enum(GraphNodeType, name="graph_node_type"),
        nullable=False,
        index=True,
    )

    # Reference back to the canonical domain record
    external_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True, index=True
    )
    external_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    label: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_by_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", foreign_keys=[organization_id], lazy="raise"
    )
    study: Mapped["Study | None"] = relationship(
        "Study", foreign_keys=[study_id], lazy="raise"
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_id], lazy="raise"
    )
    outgoing_edges: Mapped[list["GraphEdge"]] = relationship(
        "GraphEdge",
        foreign_keys="GraphEdge.source_node_id",
        back_populates="source_node",
        lazy="raise",
    )
    incoming_edges: Mapped[list["GraphEdge"]] = relationship(
        "GraphEdge",
        foreign_keys="GraphEdge.target_node_id",
        back_populates="target_node",
        lazy="raise",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "study_id": self.study_id,
            "node_type": self.node_type.value if self.node_type else None,
            "external_id": self.external_id,
            "external_type": self.external_type,
            "label": self.label,
            "description": self.description,
            "properties": self.properties,
            "is_active": self.is_active,
            "created_by_id": self.created_by_id,
            "created_at": self.created_at.isoformat()
            if hasattr(self.created_at, "isoformat")
            else str(self.created_at),
        }


class GraphEdge(UUIDMixin, Base):
    """
    A directed edge in the Context Graph. Represents a relationship between
    two nodes. Edges can be human-created or AI-generated (with a confidence score).
    AI-generated edges reference the AIDecision that produced them.
    """

    __tablename__ = "graph_edges"

    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    study_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("studies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source_node_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    edge_type: Mapped[GraphEdgeType] = mapped_column(
        Enum(GraphEdgeType, name="graph_edge_type"),
        nullable=False,
        index=True,
    )

    label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Provenance
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    is_ai_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # References the AI decision that produced this edge (if AI-generated)
    ai_decision_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ai_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_by_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    source_node: Mapped["GraphNode"] = relationship(
        "GraphNode",
        foreign_keys=[source_node_id],
        back_populates="outgoing_edges",
        lazy="raise",
    )
    target_node: Mapped["GraphNode"] = relationship(
        "GraphNode",
        foreign_keys=[target_node_id],
        back_populates="incoming_edges",
        lazy="raise",
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_id], lazy="raise"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "edge_type": self.edge_type.value if self.edge_type else None,
            "label": self.label,
            "properties": self.properties,
            "confidence": self.confidence,
            "is_ai_generated": self.is_ai_generated,
            "ai_decision_id": self.ai_decision_id,
            "created_at": self.created_at.isoformat()
            if hasattr(self.created_at, "isoformat")
            else str(self.created_at),
        }


class GraphEvent(UUIDMixin, Base):
    """
    Append-only log of every mutation to the Context Graph.
    Provides a time-ordered audit trail of how the graph evolved.
    """

    __tablename__ = "graph_events"

    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    study_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("studies.id", ondelete="SET NULL"),
        nullable=True,
    )

    # What changed
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    node_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("graph_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    edge_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("graph_edges.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Who did it
    actor_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_agent_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )  # AI agent name, e.g. "sdtm-agent"

    # Direct FK to the AI decision that caused this event (if AI-generated).
    # Enables "show all graph changes caused by decision X" queries.
    ai_decision_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ai_decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Phase 3: deduplicate mandatory workflow events on retry
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )

    # Immutable — no updated_at
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
