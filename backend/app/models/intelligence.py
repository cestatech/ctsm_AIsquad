"""Intelligence layer models — AI decisions, human overrides, lineage, and validation evidence.

These models provide complete explainability and traceability for every AI action
and human intervention in the clinical trial lifecycle. Every AI output has a
corresponding AIDecision record; every human correction has a HumanOverride record.
Neither is ever deleted or modified.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.study import Study
    from app.models.user import User


# ---------------------------------------------------------------------------
# AI Decision (Phase 2)
# ---------------------------------------------------------------------------


class AIDecisionStatus(str, enum.Enum):
    """Lifecycle of an AI decision from generation through human review."""

    PENDING_REVIEW = "PENDING_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    OVERRIDDEN = "OVERRIDDEN"
    SUPERSEDED = "SUPERSEDED"


class AIDecision(UUIDMixin, Base):
    """
    Immutable record of every decision made by an AI agent.

    Every automated action — mapping, generation, recommendation, classification —
    produces exactly one AIDecision record before any downstream effect is written.
    The record captures the full provenance chain: which agent ran, against which
    inputs, with what reasoning, at what confidence, and what was produced.

    Relationships:
        - organization: tenant scope
        - study: optional study context
        - reviewer: human who accepted/rejected this decision
        - human_override: override record if the decision was overridden
    """

    __tablename__ = "ai_decisions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    study_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Which AI agent produced this (e.g. "sdtm-agent", "protocol-agent")
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    agent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # What the agent was doing
    decision_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    module: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Model provenance
    model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Input / output artifacts referenced
    input_artifact_ids: Mapped[list | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    output_artifact_ids: Mapped[list | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )

    # The structured decision payload
    input_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Traceability — graph node this decision produced/affected
    graph_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Review lifecycle
    status: Mapped[AIDecisionStatus] = mapped_column(
        Enum(AIDecisionStatus, name="ai_decision_status"),
        nullable=False,
        default=AIDecisionStatus.PENDING_REVIEW,
        index=True,
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Immutable timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    # NO updated_at — append-only record

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", foreign_keys=[organization_id], lazy="raise"
    )
    study: Mapped["Study | None"] = relationship(
        "Study", foreign_keys=[study_id], lazy="raise"
    )
    reviewed_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[reviewed_by_id], lazy="raise"
    )
    human_overrides: Mapped[list["HumanOverride"]] = relationship(
        "HumanOverride",
        foreign_keys="HumanOverride.ai_decision_id",
        back_populates="ai_decision",
        lazy="raise",
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "study_id": str(self.study_id) if self.study_id else None,
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "decision_type": self.decision_type,
            "module": self.module,
            "model_id": self.model_id,
            "model_provider": self.model_provider,
            "prompt_hash": self.prompt_hash,
            "confidence": self.confidence,
            "input_context": self.input_context,
            "reasoning": self.reasoning,
            "output": self.output,
            "status": self.status.value if self.status else None,
            "reviewed_by_id": str(self.reviewed_by_id) if self.reviewed_by_id else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_notes": self.review_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Human Override (Phase 3)
# ---------------------------------------------------------------------------


class HumanOverride(UUIDMixin, Base):
    """
    Immutable record of every human correction or override of an AI decision.

    When a human changes a value that was AI-generated, or rejects an AI
    recommendation, a HumanOverride record is created capturing exactly what
    was changed, why, and by whom. This enables the "explain why you changed
    this" audit trail required for regulatory submissions.

    Relationships:
        - organization: tenant scope
        - study: optional study context
        - ai_decision: the AI decision being overridden
        - actor: the human who made the override
        - graph_node: the graph node affected
    """

    __tablename__ = "human_overrides"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    study_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # The AI decision being overridden (nullable — overrides can exist without AI origin)
    ai_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Context: what was being overridden
    context_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    field_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # The actual change
    original_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Mandatory justification
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    override_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Graph traceability
    graph_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Who did it
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Immutable — no updated_at
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", foreign_keys=[organization_id], lazy="raise"
    )
    study: Mapped["Study | None"] = relationship(
        "Study", foreign_keys=[study_id], lazy="raise"
    )
    ai_decision: Mapped["AIDecision | None"] = relationship(
        "AIDecision",
        foreign_keys=[ai_decision_id],
        back_populates="human_overrides",
        lazy="raise",
    )
    actor: Mapped["User"] = relationship(
        "User", foreign_keys=[actor_user_id], lazy="raise"
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "study_id": str(self.study_id) if self.study_id else None,
            "ai_decision_id": str(self.ai_decision_id) if self.ai_decision_id else None,
            "context_type": self.context_type,
            "context_id": str(self.context_id) if self.context_id else None,
            "field_path": self.field_path,
            "original_value": self.original_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "override_type": self.override_type,
            "actor_user_id": str(self.actor_user_id),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Data Lineage (Phase 4)
# ---------------------------------------------------------------------------


class DataLineageType(str, enum.Enum):
    """The type of lineage relationship between two data artifacts."""

    DERIVED = "DERIVED"
    MAPPED = "MAPPED"
    AGGREGATED = "AGGREGATED"
    TRANSFORMED = "TRANSFORMED"
    VALIDATED = "VALIDATED"
    GENERATED = "GENERATED"
    MERGED = "MERGED"
    FILTERED = "FILTERED"
    IMPUTED = "IMPUTED"


class DataLineage(UUIDMixin, Base):
    """
    Records a lineage relationship between two data items at the field/variable level.

    Captures how a downstream variable was produced from upstream sources,
    including the transformation logic, the agent/user responsible, and any
    associated AI decision. Enables the "show your work" trace from raw data
    through SDTM, ADaM, and TLF to CSR.

    Relationships:
        - organization / study: scope
        - ai_decision: if this lineage was AI-created
        - actor: if this lineage was human-created
    """

    __tablename__ = "data_lineage"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    study_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    lineage_type: Mapped[DataLineageType] = mapped_column(
        Enum(DataLineageType, name="data_lineage_type"),
        nullable=False,
        index=True,
    )

    # Source: the upstream data entity
    source_type: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    source_field: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_domain: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Target: the downstream data entity
    target_type: Mapped[str] = mapped_column(String(128), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    target_field: Mapped[str | None] = mapped_column(String(256), nullable=True)
    target_domain: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Transformation description
    transformation_logic: Mapped[str | None] = mapped_column(Text, nullable=True)
    transformation_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    assumptions: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Provenance
    is_ai_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    ai_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Graph traceability
    source_graph_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_graph_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
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
    ai_decision: Mapped["AIDecision | None"] = relationship(
        "AIDecision", foreign_keys=[ai_decision_id], lazy="raise"
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_id], lazy="raise"
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "study_id": str(self.study_id) if self.study_id else None,
            "lineage_type": self.lineage_type.value if self.lineage_type else None,
            "source_type": self.source_type,
            "source_id": str(self.source_id) if self.source_id else None,
            "source_field": self.source_field,
            "source_domain": self.source_domain,
            "target_type": self.target_type,
            "target_id": str(self.target_id) if self.target_id else None,
            "target_field": self.target_field,
            "target_domain": self.target_domain,
            "transformation_logic": self.transformation_logic,
            "is_ai_generated": self.is_ai_generated,
            "ai_decision_id": str(self.ai_decision_id) if self.ai_decision_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ArtifactLineage(UUIDMixin, Base):
    """
    Records the document-level lineage chain: which artifact was used to produce another.

    Captures the full chain from Protocol → SAP → ADaM Spec → ADaM Dataset → TLF → CSR.
    Each link records the contributing artifact, the derivation method, and any
    AI decision that automated the link.
    """

    __tablename__ = "artifact_lineage"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    study_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifact_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifact_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False)
    derivation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_ai_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    ai_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    organization: Mapped["Organization"] = relationship(
        "Organization", foreign_keys=[organization_id], lazy="raise"
    )
    study: Mapped["Study | None"] = relationship(
        "Study", foreign_keys=[study_id], lazy="raise"
    )


# ---------------------------------------------------------------------------
# Validation Evidence (Phase 5)
# ---------------------------------------------------------------------------


class ValidationEvidenceStatus(str, enum.Enum):
    PENDING = "PENDING"
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    WAIVED = "WAIVED"


class ValidationEvidence(UUIDMixin, Base):
    """
    Structured evidence record for a single validation check or finding.

    Ties a validation result to the specific data element, CDISC conformance rule,
    or business rule that was checked. Provides the evidence chain needed for a
    regulatory submission's data quality appendix.

    Relationships:
        - organization / study: scope
        - validation_run: the run that produced this evidence
        - ai_decision: if AI evaluated/corrected this finding
        - human_override: if a human waived or corrected this finding
    """

    __tablename__ = "validation_evidence"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    study_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    validation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # The rule / check being evidenced
    rule_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    rule_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    rule_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cdisc_standard: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # What was checked
    subject_type: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    subject_field: Mapped[str | None] = mapped_column(String(256), nullable=True)
    subject_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # The result
    status: Mapped[ValidationEvidenceStatus] = mapped_column(
        Enum(ValidationEvidenceStatus, name="validation_evidence_status"),
        nullable=False,
        index=True,
    )
    finding_severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    finding_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    finding_details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Provenance
    is_ai_evaluated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    ai_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Human waiver
    waived_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    waiver_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    waived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Graph traceability
    graph_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Validation engine that produced this evidence (INTERNAL, PINNACLE21, etc.)
    source: Mapped[str] = mapped_column(
        String(64), nullable=False, default="INTERNAL", server_default="INTERNAL"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
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
    ai_decision: Mapped["AIDecision | None"] = relationship(
        "AIDecision", foreign_keys=[ai_decision_id], lazy="raise"
    )
    waived_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[waived_by_id], lazy="raise"
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "study_id": str(self.study_id) if self.study_id else None,
            "validation_run_id": str(self.validation_run_id)
            if self.validation_run_id
            else None,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "rule_category": self.rule_category,
            "cdisc_standard": self.cdisc_standard,
            "subject_type": self.subject_type,
            "subject_field": self.subject_field,
            "status": self.status.value if self.status else None,
            "finding_severity": self.finding_severity,
            "finding_message": self.finding_message,
            "finding_details": self.finding_details,
            "is_ai_evaluated": self.is_ai_evaluated,
            "ai_decision_id": str(self.ai_decision_id) if self.ai_decision_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Synthetic Data (Phase 5 supplement)
# ---------------------------------------------------------------------------


class SyntheticDataRun(UUIDMixin, Base):
    """
    Records a synthetic patient data generation run.

    Captures the configuration, assumptions, and output of each synthetic data
    generation exercise for auditability and reproducibility. Every assumption
    used in the simulation is stored separately in SimulationAssumption records.
    """

    __tablename__ = "synthetic_data_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    run_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Configuration
    target_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_domains: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    configuration: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    random_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING", index=True
    )
    records_generated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI provenance
    ai_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Output artifact
    output_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Graph node
    graph_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", foreign_keys=[organization_id], lazy="raise"
    )
    study: Mapped["Study"] = relationship(
        "Study", foreign_keys=[study_id], lazy="raise"
    )
    assumptions: Mapped[list["SimulationAssumption"]] = relationship(
        "SimulationAssumption",
        back_populates="run",
        lazy="raise",
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_id], lazy="raise"
    )


class SimulationAssumption(UUIDMixin, Base):
    """
    A single documented assumption made during a synthetic data run.

    Every distributional assumption, imputation rule, or biological constraint
    used to generate synthetic data is recorded here. This enables complete
    reproducibility and regulatory defensibility of synthetic datasets.
    """

    __tablename__ = "simulation_assumptions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("synthetic_data_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    assumption_type: Mapped[str] = mapped_column(String(128), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(64), nullable=True)
    variable: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run: Mapped["SyntheticDataRun"] = relationship(
        "SyntheticDataRun", back_populates="assumptions", lazy="raise"
    )
    organization: Mapped["Organization"] = relationship(
        "Organization", foreign_keys=[organization_id], lazy="raise"
    )


# ---------------------------------------------------------------------------
# External Source
# ---------------------------------------------------------------------------


class ExternalSource(UUIDMixin, Base):
    """
    Records an external reference used to inform or validate a clinical trial decision.

    Examples: published literature, regulatory guidance, historical trial data,
    biomarker databases, or sponsor SOPs. Every AI decision that references
    external evidence must create an ExternalSource record and link to it via the graph.
    """

    __tablename__ = "external_sources"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    authors: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pmid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_findings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    relevance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    graph_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization: Mapped["Organization"] = relationship(
        "Organization", foreign_keys=[organization_id], lazy="raise"
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_id], lazy="raise"
    )
