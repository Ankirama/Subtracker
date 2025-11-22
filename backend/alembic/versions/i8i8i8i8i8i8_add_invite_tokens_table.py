"""add_invite_tokens_table

Revision ID: i8i8i8i8i8i8
Revises: 07a4f65b0f22
Create Date: 2025-11-22 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = 'i8i8i8i8i8i8'
down_revision = '07a4f65b0f22'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create invite_tokens table for invite-only registration
    op.create_table(
        'invite_tokens',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('created_by_id', UUID(as_uuid=True), nullable=False),
        sa.Column('invited_email', sa.String(255), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('used_by_id', UUID(as_uuid=True), nullable=True),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['used_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )

    # Create index on token for fast lookups
    op.create_index(op.f('ix_invite_tokens_token'), 'invite_tokens', ['token'], unique=True)

    # Create index on created_by_id for listing admin's invites
    op.create_index(op.f('ix_invite_tokens_created_by_id'), 'invite_tokens', ['created_by_id'], unique=False)


def downgrade() -> None:
    # Drop indexes and table
    op.drop_index(op.f('ix_invite_tokens_created_by_id'), table_name='invite_tokens')
    op.drop_index(op.f('ix_invite_tokens_token'), table_name='invite_tokens')
    op.drop_table('invite_tokens')
