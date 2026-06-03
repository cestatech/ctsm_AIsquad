"""Add ai_decision_id FK to graph_events for direct AI provenance linkage.

graph_events.ai_decision_id lets the graph event log reference the exact
AI decision that caused each event, making the "why" queryable by FK join
rather than payload inspection.

Revision ID: d4e5f6a7b8c9
Revises: c2d3e4f5a6b7
Create Date: 2026-06-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "graph_events",
        sa.Column(
            "ai_decision_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("ai_decisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_graph_events_ai_decision_id",
        "graph_events",
        ["ai_decision_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_graph_events_ai_decision_id", table_name="graph_events")
    op.drop_column("graph_events", "ai_decision_id")
