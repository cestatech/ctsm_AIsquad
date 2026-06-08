"""Add statistical_program_qc_runs for dual-programmer R QC.

Revision ID: 20260605_0007
Revises: 20260605_0006
Create Date: 2026-06-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260605_0007"
down_revision = "20260605_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE statistical_qc_workflow AS ENUM "
        "('RAW_TO_SDTM', 'SDTM_TO_ADAM', 'ADAM_TO_TLF')"
    )
    op.execute(
        "CREATE TYPE statistical_qc_status AS ENUM "
        "('PENDING', 'PROGRAMS_GENERATED', 'MATCH', 'MISMATCH', "
        "'EXECUTION_FAILED', 'R_UNAVAILABLE')"
    )
    op.create_table(
        "statistical_program_qc_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_step",
            postgresql.ENUM(
                "RAW_TO_SDTM",
                "SDTM_TO_ADAM",
                "ADAM_TO_TLF",
                name="statistical_qc_workflow",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "PROGRAMS_GENERATED",
                "MATCH",
                "MISMATCH",
                "EXECUTION_FAILED",
                "R_UNAVAILABLE",
                name="statistical_qc_status",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "source_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "output_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "primary_ai_decision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_decisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "qc_ai_decision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_decisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("primary_r_program", sa.Text(), nullable=False, server_default=""),
        sa.Column("qc_r_program", sa.Text(), nullable=False, server_default=""),
        sa.Column("primary_program_hash", sa.String(64), nullable=True),
        sa.Column("qc_program_hash", sa.String(64), nullable=True),
        sa.Column("comparison_result", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_stat_qc_runs_organization_id",
        "statistical_program_qc_runs",
        ["organization_id"],
    )
    op.create_index(
        "ix_stat_qc_runs_study_id",
        "statistical_program_qc_runs",
        ["study_id"],
    )
    op.create_index(
        "ix_stat_qc_runs_output_artifact_id",
        "statistical_program_qc_runs",
        ["output_artifact_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stat_qc_runs_output_artifact_id",
        table_name="statistical_program_qc_runs",
    )
    op.drop_index(
        "ix_stat_qc_runs_study_id",
        table_name="statistical_program_qc_runs",
    )
    op.drop_index(
        "ix_stat_qc_runs_organization_id",
        table_name="statistical_program_qc_runs",
    )
    op.drop_table("statistical_program_qc_runs")
    op.execute("DROP TYPE statistical_qc_status")
    op.execute("DROP TYPE statistical_qc_workflow")
