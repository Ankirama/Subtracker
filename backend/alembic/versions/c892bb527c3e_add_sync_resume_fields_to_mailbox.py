"""Add sync resume fields to mailbox

Revision ID: c892bb527c3e
Revises: 8ae62870bccd
Create Date: 2025-11-19 07:35:35.126928

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c892bb527c3e'
down_revision = '8ae62870bccd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add sync resume capability fields to mailboxes table (Issue #7)
    op.add_column('mailboxes', sa.Column('last_sync_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('mailboxes', sa.Column('last_sync_position', sa.Integer(), nullable=True))
    op.add_column('mailboxes', sa.Column('last_sync_batch_num', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Remove sync resume capability fields from mailboxes table
    op.drop_column('mailboxes', 'last_sync_batch_num')
    op.drop_column('mailboxes', 'last_sync_position')
    op.drop_column('mailboxes', 'last_sync_started_at')
