"""Add sponsor_intakes, intake_messages, study_briefs tables.

Supports the AI-driven sponsor intake questionnaire that gathers all
study information needed to drive the Protocol → CSR generation pipeline.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend graph node type enum with intake-specific node types
    op.execute("ALTER TYPE graph_node_type ADD VALUE IF NOT EXISTS 'INTAKE_SESSION'")
    op.execute("ALTER TYPE graph_node_type ADD VALUE IF NOT EXISTS 'STUDY_BRIEF'")

    op.execute(
        "CREATE TYPE intake_status AS ENUM "
        "('IN_PROGRESS', 'READY_TO_COMPILE', 'COMPILED')"
    )

    op.create_table(
        "sponsor_intakes",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("study_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "status",
            sa.Enum("IN_PROGRESS", "READY_TO_COMPILE", "COMPILED", name="intake_status"),
            nullable=False,
            server_default="IN_PROGRESS",
        ),
        sa.Column(
            "domains_completed",
            postgresql.ARRAY(sa.String(50)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("ready_to_compile", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["study_id"], ["studies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
    )
    op.create_index("ix_sponsor_intakes_organization_id", "sponsor_intakes", ["organization_id"])
    op.create_index("ix_sponsor_intakes_study_id", "sponsor_intakes", ["study_id"])

    op.create_table(
        "intake_messages",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("intake_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(50), nullable=True),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["intake_id"], ["sponsor_intakes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_intake_messages_intake_id", "intake_messages", ["intake_id"])

    op.create_table(
        "study_briefs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("intake_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("study_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("compiled_by_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["intake_id"], ["sponsor_intakes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["study_id"], ["studies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["compiled_by_id"], ["users.id"]),
        sa.UniqueConstraint("intake_id", name="uq_study_briefs_intake"),
    )
    op.create_index("ix_study_briefs_study_id", "study_briefs", ["study_id"])


def downgrade() -> None:
    op.drop_table("study_briefs")
    op.drop_table("intake_messages")
    op.drop_table("sponsor_intakes")
    op.execute("DROP TYPE IF EXISTS intake_status")
