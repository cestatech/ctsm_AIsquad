"""Phase 8 submission packages, validation evidence source, INCLUDES edge.

Revision ID: 20260608_0008
Revises: 20260605_0007
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260608_0008"
down_revision = "20260605_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE submission_package_status AS ENUM "
        "('DRAFT', 'PACKAGING', 'READY', 'SUBMITTED')"
    )
    op.create_table(
        "submission_packages",
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
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "DRAFT",
                "PACKAGING",
                "READY",
                "SUBMITTED",
                name="submission_package_status",
                create_type=False,
            ),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column(
            "artifact_ids",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
        ),
        sa.Column("local_path", sa.String(1024), nullable=True),
        sa.Column("s3_key", sa.String(1024), nullable=True),
        sa.Column("package_checksum", sa.String(128), nullable=True),
        sa.Column(
            "manifest",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_submission_packages_org_study",
        "submission_packages",
        ["organization_id", "study_id"],
    )

    op.add_column(
        "validation_evidence",
        sa.Column(
            "source",
            sa.String(64),
            nullable=False,
            server_default="INTERNAL",
        ),
    )

    op.execute("ALTER TYPE graph_edge_type ADD VALUE IF NOT EXISTS 'INCLUDES'")


def downgrade() -> None:
    op.drop_column("validation_evidence", "source")
    op.drop_index("ix_submission_packages_org_study", table_name="submission_packages")
    op.drop_table("submission_packages")
    op.execute("DROP TYPE IF EXISTS submission_package_status")
