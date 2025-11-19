"""add sync history and progress tracking

Revision ID: 68494f616c0d
Revises: 4fdf15473020
Create Date: 2025-11-19 09:52:33.358718

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '68494f616c0d'
down_revision = '4fdf15473020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create sync_history table (Issue #11)
    op.create_table(
        'sync_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('mailbox_id', UUID(as_uuid=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer, nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('total_emails_processed', sa.Integer, nullable=False, server_default='0'),
        sa.Column('subscriptions_found', sa.Integer, nullable=False, server_default='0'),
        sa.Column('subscriptions_updated', sa.Integer, nullable=False, server_default='0'),
        sa.Column('batches_processed', sa.Integer, nullable=False, server_default='0'),
        sa.Column('sync_type', sa.String(50), nullable=True),
        sa.Column('date_filter_used', sa.String(50), nullable=True),
        sa.Column('batch_size_used', sa.Integer, nullable=True),
        sa.Column('was_resumed', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('resumed_from_position', sa.Integer, nullable=True),
        sa.Column('resumed_from_batch', sa.Integer, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('final_position', sa.Integer, nullable=True),
        sa.Column('final_batch_number', sa.Integer, nullable=True),
        sa.Column('final_progress_percentage', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['mailbox_id'], ['mailboxes.id'], ondelete='CASCADE'),
    )

    # Create indexes for sync_history
    op.create_index('ix_sync_history_id', 'sync_history', ['id'])
    op.create_index('ix_sync_history_mailbox_id', 'sync_history', ['mailbox_id'])
    op.create_index('ix_sync_history_started_at', 'sync_history', ['started_at'])
    op.create_index('ix_sync_history_status', 'sync_history', ['status'])

    # Add progress tracking fields to mailboxes table (Issue #10)
    op.add_column('mailboxes', sa.Column('current_batch_number', sa.Integer, nullable=True))
    op.add_column('mailboxes', sa.Column('total_batches_estimate', sa.Integer, nullable=True))
    op.add_column('mailboxes', sa.Column('progress_percentage', sa.Float, nullable=True))
    op.add_column('mailboxes', sa.Column('estimated_completion_time', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove progress tracking fields from mailboxes table
    op.drop_column('mailboxes', 'estimated_completion_time')
    op.drop_column('mailboxes', 'progress_percentage')
    op.drop_column('mailboxes', 'total_batches_estimate')
    op.drop_column('mailboxes', 'current_batch_number')

    # Drop indexes for sync_history
    op.drop_index('ix_sync_history_status', table_name='sync_history')
    op.drop_index('ix_sync_history_started_at', table_name='sync_history')
    op.drop_index('ix_sync_history_mailbox_id', table_name='sync_history')
    op.drop_index('ix_sync_history_id', table_name='sync_history')

    # Drop sync_history table
    op.drop_table('sync_history')
