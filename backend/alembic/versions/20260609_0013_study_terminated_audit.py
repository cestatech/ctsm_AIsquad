"""Add study.terminated audit action."""

from __future__ import annotations

from alembic import op

revision = "20260609_0013"
down_revision = "20260609_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'study.terminated'"
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely.
    pass
