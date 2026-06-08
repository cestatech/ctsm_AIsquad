"""Add data parse/mapping audit action enum values.

Revision ID: 20260605_0004
Revises: 20260605_0003
Create Date: 2026-06-05
"""

from __future__ import annotations

from alembic import op

revision = "20260605_0004"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

_NEW_VALUES = (
    "data.file_parsed",
    "data.field_mapped",
    "data.mapping_approved",
)


def upgrade() -> None:
    for value in _NEW_VALUES:
        op.execute(
            f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{value}'"
        )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely.
    pass
