"""Add oldest/newest email date columns on sync_history and mailboxes

Tracks the date range of emails processed by each sync run, so the user can
verify the expected window was covered (e.g. after changing import_date_filter
or a force-resync).

Revision ID: m2m2m2m2m2m2
Revises: l1l1l1l1l1l1
Create Date: 2026-05-01

"""

from alembic import op
import sqlalchemy as sa


revision = "m2m2m2m2m2m2"
down_revision = "l1l1l1l1l1l1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sync_history",
        sa.Column("oldest_email_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sync_history",
        sa.Column("newest_email_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mailboxes",
        sa.Column(
            "last_sync_oldest_email_date", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "mailboxes",
        sa.Column(
            "last_sync_newest_email_date", sa.DateTime(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("mailboxes", "last_sync_newest_email_date")
    op.drop_column("mailboxes", "last_sync_oldest_email_date")
    op.drop_column("sync_history", "newest_email_date")
    op.drop_column("sync_history", "oldest_email_date")
