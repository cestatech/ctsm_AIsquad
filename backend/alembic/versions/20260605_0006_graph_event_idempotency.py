"""Add idempotency_key to graph_events for Phase 3 contract.

Revision ID: 20260605_0006
Revises: 20260605_0005
Create Date: 2026-06-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260605_0006"
down_revision = "20260605_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "graph_events",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_graph_events_idempotency_key",
        "graph_events",
        ["idempotency_key"],
        unique=False,
    )
    op.create_index(
        "uq_graph_events_org_idempotency",
        "graph_events",
        ["organization_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_graph_events_org_idempotency", table_name="graph_events")
    op.drop_index("ix_graph_events_idempotency_key", table_name="graph_events")
    op.drop_column("graph_events", "idempotency_key")
