"""Add sync_history_id links on subscriptions / price_history / mailboxes

Revision ID: o4o4o4o4o4o4
Revises: n3n3n3n3n3n3
Create Date: 2026-05-02

"""

from alembic import op
import sqlalchemy as sa


revision = "o4o4o4o4o4o4"
down_revision = "n3n3n3n3n3n3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column(
            "discovered_via_sync_history_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sync_history.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_subscriptions_discovered_via_sync_history_id",
        "subscriptions",
        ["discovered_via_sync_history_id"],
    )
    op.add_column(
        "price_history",
        sa.Column(
            "sync_history_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sync_history.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_price_history_sync_history_id",
        "price_history",
        ["sync_history_id"],
    )
    op.add_column(
        "mailboxes",
        sa.Column(
            "last_sync_history_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sync_history.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("mailboxes", "last_sync_history_id")
    op.drop_index("ix_price_history_sync_history_id", "price_history")
    op.drop_column("price_history", "sync_history_id")
    op.drop_index("ix_subscriptions_discovered_via_sync_history_id", "subscriptions")
    op.drop_column("subscriptions", "discovered_via_sync_history_id")
