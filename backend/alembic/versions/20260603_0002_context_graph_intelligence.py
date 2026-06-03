"""Add Context Graph, AI Decision, Human Override, Lineage, and Validation Intelligence tables.

These tables form the Celerius Intelligence Platform (CIP) layer — the explainability
and traceability substrate for every AI action and human intervention in the
clinical trial lifecycle.

New tables:
  graph_nodes, graph_edges, graph_events
  ai_decisions, human_overrides
  data_lineage, artifact_lineage
  validation_evidence
  synthetic_data_runs, simulation_assumptions
  external_sources

New enums:
  graph_node_type, graph_edge_type
  ai_decision_status
  data_lineage_type
  validation_evidence_status

Revision ID: c2d3e4f5a6b7
Revises: b1a2c3d4e5f6
Create Date: 2026-06-03 00:01:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1a2c3d4e5f6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enums
    # ------------------------------------------------------------------
    graph_node_type = postgresql.ENUM(
        "STUDY", "PROTOCOL", "PROTOCOL_SECTION", "OBJECTIVE", "ENDPOINT",
        "ELIGIBILITY_CRITERION", "VISIT", "ASSESSMENT",
        "ECR_FORM", "ECR_FIELD", "EDIT_CHECK", "RAW_DATA_FIELD", "VALIDATION_RULE",
        "SDTM_DOMAIN", "SDTM_VARIABLE",
        "ADAM_DATASET", "ADAM_VARIABLE",
        "TLF", "TLF_CELL", "CSR_SECTION",
        "USER", "ROLE", "REVIEWER", "APPROVAL",
        "AI_AGENT", "AI_RECOMMENDATION", "AI_DECISION",
        "HUMAN_OVERRIDE",
        "VALIDATION_RUN", "PINNACLE21_FINDING",
        "SYNTHETIC_DATA_RUN", "SIMULATION_ASSUMPTION",
        "EXTERNAL_SOURCE", "SITE", "SITE_FEASIBILITY_ASSESSMENT", "PUBLICATION",
        "REGULATORY_SUBMISSION", "AUDIT_EVENT",
        "ARTIFACT",
        name="graph_node_type",
        create_type=True,
    )
    graph_node_type.create(op.get_bind(), checkfirst=True)

    graph_edge_type = postgresql.ENUM(
        "CREATED_BY", "UPDATED_BY", "REVIEWED_BY", "APPROVED_BY", "REJECTED_BY",
        "DERIVED_FROM", "GENERATED_FROM", "MAPS_TO", "VALIDATES", "FAILS_VALIDATION",
        "FIXED_BY", "SUPPORTS", "CITED_IN", "USED_IN", "DEPENDS_ON",
        "SUPERSEDES", "AMENDS", "ACCEPTED_BY", "OVERRIDDEN_BY",
        "EXPLAINS", "CROSS_CHECKED_BY",
        "OBJECTIVE_TO_ENDPOINT", "ENDPOINT_TO_ECR", "ECR_TO_SDTM",
        "SDTM_TO_ADAM", "ADAM_TO_TLF", "TLF_TO_CSR",
        "PART_OF", "HAS_MEMBER",
        name="graph_edge_type",
        create_type=True,
    )
    graph_edge_type.create(op.get_bind(), checkfirst=True)

    ai_decision_status = postgresql.ENUM(
        "PENDING_REVIEW", "ACCEPTED", "REJECTED", "OVERRIDDEN", "SUPERSEDED",
        name="ai_decision_status",
        create_type=True,
    )
    ai_decision_status.create(op.get_bind(), checkfirst=True)

    data_lineage_type = postgresql.ENUM(
        "DERIVED", "MAPPED", "AGGREGATED", "TRANSFORMED", "VALIDATED",
        "GENERATED", "MERGED", "FILTERED", "IMPUTED",
        name="data_lineage_type",
        create_type=True,
    )
    data_lineage_type.create(op.get_bind(), checkfirst=True)

    validation_evidence_status = postgresql.ENUM(
        "PENDING", "PASS", "FAIL", "WARNING", "WAIVED",
        name="validation_evidence_status",
        create_type=True,
    )
    validation_evidence_status.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # graph_nodes
    # ------------------------------------------------------------------
    op.create_table(
        "graph_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("study_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("studies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("node_type", sa.Enum("STUDY", "PROTOCOL", "PROTOCOL_SECTION",
                  "OBJECTIVE", "ENDPOINT", "ELIGIBILITY_CRITERION", "VISIT",
                  "ASSESSMENT", "ECR_FORM", "ECR_FIELD", "EDIT_CHECK",
                  "RAW_DATA_FIELD", "VALIDATION_RULE", "SDTM_DOMAIN",
                  "SDTM_VARIABLE", "ADAM_DATASET", "ADAM_VARIABLE", "TLF",
                  "TLF_CELL", "CSR_SECTION", "USER", "ROLE", "REVIEWER",
                  "APPROVAL", "AI_AGENT", "AI_RECOMMENDATION", "AI_DECISION",
                  "HUMAN_OVERRIDE", "VALIDATION_RUN", "PINNACLE21_FINDING",
                  "SYNTHETIC_DATA_RUN", "SIMULATION_ASSUMPTION",
                  "EXTERNAL_SOURCE", "SITE", "SITE_FEASIBILITY_ASSESSMENT",
                  "PUBLICATION", "REGULATORY_SUBMISSION", "AUDIT_EVENT",
                  "ARTIFACT", name="graph_node_type", create_constraint=False),
                  nullable=False),
        sa.Column("external_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_type", sa.String(64), nullable=True),
        sa.Column("label", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("properties", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_graph_nodes_organization_id", "graph_nodes", ["organization_id"])
    op.create_index("ix_graph_nodes_study_id", "graph_nodes", ["study_id"])
    op.create_index("ix_graph_nodes_node_type", "graph_nodes", ["node_type"])
    op.create_index("ix_graph_nodes_external_id", "graph_nodes", ["external_id"])

    # ------------------------------------------------------------------
    # ai_decisions  (created before graph_edges — graph_edges FK → ai_decisions)
    # ------------------------------------------------------------------
    op.create_table(
        "ai_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("study_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("studies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_name", sa.String(128), nullable=False),
        sa.Column("agent_version", sa.String(64), nullable=True),
        sa.Column("decision_type", sa.String(128), nullable=False),
        sa.Column("module", sa.String(128), nullable=True),
        sa.Column("model_id", sa.String(128), nullable=True),
        sa.Column("model_provider", sa.String(64), nullable=True),
        sa.Column("prompt_hash", sa.String(64), nullable=True),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("input_artifact_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("output_artifact_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("input_context", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("output", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("graph_node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("graph_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.Enum("PENDING_REVIEW", "ACCEPTED", "REJECTED",
                  "OVERRIDDEN", "SUPERSEDED", name="ai_decision_status",
                  create_constraint=False), nullable=False,
                  server_default="PENDING_REVIEW"),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_ai_decisions_organization_id", "ai_decisions", ["organization_id"])
    op.create_index("ix_ai_decisions_study_id", "ai_decisions", ["study_id"])
    op.create_index("ix_ai_decisions_agent_name", "ai_decisions", ["agent_name"])
    op.create_index("ix_ai_decisions_decision_type", "ai_decisions", ["decision_type"])
    op.create_index("ix_ai_decisions_status", "ai_decisions", ["status"])
    op.create_index("ix_ai_decisions_created_at", "ai_decisions", ["created_at"])

    # ------------------------------------------------------------------
    # graph_edges
    # ------------------------------------------------------------------
    op.create_table(
        "graph_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("study_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("studies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("edge_type", sa.Enum(
            "CREATED_BY", "UPDATED_BY", "REVIEWED_BY", "APPROVED_BY", "REJECTED_BY",
            "DERIVED_FROM", "GENERATED_FROM", "MAPS_TO", "VALIDATES",
            "FAILS_VALIDATION", "FIXED_BY", "SUPPORTS", "CITED_IN", "USED_IN",
            "DEPENDS_ON", "SUPERSEDES", "AMENDS", "ACCEPTED_BY", "OVERRIDDEN_BY",
            "EXPLAINS", "CROSS_CHECKED_BY", "OBJECTIVE_TO_ENDPOINT",
            "ENDPOINT_TO_ECR", "ECR_TO_SDTM", "SDTM_TO_ADAM", "ADAM_TO_TLF",
            "TLF_TO_CSR", "PART_OF", "HAS_MEMBER",
            name="graph_edge_type", create_constraint=False), nullable=False),
        sa.Column("label", sa.String(256), nullable=True),
        sa.Column("properties", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("is_ai_generated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ai_decision_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_decisions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_graph_edges_organization_id", "graph_edges", ["organization_id"])
    op.create_index("ix_graph_edges_study_id", "graph_edges", ["study_id"])
    op.create_index("ix_graph_edges_source_node_id", "graph_edges", ["source_node_id"])
    op.create_index("ix_graph_edges_target_node_id", "graph_edges", ["target_node_id"])
    op.create_index("ix_graph_edges_edge_type", "graph_edges", ["edge_type"])

    # ------------------------------------------------------------------
    # graph_events
    # ------------------------------------------------------------------
    op.create_table(
        "graph_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("study_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("studies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("graph_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("edge_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("graph_edges.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_agent_id", sa.String(128), nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_graph_events_organization_id", "graph_events", ["organization_id"])
    op.create_index("ix_graph_events_event_type", "graph_events", ["event_type"])
    op.create_index("ix_graph_events_created_at", "graph_events", ["created_at"])

    # ------------------------------------------------------------------
    # human_overrides
    # ------------------------------------------------------------------
    op.create_table(
        "human_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("study_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("studies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ai_decision_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_decisions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("context_type", sa.String(128), nullable=False),
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("field_path", sa.String(512), nullable=True),
        sa.Column("original_value", postgresql.JSONB, nullable=True),
        sa.Column("new_value", postgresql.JSONB, nullable=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("override_type", sa.String(64), nullable=False),
        sa.Column("graph_node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("graph_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_human_overrides_organization_id", "human_overrides", ["organization_id"])
    op.create_index("ix_human_overrides_study_id", "human_overrides", ["study_id"])
    op.create_index("ix_human_overrides_ai_decision_id", "human_overrides", ["ai_decision_id"])
    op.create_index("ix_human_overrides_context_type", "human_overrides", ["context_type"])
    op.create_index("ix_human_overrides_override_type", "human_overrides", ["override_type"])
    op.create_index("ix_human_overrides_actor_user_id", "human_overrides", ["actor_user_id"])
    op.create_index("ix_human_overrides_created_at", "human_overrides", ["created_at"])

    # ------------------------------------------------------------------
    # data_lineage
    # ------------------------------------------------------------------
    op.create_table(
        "data_lineage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("study_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("studies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("lineage_type", sa.Enum(
            "DERIVED", "MAPPED", "AGGREGATED", "TRANSFORMED", "VALIDATED",
            "GENERATED", "MERGED", "FILTERED", "IMPUTED",
            name="data_lineage_type", create_constraint=False), nullable=False),
        sa.Column("source_type", sa.String(128), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_field", sa.String(256), nullable=True),
        sa.Column("source_domain", sa.String(64), nullable=True),
        sa.Column("target_type", sa.String(128), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_field", sa.String(256), nullable=True),
        sa.Column("target_domain", sa.String(64), nullable=True),
        sa.Column("transformation_logic", sa.Text, nullable=True),
        sa.Column("transformation_code", sa.Text, nullable=True),
        sa.Column("assumptions", postgresql.JSONB, nullable=True),
        sa.Column("is_ai_generated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ai_decision_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_decisions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_graph_node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("graph_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_graph_node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("graph_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_data_lineage_organization_id", "data_lineage", ["organization_id"])
    op.create_index("ix_data_lineage_study_id", "data_lineage", ["study_id"])
    op.create_index("ix_data_lineage_lineage_type", "data_lineage", ["lineage_type"])
    op.create_index("ix_data_lineage_created_at", "data_lineage", ["created_at"])

    # ------------------------------------------------------------------
    # artifact_lineage
    # ------------------------------------------------------------------
    op.create_table(
        "artifact_lineage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("study_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("studies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_artifact_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("artifact_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_artifact_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_version_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("artifact_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("relationship_type", sa.String(64), nullable=False),
        sa.Column("derivation_notes", sa.Text, nullable=True),
        sa.Column("is_ai_generated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ai_decision_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_decisions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_artifact_lineage_organization_id", "artifact_lineage", ["organization_id"])
    op.create_index("ix_artifact_lineage_study_id", "artifact_lineage", ["study_id"])
    op.create_index("ix_artifact_lineage_source_artifact_id", "artifact_lineage", ["source_artifact_id"])
    op.create_index("ix_artifact_lineage_target_artifact_id", "artifact_lineage", ["target_artifact_id"])

    # ------------------------------------------------------------------
    # validation_evidence
    # ------------------------------------------------------------------
    op.create_table(
        "validation_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("study_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("studies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("validation_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("validation_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rule_id", sa.String(128), nullable=True),
        sa.Column("rule_name", sa.String(256), nullable=True),
        sa.Column("rule_category", sa.String(64), nullable=True),
        sa.Column("cdisc_standard", sa.String(64), nullable=True),
        sa.Column("subject_type", sa.String(128), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject_field", sa.String(256), nullable=True),
        sa.Column("subject_value", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.Enum(
            "PENDING", "PASS", "FAIL", "WARNING", "WAIVED",
            name="validation_evidence_status", create_constraint=False), nullable=False),
        sa.Column("finding_severity", sa.String(32), nullable=True),
        sa.Column("finding_message", sa.Text, nullable=True),
        sa.Column("finding_details", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_ai_evaluated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ai_decision_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_decisions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("waived_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("waiver_reason", sa.Text, nullable=True),
        sa.Column("waived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("graph_node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("graph_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_validation_evidence_organization_id", "validation_evidence", ["organization_id"])
    op.create_index("ix_validation_evidence_study_id", "validation_evidence", ["study_id"])
    op.create_index("ix_validation_evidence_validation_run_id", "validation_evidence", ["validation_run_id"])
    op.create_index("ix_validation_evidence_rule_id", "validation_evidence", ["rule_id"])
    op.create_index("ix_validation_evidence_status", "validation_evidence", ["status"])
    op.create_index("ix_validation_evidence_created_at", "validation_evidence", ["created_at"])

    # ------------------------------------------------------------------
    # synthetic_data_runs
    # ------------------------------------------------------------------
    op.create_table(
        "synthetic_data_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("study_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("target_n", sa.Integer, nullable=True),
        sa.Column("target_domains", postgresql.JSONB, nullable=True),
        sa.Column("configuration", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("random_seed", sa.Integer, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("records_generated", sa.Integer, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("ai_decision_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_decisions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("output_artifact_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("graph_node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("graph_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_synthetic_data_runs_organization_id", "synthetic_data_runs", ["organization_id"])
    op.create_index("ix_synthetic_data_runs_study_id", "synthetic_data_runs", ["study_id"])
    op.create_index("ix_synthetic_data_runs_status", "synthetic_data_runs", ["status"])

    # ------------------------------------------------------------------
    # simulation_assumptions
    # ------------------------------------------------------------------
    op.create_table(
        "simulation_assumptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("synthetic_data_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assumption_type", sa.String(128), nullable=False),
        sa.Column("domain", sa.String(64), nullable=True),
        sa.Column("variable", sa.String(128), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("parameters", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("source_reference", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_simulation_assumptions_organization_id", "simulation_assumptions", ["organization_id"])
    op.create_index("ix_simulation_assumptions_run_id", "simulation_assumptions", ["run_id"])

    # ------------------------------------------------------------------
    # external_sources
    # ------------------------------------------------------------------
    op.create_table(
        "external_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("authors", sa.Text, nullable=True),
        sa.Column("publication_date", sa.String(32), nullable=True),
        sa.Column("doi", sa.String(256), nullable=True),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("pmid", sa.String(32), nullable=True),
        sa.Column("version", sa.String(64), nullable=True),
        sa.Column("abstract", sa.Text, nullable=True),
        sa.Column("key_findings", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("relevance_notes", sa.Text, nullable=True),
        sa.Column("graph_node_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("graph_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_external_sources_organization_id", "external_sources", ["organization_id"])
    op.create_index("ix_external_sources_source_type", "external_sources", ["source_type"])
    op.create_index("ix_external_sources_doi", "external_sources", ["doi"])


def downgrade() -> None:
    op.drop_table("external_sources")
    op.drop_table("simulation_assumptions")
    op.drop_table("synthetic_data_runs")
    op.drop_table("validation_evidence")
    op.drop_table("artifact_lineage")
    op.drop_table("data_lineage")
    op.drop_table("human_overrides")
    op.drop_table("graph_events")
    op.drop_table("graph_edges")
    op.drop_table("ai_decisions")
    op.drop_table("graph_nodes")

    op.execute("DROP TYPE IF EXISTS validation_evidence_status")
    op.execute("DROP TYPE IF EXISTS data_lineage_type")
    op.execute("DROP TYPE IF EXISTS ai_decision_status")
    op.execute("DROP TYPE IF EXISTS graph_edge_type")
    op.execute("DROP TYPE IF EXISTS graph_node_type")
