"""Add price_history table

Revision ID: d3d3d3d3d3d3
Revises: c2c2c2c2c2c2
Create Date: 2025-01-17 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd3d3d3d3d3d3'
down_revision = 'c2c2c2c2c2c2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create price_history table
    op.create_table(
        'price_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('new_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='EUR'),
        sa.Column('change_type', sa.String(length=50), nullable=False),
        sa.Column('change_percentage', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('detected_from', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index(op.f('ix_price_history_id'), 'price_history', ['id'], unique=False)
    op.create_index(op.f('ix_price_history_subscription_id'), 'price_history', ['subscription_id'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_price_history_subscription_id'), table_name='price_history')
    op.drop_index(op.f('ix_price_history_id'), table_name='price_history')

    # Drop table
    op.drop_table('price_history')
