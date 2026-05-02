"""Add SYNC_PREVIEW_AVAILABLE to notificationtype enum

Revision ID: p5p5p5p5p5p5
Revises: o4o4o4o4o4o4
Create Date: 2026-05-02

"""

from alembic import op


revision = "p5p5p5p5p5p5"
down_revision = "o4o4o4o4o4o4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'SYNC_PREVIEW_AVAILABLE'"
        )


def downgrade() -> None:
    # Postgres does not natively support removing enum values; one-way migration.
    pass
