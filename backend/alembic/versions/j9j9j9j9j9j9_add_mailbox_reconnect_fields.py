"""Add mailbox reconnect fields

Revision ID: j9j9j9j9j9j9
Revises: a1b2c3d4e5f6
Create Date: 2025-12-17

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "j9j9j9j9j9j9"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add reconnect tracking fields to mailboxes table
    op.add_column(
        "mailboxes",
        sa.Column(
            "needs_reconnect",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "mailboxes",
        sa.Column("auth_error_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mailboxes",
        sa.Column("auth_error_message", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mailboxes", "auth_error_message")
    op.drop_column("mailboxes", "auth_error_at")
    op.drop_column("mailboxes", "needs_reconnect")
