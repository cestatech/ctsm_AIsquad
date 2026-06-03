"""Baseline: mark existing schema as applied.

The initial schema was applied via database/schema/001_initial_schema.sql.
This migration is a no-op marker so Alembic tracks the baseline revision
without trying to recreate tables that already exist.

Revision ID: b1a2c3d4e5f6
Revises:
Create Date: 2026-06-03 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1a2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Schema already applied via 001_initial_schema.sql — nothing to do.
    pass


def downgrade() -> None:
    # Cannot reverse baseline — would drop entire schema.
    pass
