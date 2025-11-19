"""add two-factor authentication fields

Revision ID: add_2fa_simple
Revises: h7h7h7h7h7h7
Create Date: 2025-11-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_2fa_simple'
down_revision = 'h7h7h7h7h7h7'
branch_labels = None
depends_on = None


def upgrade():
    # Add 2FA fields to users table
    op.add_column('users', sa.Column('two_factor_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('two_factor_method', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('two_factor_secret', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('backup_codes', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'))

    # Create email_otp table
    op.create_table(
        'email_otp',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_used', sa.String(length=1), nullable=False, server_default='N'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_email_otp_user_id'), 'email_otp', ['user_id'], unique=False)


def downgrade():
    # Remove email_otp table
    op.drop_index(op.f('ix_email_otp_user_id'), table_name='email_otp')
    op.drop_table('email_otp')

    # Remove 2FA fields from users table
    op.drop_column('users', 'backup_codes')
    op.drop_column('users', 'two_factor_secret')
    op.drop_column('users', 'two_factor_method')
    op.drop_column('users', 'two_factor_enabled')
