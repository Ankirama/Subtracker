"""Add sync cancellation fields to mailbox

Revision ID: 4fdf15473020
Revises: c892bb527c3e
Create Date: 2025-11-19 07:46:35.282959

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4fdf15473020"
down_revision = "c892bb527c3e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add user-initiated sync cancellation fields to mailboxes table
    op.add_column(
        "mailboxes",
        sa.Column(
            "sync_cancellation_requested",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "mailboxes",
        sa.Column("sync_cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Remove sync cancellation fields from mailboxes table
    op.drop_column("mailboxes", "sync_cancelled_at")
    op.drop_column("mailboxes", "sync_cancellation_requested")
