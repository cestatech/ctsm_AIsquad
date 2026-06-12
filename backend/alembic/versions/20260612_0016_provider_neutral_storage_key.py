"""Rename the provider-specific submission package storage key.

Revision ID: 20260612_0016
Revises: 20260611_0015
"""

from alembic import op

revision = "20260612_0016"
down_revision = "20260611_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "submission_packages",
        "s3_key",
        new_column_name="storage_key",
    )


def downgrade() -> None:
    op.alter_column(
        "submission_packages",
        "storage_key",
        new_column_name="s3_key",
    )
