"""Add SUBMISSION_PACKAGE graph node type.

Revision ID: 20260608_0009
Revises: 20260608_0008
Create Date: 2026-06-08
"""

from __future__ import annotations

from alembic import op

revision = "20260608_0009"
down_revision = "20260608_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE graph_node_type ADD VALUE IF NOT EXISTS 'SUBMISSION_PACKAGE'"
    )


def downgrade() -> None:
    pass
