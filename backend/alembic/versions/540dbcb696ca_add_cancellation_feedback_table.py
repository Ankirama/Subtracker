"""Add cancellation_feedback table

Revision ID: 540dbcb696ca
Revises: 146748050f00
Create Date: 2025-11-19 21:45:28.734573

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "540dbcb696ca"
down_revision = "146748050f00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create FeedbackType enum if it doesn't exist
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE feedbacktype AS ENUM ('helpful', 'not_helpful', 'inaccurate', 'incomplete', 'worked', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """
    )

    # Create cancellation_feedback table
    op.create_table(
        "cancellation_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "provider_cancellation_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "feedback_type",
            postgresql.ENUM(
                "helpful",
                "not_helpful",
                "inaccurate",
                "incomplete",
                "worked",
                "failed",
                name="feedbacktype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("successfully_cancelled", sa.Boolean(), nullable=True),
        sa.Column("time_taken_minutes", sa.Integer(), nullable=True),
        sa.Column("helpfulness_rating", sa.Integer(), nullable=True),
        sa.Column("accuracy_rating", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "issues_encountered", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("ai_confidence_at_feedback", sa.Float(), nullable=True),
        sa.Column("validation_quality_at_feedback", sa.Float(), nullable=True),
        sa.Column("prompt_version_at_feedback", sa.String(length=50), nullable=True),
        sa.Column("device_type", sa.String(length=50), nullable=True),
        sa.Column("provider_name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["provider_cancellation_id"],
            ["provider_cancellation_info.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create index on provider_name for fast queries
    op.create_index(
        op.f("ix_cancellation_feedback_provider_name"),
        "cancellation_feedback",
        ["provider_name"],
        unique=False,
    )


def downgrade() -> None:
    # Drop table and indexes
    op.drop_index(
        op.f("ix_cancellation_feedback_provider_name"),
        table_name="cancellation_feedback",
    )
    op.drop_table("cancellation_feedback")

    # Drop enum type
    feedback_type_enum = postgresql.ENUM(name="feedbacktype")
    feedback_type_enum.drop(op.get_bind(), checkfirst=True)
