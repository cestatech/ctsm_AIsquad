"""Add idempotency_key_hash to graph_edges for long edge-type keys.

Revision ID: 20260611_0014
Revises: 20260609_0013
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260611_0014"
down_revision = "20260609_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "graph_edges",
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_graph_edges_idempotency_key_hash",
        "graph_edges",
        ["idempotency_key_hash"],
        unique=False,
    )
    op.create_index(
        "uq_graph_edges_org_idempotency_hash",
        "graph_edges",
        ["organization_id", "idempotency_key_hash"],
        unique=True,
        postgresql_where=sa.text("idempotency_key_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_graph_edges_org_idempotency_hash", table_name="graph_edges")
    op.drop_index("ix_graph_edges_idempotency_key_hash", table_name="graph_edges")
    op.drop_column("graph_edges", "idempotency_key_hash")
