"""Add admin functionality

Revision ID: b1b1b1b1b1b1
Revises: 0e9af29b93e6
Create Date: 2025-11-16 21:45:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b1b1b1b1b1b1"
down_revision = "0e9af29b93e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_admin column to users table
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_users_is_admin", "users", ["is_admin"])

    # Create admin_settings table
    op.create_table(
        "admin_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(), nullable=False, unique=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("value_type", sa.String(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_admin_settings_key", "admin_settings", ["key"])
    op.create_index("ix_admin_settings_category", "admin_settings", ["category"])

    # Create admin_audit_logs table
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_admin_audit_logs_user_id", "admin_audit_logs", ["user_id"])
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])
    op.create_index(
        "ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"]
    )

    # Create application_logs table
    op.create_table(
        "application_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("level", sa.String(), nullable=False),
        sa.Column("logger_name", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("module", sa.String(), nullable=True),
        sa.Column("function_name", sa.String(), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("exception_type", sa.String(), nullable=True),
        sa.Column("exception_message", sa.Text(), nullable=True),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_application_logs_level", "application_logs", ["level"])
    op.create_index(
        "ix_application_logs_created_at", "application_logs", ["created_at"]
    )
    op.create_index(
        "ix_application_logs_logger_name", "application_logs", ["logger_name"]
    )

    # Create security_events table
    op.create_table(
        "security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_security_events_event_type", "security_events", ["event_type"])
    op.create_index("ix_security_events_created_at", "security_events", ["created_at"])
    op.create_index("ix_security_events_severity", "security_events", ["severity"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index("ix_security_events_severity", table_name="security_events")
    op.drop_index("ix_security_events_created_at", table_name="security_events")
    op.drop_index("ix_security_events_event_type", table_name="security_events")
    op.drop_table("security_events")

    op.drop_index("ix_application_logs_logger_name", table_name="application_logs")
    op.drop_index("ix_application_logs_created_at", table_name="application_logs")
    op.drop_index("ix_application_logs_level", table_name="application_logs")
    op.drop_table("application_logs")

    op.drop_index("ix_admin_audit_logs_created_at", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_action", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_user_id", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")

    op.drop_index("ix_admin_settings_category", table_name="admin_settings")
    op.drop_index("ix_admin_settings_key", table_name="admin_settings")
    op.drop_table("admin_settings")

    # Remove is_admin column from users
    op.drop_index("ix_users_is_admin", table_name="users")
    op.drop_column("users", "is_admin")
