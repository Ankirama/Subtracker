"""add_cancellation_workflows

Revision ID: 146748050f00
Revises: 68494f616c0d
Create Date: 2025-11-19 15:02:09.599737

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '146748050f00'
down_revision = '68494f616c0d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types (only if they don't exist)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE difficulty_rating_enum AS ENUM ('easy', 'medium', 'hard');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE instructions_source_enum AS ENUM ('manual', 'ai_generated', 'community', 'verified');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create provider_cancellation_info table
    op.create_table(
        'provider_cancellation_info',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_name', sa.String(length=255), nullable=False),
        sa.Column('cancellation_url', sa.Text(), nullable=True),
        sa.Column(
            'difficulty_rating',
            postgresql.ENUM('easy', 'medium', 'hard', name='difficulty_rating_enum', create_type=False),
            nullable=False,
            server_default='medium'
        ),
        sa.Column('instructions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            'instructions_source',
            postgresql.ENUM('manual', 'ai_generated', 'community', 'verified', name='instructions_source_enum', create_type=False),
            nullable=False,
            server_default='ai_generated'
        ),
        sa.Column('requires_phone_call', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('requires_chat', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('allows_pause', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('pause_instructions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verification_notes', sa.Text(), nullable=True),
        sa.Column('ai_research_prompt', sa.Text(), nullable=True),
        sa.Column('ai_research_response', sa.Text(), nullable=True),
        sa.Column('ai_confidence_score', sa.Float(), nullable=True),
        sa.Column('additional_notes', sa.Text(), nullable=True),
        sa.Column('estimated_time_minutes', sa.Float(), nullable=True),
        sa.Column('cancellation_gotchas', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for provider_cancellation_info
    op.create_index(op.f('ix_provider_cancellation_info_id'), 'provider_cancellation_info', ['id'], unique=False)
    op.create_index(
        op.f('ix_provider_cancellation_info_provider_name'),
        'provider_cancellation_info',
        ['provider_name'],
        unique=True
    )
    op.create_index(
        op.f('ix_provider_cancellation_info_difficulty_rating'),
        'provider_cancellation_info',
        ['difficulty_rating'],
        unique=False
    )
    op.create_index(
        op.f('ix_provider_cancellation_info_instructions_source'),
        'provider_cancellation_info',
        ['instructions_source'],
        unique=False
    )

    # Add cancellation tracking columns to subscriptions table
    op.add_column(
        'subscriptions',
        sa.Column('cancellation_status', sa.String(length=50), nullable=False, server_default='active')
    )
    op.add_column('subscriptions', sa.Column('cancellation_requested_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('cancellation_confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('cancellation_notes', sa.Text(), nullable=True))

    # Create index on cancellation_status
    op.create_index(
        op.f('ix_subscriptions_cancellation_status'),
        'subscriptions',
        ['cancellation_status'],
        unique=False
    )


def downgrade() -> None:
    # Drop index on subscriptions
    op.drop_index(op.f('ix_subscriptions_cancellation_status'), table_name='subscriptions')

    # Remove cancellation columns from subscriptions
    op.drop_column('subscriptions', 'cancellation_notes')
    op.drop_column('subscriptions', 'cancellation_confirmed_at')
    op.drop_column('subscriptions', 'cancellation_requested_at')
    op.drop_column('subscriptions', 'cancellation_status')

    # Drop indexes for provider_cancellation_info
    op.drop_index(op.f('ix_provider_cancellation_info_instructions_source'), table_name='provider_cancellation_info')
    op.drop_index(op.f('ix_provider_cancellation_info_difficulty_rating'), table_name='provider_cancellation_info')
    op.drop_index(op.f('ix_provider_cancellation_info_provider_name'), table_name='provider_cancellation_info')
    op.drop_index(op.f('ix_provider_cancellation_info_id'), table_name='provider_cancellation_info')

    # Drop provider_cancellation_info table
    op.drop_table('provider_cancellation_info')

    # Drop enum types
    op.execute("DROP TYPE instructions_source_enum")
    op.execute("DROP TYPE difficulty_rating_enum")
