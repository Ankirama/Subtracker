"""Add new_emails_count columns on sync_history and mailboxes

Tracks how many email_messages rows were inserted during each sync run, so
the user can see "+N new emails this run" rather than just the cumulative
total_emails_processed counter.

Revision ID: n3n3n3n3n3n3
Revises: m2m2m2m2m2m2
Create Date: 2026-05-02

"""

from alembic import op
import sqlalchemy as sa


revision = "n3n3n3n3n3n3"
down_revision = "m2m2m2m2m2m2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sync_history",
        sa.Column("new_emails_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "mailboxes",
        sa.Column("last_sync_new_emails_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mailboxes", "last_sync_new_emails_count")
    op.drop_column("sync_history", "new_emails_count")
