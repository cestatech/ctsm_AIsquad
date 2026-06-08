"""Add ai.mapping_suggested audit action enum value.

Revision ID: 20260605_0005
Revises: 20260605_0004
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op

revision = "20260605_0005"
down_revision = "20260605_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'ai.mapping_suggested'"
    )


def downgrade() -> None:
    pass
