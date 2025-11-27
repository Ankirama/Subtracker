"""add_subscription_feedback_table

Revision ID: abc123def456
Revises: i8i8i8i8i8i8
Create Date: 2025-11-27 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY


# revision identifiers, used by Alembic.
revision = 'abc123def456'
down_revision = 'i8i8i8i8i8i8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create subscription_feedback table
    op.create_table(
        'subscription_feedback',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subscription_id', UUID(as_uuid=True), nullable=False),
        sa.Column('feedback_type', sa.String(50), nullable=False),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('subscription_snapshot', JSONB, nullable=False),
        sa.Column('ai_classification_data', JSONB, nullable=True),
        sa.Column('source_email_ids', ARRAY(UUID(as_uuid=True)), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Create indexes
    op.create_index('ix_subscription_feedback_id', 'subscription_feedback', ['id'])
    op.create_index('ix_subscription_feedback_user_id', 'subscription_feedback', ['user_id'])
    op.create_index('ix_subscription_feedback_feedback_type', 'subscription_feedback', ['feedback_type'])
    op.create_index('ix_subscription_feedback_created_at', 'subscription_feedback', ['created_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_subscription_feedback_created_at', table_name='subscription_feedback')
    op.drop_index('ix_subscription_feedback_feedback_type', table_name='subscription_feedback')
    op.drop_index('ix_subscription_feedback_user_id', table_name='subscription_feedback')
    op.drop_index('ix_subscription_feedback_id', table_name='subscription_feedback')

    # Drop table
    op.drop_table('subscription_feedback')
