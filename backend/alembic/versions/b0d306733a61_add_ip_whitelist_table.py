"""add_ip_whitelist_table

Revision ID: b0d306733a61
Revises: 8e2d92da35aa
Create Date: 2025-11-18 21:44:18.845629

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b0d306733a61"
down_revision = "8e2d92da35aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create IP whitelist table
    op.create_table(
        "ip_whitelist",
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("added_by_user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("ip_address"),
    )


def downgrade() -> None:
    # Drop IP whitelist table
    op.drop_table("ip_whitelist")
