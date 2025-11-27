"""add color to categories

Revision ID: g6g6g6g6g6g6
Revises: f5f5f5f5f5f5
Create Date: 2025-11-17 11:30:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "g6g6g6g6g6g6"
down_revision = "f5f5f5f5f5f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add color column to categories table
    op.add_column(
        "categories",
        sa.Column("color", sa.String(length=50), nullable=False, server_default="gray"),
    )


def downgrade() -> None:
    # Remove color column
    op.drop_column("categories", "color")
