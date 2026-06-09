"""Add data source classification columns for pipeline data cuts.

Revision ID: 20260609_0012
Revises: 20260608_0011
Create Date: 2026-06-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260609_0012"
down_revision = "20260608_0011"
branch_labels = None
depends_on = None

data_source_type = postgresql.ENUM(
    "SYNTHETIC",
    "LIVE_INTERIM",
    "LIVE_FINAL",
    name="data_source_type",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE data_source_type AS ENUM ('SYNTHETIC', 'LIVE_INTERIM', 'LIVE_FINAL')"
    )

    op.add_column(
        "uploaded_files",
        sa.Column(
            "data_source_type",
            data_source_type,
            nullable=False,
            server_default="LIVE_FINAL",
        ),
    )
    op.add_column(
        "uploaded_files",
        sa.Column("data_cut_label", sa.String(256), nullable=True),
    )
    op.add_column(
        "uploaded_files",
        sa.Column("data_cut_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "uploaded_files",
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "uploaded_files",
        sa.Column("data_cut_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.add_column(
        "raw_datasets",
        sa.Column(
            "data_source_type",
            data_source_type,
            nullable=False,
            server_default="LIVE_FINAL",
        ),
    )
    op.add_column(
        "raw_datasets",
        sa.Column("data_cut_label", sa.String(256), nullable=True),
    )
    op.add_column(
        "raw_datasets",
        sa.Column("data_cut_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "raw_datasets",
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "raw_datasets",
        sa.Column("data_cut_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "raw_datasets",
        sa.Column("source_upload_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # source_upload_id is a lineage reference only — uploaded_file_id is the ORM FK

    op.add_column(
        "synthetic_data_runs",
        sa.Column(
            "data_source_type",
            data_source_type,
            nullable=False,
            server_default="SYNTHETIC",
        ),
    )
    op.add_column(
        "synthetic_data_runs",
        sa.Column("data_cut_label", sa.String(256), nullable=True),
    )
    op.add_column(
        "synthetic_data_runs",
        sa.Column("data_cut_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "synthetic_data_runs",
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "synthetic_data_runs",
        sa.Column("data_cut_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("synthetic_data_runs", "data_cut_id")
    op.drop_column("synthetic_data_runs", "is_synthetic")
    op.drop_column("synthetic_data_runs", "data_cut_date")
    op.drop_column("synthetic_data_runs", "data_cut_label")
    op.drop_column("synthetic_data_runs", "data_source_type")

    op.drop_column("raw_datasets", "source_upload_id")
    op.drop_column("raw_datasets", "data_cut_id")
    op.drop_column("raw_datasets", "is_synthetic")
    op.drop_column("raw_datasets", "data_cut_date")
    op.drop_column("raw_datasets", "data_cut_label")
    op.drop_column("raw_datasets", "data_source_type")

    op.drop_column("uploaded_files", "data_cut_id")
    op.drop_column("uploaded_files", "is_synthetic")
    op.drop_column("uploaded_files", "data_cut_date")
    op.drop_column("uploaded_files", "data_cut_label")
    op.drop_column("uploaded_files", "data_source_type")

    op.execute("DROP TYPE IF EXISTS data_source_type")
