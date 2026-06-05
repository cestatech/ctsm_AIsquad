"""Add org_role column to users for organization-level RBAC.

Without this column, effective_role always falls back to CONTRIBUTOR,
making REVIEWER enforcement impossible at the org level.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "org_role",
            postgresql.ENUM("ADMIN", "CONTRIBUTOR", "REVIEWER", name="user_role", create_type=False),
            nullable=False,
            server_default="CONTRIBUTOR",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "org_role")
