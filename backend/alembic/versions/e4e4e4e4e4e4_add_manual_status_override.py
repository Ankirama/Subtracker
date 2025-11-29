"""add manual_status_override

Revision ID: e4e4e4e4e4e4
Revises: d3d3d3d3d3d3
Create Date: 2025-11-17 11:36:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e4e4e4e4e4e4"
down_revision = "d3d3d3d3d3d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add manual_status_override column to subscriptions table
    op.add_column(
        "subscriptions",
        sa.Column(
            "manual_status_override",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    # Remove manual_status_override column from subscriptions table
    op.drop_column("subscriptions", "manual_status_override")
