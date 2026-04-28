"""Add email_sync_errors table and widen email_messages text columns

Revision ID: k0k0k0k0k0k0
Revises: j9j9j9j9j9j9
Create Date: 2026-04-28

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "k0k0k0k0k0k0"
down_revision = "j9j9j9j9j9j9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen four columns of email_messages from varchar to TEXT.
    # PostgreSQL stores varchar and TEXT identically; the ALTER does not
    # rewrite the table. Indexes and unique constraints survive untouched.
    op.alter_column(
        "email_messages",
        "subject",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "email_messages",
        "sender_name",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "email_messages",
        "message_id",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "email_messages",
        "thread_id",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )

    # New table: email_sync_errors
    op.create_table(
        "email_sync_errors",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "mailbox_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mailboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sync_history_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sync_history.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("sender", sa.String(length=255), nullable=True),
        sa.Column("error_type", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "severity",
            sa.String(length=20),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("resolution", sa.String(length=50), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_email_sync_errors_mailbox_status",
        "email_sync_errors",
        ["mailbox_id", "status"],
    )
    op.create_index(
        "ix_email_sync_errors_type_created",
        "email_sync_errors",
        ["error_type", "created_at"],
    )
    op.create_index(
        "ix_email_sync_errors_created_at",
        "email_sync_errors",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_sync_errors_created_at", table_name="email_sync_errors")
    op.drop_index("ix_email_sync_errors_type_created", table_name="email_sync_errors")
    op.drop_index("ix_email_sync_errors_mailbox_status", table_name="email_sync_errors")
    op.drop_table("email_sync_errors")

    op.alter_column(
        "email_messages",
        "thread_id",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "email_messages",
        "message_id",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=False,
    )
    op.alter_column(
        "email_messages",
        "sender_name",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "email_messages",
        "subject",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=False,
    )
