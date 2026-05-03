"""Add CANCELLATION_DETECTED to notificationtype enum

Revision ID: q6q6q6q6q6q6
Revises: p5p5p5p5p5p5
Create Date: 2026-05-03

"""

from alembic import op


revision = "q6q6q6q6q6q6"
down_revision = "p5p5p5p5p5p5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'CANCELLATION_DETECTED'"
        )


def downgrade() -> None:
    # Postgres does not natively support removing enum values; one-way migration.
    pass
