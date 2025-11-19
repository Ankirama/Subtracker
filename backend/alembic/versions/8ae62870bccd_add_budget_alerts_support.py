"""add_budget_alerts_support

Revision ID: 8ae62870bccd
Revises: b0d306733a61
Create Date: 2025-11-19 00:39:03.556240

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8ae62870bccd'
down_revision = 'b0d306733a61'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create notification type enum if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationtype') THEN
                CREATE TYPE notificationtype AS ENUM (
                    'RENEWAL_REMINDER',
                    'TRIAL_ENDING',
                    'WEEKLY_SUMMARY',
                    'MONTHLY_SUMMARY',
                    'INACTIVE_SUBSCRIPTION',
                    'PRICE_CHANGE',
                    'BUDGET_ALERT',
                    'SYSTEM_ANNOUNCEMENT'
                );
            ELSE
                -- If enum exists but doesn't have BUDGET_ALERT, add it
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum
                    WHERE enumtypid = 'notificationtype'::regtype
                    AND enumlabel = 'BUDGET_ALERT'
                ) THEN
                    ALTER TYPE notificationtype ADD VALUE 'BUDGET_ALERT';
                END IF;
            END IF;
        END$$;
    """)

    # Create notification priority enum if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationpriority') THEN
                CREATE TYPE notificationpriority AS ENUM ('LOW', 'MEDIUM', 'HIGH');
            END IF;
        END$$;
    """)

    # Convert type column to enum if it's still VARCHAR
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'notifications'
                AND column_name = 'type'
                AND data_type = 'character varying'
            ) THEN
                ALTER TABLE notifications
                ALTER COLUMN type TYPE notificationtype USING type::notificationtype;
            END IF;
        END$$;
    """)

    # Convert priority column to enum if it's still VARCHAR
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'notifications'
                AND column_name = 'priority'
                AND data_type = 'character varying'
            ) THEN
                ALTER TABLE notifications
                ALTER COLUMN priority TYPE notificationpriority USING priority::notificationpriority;
            END IF;
        END$$;
    """)

    # Add related_budget_id column to notifications table if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='notifications'
                AND column_name='related_budget_id'
            ) THEN
                ALTER TABLE notifications
                ADD COLUMN related_budget_id UUID;

                ALTER TABLE notifications
                ADD CONSTRAINT notifications_related_budget_id_fkey
                FOREIGN KEY (related_budget_id)
                REFERENCES budgets(id)
                ON DELETE CASCADE;
            END IF;
        END$$;
    """)


def downgrade() -> None:
    # Remove related_budget_id column
    op.execute("""
        ALTER TABLE notifications DROP COLUMN IF EXISTS related_budget_id CASCADE;
    """)

    # Note: Cannot easily remove enum value in PostgreSQL
    # BUDGET_ALERT value will remain in the enum
