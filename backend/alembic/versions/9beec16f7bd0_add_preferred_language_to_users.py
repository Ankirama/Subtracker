"""Add preferred_language to users

Revision ID: 9beec16f7bd0
Revises: i8i8i8i8i8i8
Create Date: 2025-12-05 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9beec16f7bd0"
down_revision = "i8i8i8i8i8i8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add preferred_language column to users table
    # NULL means use browser detection, otherwise 'en' or 'fr'
    op.add_column(
        "users",
        sa.Column("preferred_language", sa.String(length=5), nullable=True),
    )


def downgrade() -> None:
    # Remove preferred_language column from users table
    op.drop_column("users", "preferred_language")
