"""add_email_verification_and_ip_blocking

Revision ID: 8e2d92da35aa
Revises: add_2fa_simple
Create Date: 2025-11-18 21:04:24.421286

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e2d92da35aa'
down_revision = 'add_2fa_simple'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add email verification fields to users table
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('email_verification_token', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('email_verification_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('display_name', sa.String(length=255), nullable=True))

    # Create indexes
    op.create_index('ix_users_email_verified', 'users', ['email_verified'])
    op.create_index('ix_users_email_verification_token', 'users', ['email_verification_token'], unique=True)

    # Create ip_blocks table
    op.create_table(
        'ip_blocks',
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('blocked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('attempt_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('ip_address')
    )


def downgrade() -> None:
    # Drop ip_blocks table
    op.drop_table('ip_blocks')

    # Drop indexes
    op.drop_index('ix_users_email_verification_token', 'users')
    op.drop_index('ix_users_email_verified', 'users')

    # Drop columns from users table
    op.drop_column('users', 'display_name')
    op.drop_column('users', 'email_verified_at')
    op.drop_column('users', 'email_verification_sent_at')
    op.drop_column('users', 'email_verification_token')
    op.drop_column('users', 'email_verified')
