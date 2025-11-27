"""make_amount_nullable

Revision ID: 00514e4b44e6
Revises: 0926026c96f0
Create Date: 2025-11-15 09:28:17.271393

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "00514e4b44e6"
down_revision = "0926026c96f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make amount column nullable
    op.alter_column(
        "subscriptions",
        "amount",
        existing_type=sa.Numeric(precision=10, scale=2),
        nullable=True,
    )


def downgrade() -> None:
    # Revert amount column to NOT NULL
    op.alter_column(
        "subscriptions",
        "amount",
        existing_type=sa.Numeric(precision=10, scale=2),
        nullable=False,
    )
