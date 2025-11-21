"""Add cancellation suggestion fields to subscriptions

Revision ID: a1a1a1a1a1a1
Revises: 540dbcb696ca
Create Date: 2025-11-21 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1a1a1a1a1a1'
down_revision = '540dbcb696ca'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add AI-suggested cancellation fields to subscriptions table
    op.add_column(
        'subscriptions',
        sa.Column('suggested_cancellation_status', sa.String(length=50), nullable=True)
    )
    op.add_column(
        'subscriptions',
        sa.Column('cancellation_suggestion_reason', sa.Text(), nullable=True)
    )
    op.add_column(
        'subscriptions',
        sa.Column('cancellation_suggestion_created_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Add index on suggested_cancellation_status for efficient queries
    op.create_index(
        'ix_subscriptions_suggested_cancellation_status',
        'subscriptions',
        ['suggested_cancellation_status'],
        unique=False
    )


def downgrade() -> None:
    # Remove index
    op.drop_index('ix_subscriptions_suggested_cancellation_status', table_name='subscriptions')

    # Remove columns in reverse order
    op.drop_column('subscriptions', 'cancellation_suggestion_created_at')
    op.drop_column('subscriptions', 'cancellation_suggestion_reason')
    op.drop_column('subscriptions', 'suggested_cancellation_status')
