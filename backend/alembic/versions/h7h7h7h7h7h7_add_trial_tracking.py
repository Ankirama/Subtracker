"""add trial tracking

Revision ID: h7h7h7h7h7h7
Revises: g6g6g6g6g6g6
Create Date: 2025-11-17 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "h7h7h7h7h7h7"
down_revision = "g6g6g6g6g6g6"
branch_labels = None
depends_on = None


def upgrade():
    # Add trial_status field
    # Possible values: 'none', 'trial', 'trial_ended', 'trial_cancelled', 'converted'
    op.add_column(
        "subscriptions", sa.Column("trial_status", sa.String(50), nullable=True)
    )

    # Add trial_end_date field
    op.add_column(
        "subscriptions", sa.Column("trial_end_date", sa.Date(), nullable=True)
    )

    # Add is_confirmed field - true if subscription is confirmed (2+ emails OR no trial detected)
    op.add_column(
        "subscriptions",
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default="true"),
    )

    # Create index on is_confirmed for filtering
    op.create_index("ix_subscriptions_is_confirmed", "subscriptions", ["is_confirmed"])

    # Create index on trial_status for filtering
    op.create_index("ix_subscriptions_trial_status", "subscriptions", ["trial_status"])


def downgrade():
    op.drop_index("ix_subscriptions_trial_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_is_confirmed", table_name="subscriptions")
    op.drop_column("subscriptions", "is_confirmed")
    op.drop_column("subscriptions", "trial_end_date")
    op.drop_column("subscriptions", "trial_status")
