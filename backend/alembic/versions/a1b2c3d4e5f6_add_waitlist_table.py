"""Add waitlist table

Revision ID: a1b2c3d4e5f6
Revises: e9477877620d
Create Date: 2025-12-06 18:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "e9477877620d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create waitlist table
    op.create_table(
        "waitlist",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("access_code", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(op.f("ix_waitlist_email"), "waitlist", ["email"], unique=True)
    op.create_index(op.f("ix_waitlist_status"), "waitlist", ["status"], unique=False)
    op.create_index(
        op.f("ix_waitlist_access_code"), "waitlist", ["access_code"], unique=True
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f("ix_waitlist_access_code"), table_name="waitlist")
    op.drop_index(op.f("ix_waitlist_status"), table_name="waitlist")
    op.drop_index(op.f("ix_waitlist_email"), table_name="waitlist")

    # Drop table
    op.drop_table("waitlist")
