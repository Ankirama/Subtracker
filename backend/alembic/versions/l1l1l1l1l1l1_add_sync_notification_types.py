"""Add SYNC_SKIPPED_MANY and SYNC_CIRCUIT_BREAKER to notificationtype enum

Revision ID: l1l1l1l1l1l1
Revises: k0k0k0k0k0k0
Create Date: 2026-04-29

"""

from alembic import op


revision = "l1l1l1l1l1l1"
down_revision = "k0k0k0k0k0k0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'SYNC_SKIPPED_MANY'"
        )
        op.execute(
            "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'SYNC_CIRCUIT_BREAKER'"
        )


def downgrade() -> None:
    # Postgres does not natively support removing enum values; one-way migration.
    pass
