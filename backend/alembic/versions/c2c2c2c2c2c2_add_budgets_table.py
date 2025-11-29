"""Add budgets table

Revision ID: c2c2c2c2c2c2
Revises: b1b1b1b1b1b1
Create Date: 2025-01-17 14:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c2c2c2c2c2c2"
down_revision = "b1b1b1b1b1b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create budgets table
    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column(
            "period", sa.String(length=50), nullable=False, server_default="monthly"
        ),
        sa.Column("limit_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "currency", sa.String(length=3), nullable=False, server_default="EUR"
        ),
        sa.Column("alert_threshold", sa.Integer(), nullable=False, server_default="80"),
        sa.Column(
            "alert_enabled", sa.String(length=20), nullable=False, server_default="true"
        ),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(op.f("ix_budgets_id"), "budgets", ["id"], unique=False)
    op.create_index(op.f("ix_budgets_user_id"), "budgets", ["user_id"], unique=False)
    op.create_index(op.f("ix_budgets_category"), "budgets", ["category"], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f("ix_budgets_category"), table_name="budgets")
    op.drop_index(op.f("ix_budgets_user_id"), table_name="budgets")
    op.drop_index(op.f("ix_budgets_id"), table_name="budgets")

    # Drop table
    op.drop_table("budgets")
