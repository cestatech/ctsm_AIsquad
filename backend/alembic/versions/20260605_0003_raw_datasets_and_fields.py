"""Add raw_datasets, raw_fields, field_mapping_versions tables and upload enhancements.

Phase 2: turns file uploads into a full data ingestion layer with column
profiling, versioned field-to-eCRF/SDTM mappings, and CIP graph registration.

Also adds RAW_DATASET and UPLOADED_FILE to the graph_node_type PostgreSQL enum.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c3d4e5f6a7b8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- 1. Extend PostgreSQL enums (PG 12+ supports this in a transaction) ------
    op.execute(
        sa.text("ALTER TYPE graph_node_type ADD VALUE IF NOT EXISTS 'RAW_DATASET'")
    )
    op.execute(
        sa.text("ALTER TYPE graph_node_type ADD VALUE IF NOT EXISTS 'UPLOADED_FILE'")
    )

    # -- 2. Extend uploaded_files with hash and status --------------------------
    op.add_column(
        "uploaded_files",
        sa.Column("file_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "uploaded_files",
        sa.Column(
            "upload_status",
            sa.String(20),
            nullable=False,
            server_default="UPLOADED",
        ),
    )

    # -- 3. raw_datasets --------------------------------------------------------
    op.create_table(
        "raw_datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("uploaded_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dataset_name", sa.String(500), nullable=False),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("column_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "parse_status", sa.String(20), nullable=False, server_default="PENDING"
        ),
        sa.Column("parse_error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_raw_datasets_uploaded_file_id", "raw_datasets", ["uploaded_file_id"])
    op.create_index("ix_raw_datasets_study_id", "raw_datasets", ["study_id"])
    op.create_index("ix_raw_datasets_organization_id", "raw_datasets", ["organization_id"])

    # -- 4. raw_fields ----------------------------------------------------------
    op.create_table(
        "raw_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "raw_dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("raw_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("column_name", sa.String(500), nullable=False),
        sa.Column("column_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "inferred_type", sa.String(20), nullable=False, server_default="string"
        ),
        sa.Column(
            "sample_values", postgresql.JSONB, nullable=False, server_default="[]"
        ),
        sa.Column("missing_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("distinct_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("min_value", sa.Text, nullable=True),
        sa.Column("max_value", sa.Text, nullable=True),
        sa.Column("mapped_ecrf_field_id", sa.String(200), nullable=True),
        sa.Column("mapped_sdtm_variable_id", sa.String(200), nullable=True),
        sa.Column(
            "mapping_status", sa.String(20), nullable=False, server_default="UNMAPPED"
        ),
        sa.Column("mapping_version", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_raw_fields_raw_dataset_id", "raw_fields", ["raw_dataset_id"])
    op.create_index("ix_raw_fields_study_id", "raw_fields", ["study_id"])
    op.create_index("ix_raw_fields_organization_id", "raw_fields", ["organization_id"])

    # -- 5. field_mapping_versions ---------------------------------------------
    op.create_table(
        "field_mapping_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "raw_field_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("raw_fields.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("mapped_ecrf_field_id", sa.String(200), nullable=True),
        sa.Column("mapped_sdtm_variable_id", sa.String(200), nullable=True),
        sa.Column("mapping_status", sa.String(20), nullable=False),
        sa.Column(
            "changed_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "approved_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_field_mapping_versions_raw_field_id",
        "field_mapping_versions",
        ["raw_field_id"],
    )
    op.create_index(
        "ix_field_mapping_versions_organization_id",
        "field_mapping_versions",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_field_mapping_versions_organization_id", "field_mapping_versions")
    op.drop_index("ix_field_mapping_versions_raw_field_id", "field_mapping_versions")
    op.drop_table("field_mapping_versions")

    op.drop_index("ix_raw_fields_organization_id", "raw_fields")
    op.drop_index("ix_raw_fields_study_id", "raw_fields")
    op.drop_index("ix_raw_fields_raw_dataset_id", "raw_fields")
    op.drop_table("raw_fields")

    op.drop_index("ix_raw_datasets_organization_id", "raw_datasets")
    op.drop_index("ix_raw_datasets_study_id", "raw_datasets")
    op.drop_index("ix_raw_datasets_uploaded_file_id", "raw_datasets")
    op.drop_table("raw_datasets")

    op.drop_column("uploaded_files", "upload_status")
    op.drop_column("uploaded_files", "file_hash")
    # Note: PostgreSQL does not support DROP VALUE for enums — no rollback for graph_node_type additions
