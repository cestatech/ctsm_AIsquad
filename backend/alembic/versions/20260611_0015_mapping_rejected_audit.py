"""Add data.mapping_rejected audit action."""

from __future__ import annotations

from alembic import op

revision = "20260611_0015"
down_revision = "20260611_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'data.mapping_rejected'"
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely.
    pass
