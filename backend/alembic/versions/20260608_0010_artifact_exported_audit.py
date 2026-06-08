"""Add artifact.exported audit action enum value.

Revision ID: 20260608_0010
Revises: 20260608_0009
Create Date: 2026-06-08
"""

from __future__ import annotations

from alembic import op

revision = "20260608_0010"
down_revision = "20260608_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'artifact.exported'"
    )


def downgrade() -> None:
    pass
