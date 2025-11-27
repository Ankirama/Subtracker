"""
Cleanup script for duplicate subscriptions.

Finds and merges duplicate subscriptions based on stable fields:
- mailbox_id
- provider
- amount
- billing_cycle
- email_sender

Keeps the oldest subscription and migrates all email relationships.
"""

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models.subscription import Subscription
from app.models.email_message import subscription_emails
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database connection
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def find_duplicate_groups(db):
    """
    Find groups of duplicate subscriptions based on stable fields.

    Returns:
        List of tuples: (mailbox_id, provider, amount, billing_cycle, email_sender, count)
    """
    duplicates = (
        db.query(
            Subscription.mailbox_id,
            Subscription.provider,
            Subscription.amount,
            Subscription.billing_cycle,
            Subscription.email_sender,
            func.count(Subscription.id).label("count"),
        )
        .group_by(
            Subscription.mailbox_id,
            Subscription.provider,
            Subscription.amount,
            Subscription.billing_cycle,
            Subscription.email_sender,
        )
        .having(func.count(Subscription.id) > 1)
        .all()
    )

    return duplicates


def merge_duplicate_subscriptions(
    db, mailbox_id, provider, amount, billing_cycle, email_sender
):
    """
    Merge duplicate subscriptions for a given composite key.

    Strategy:
    1. Find all subscriptions matching the key
    2. Keep the oldest one (earliest created_at)
    3. Migrate all email relationships to the kept subscription
    4. Delete the duplicate subscriptions

    Returns:
        Dict with merge statistics
    """
    # Find all subscriptions matching this key
    subscriptions = (
        db.query(Subscription)
        .filter(
            Subscription.mailbox_id == mailbox_id,
            Subscription.provider == provider,
            Subscription.amount == amount,
            Subscription.billing_cycle == billing_cycle,
            Subscription.email_sender == email_sender,
        )
        .order_by(Subscription.created_at)
        .all()
    )

    if len(subscriptions) <= 1:
        logger.info(f"No duplicates found for {provider}")
        return {"merged": 0, "kept": None, "deleted": []}

    # Keep the oldest subscription
    kept_subscription = subscriptions[0]
    duplicate_subscriptions = subscriptions[1:]

    logger.info(
        f"Merging {len(duplicate_subscriptions)} duplicates for {provider} (keeping {kept_subscription.id})"
    )

    deleted_ids = []
    migrated_emails = 0

    for dup in duplicate_subscriptions:
        # Migrate email relationships
        email_relationships = db.execute(
            subscription_emails.select().where(
                subscription_emails.c.subscription_id == dup.id
            )
        ).fetchall()

        for rel in email_relationships:
            # Check if relationship already exists for kept subscription
            existing = db.execute(
                subscription_emails.select().where(
                    subscription_emails.c.subscription_id == kept_subscription.id,
                    subscription_emails.c.email_id == rel.email_id,
                )
            ).first()

            if not existing:
                # Create relationship for kept subscription
                db.execute(
                    subscription_emails.insert().values(
                        subscription_id=kept_subscription.id,
                        email_id=rel.email_id,
                        extraction_role=rel.extraction_role,
                        extraction_data=rel.extraction_data,
                    )
                )
                migrated_emails += 1

            # Delete old relationship
            db.execute(
                subscription_emails.delete().where(
                    subscription_emails.c.subscription_id == dup.id,
                    subscription_emails.c.email_id == rel.email_id,
                )
            )

        # Delete duplicate subscription
        db.delete(dup)
        deleted_ids.append(str(dup.id))
        logger.info(f"Deleted duplicate subscription {dup.id}")

    # Update kept subscription's updated_at timestamp
    kept_subscription.updated_at = datetime.utcnow()

    db.commit()

    return {
        "merged": len(duplicate_subscriptions),
        "kept": str(kept_subscription.id),
        "deleted": deleted_ids,
        "migrated_emails": migrated_emails,
    }


def main():
    """
    Main cleanup function.
    """
    db = SessionLocal()

    try:
        logger.info("Starting duplicate subscription cleanup...")

        # Find duplicate groups
        duplicate_groups = find_duplicate_groups(db)

        if not duplicate_groups:
            logger.info("No duplicates found!")
            return

        logger.info(f"Found {len(duplicate_groups)} duplicate groups")

        total_merged = 0
        total_deleted = 0
        total_migrated_emails = 0

        # Process each duplicate group
        for group in duplicate_groups:
            mailbox_id, provider, amount, billing_cycle, email_sender, count = group
            logger.info(
                f"\nProcessing duplicate group: {provider} (€{amount}/{billing_cycle}) - {count} subscriptions"
            )

            result = merge_duplicate_subscriptions(
                db, mailbox_id, provider, amount, billing_cycle, email_sender
            )

            total_merged += result["merged"]
            total_deleted += len(result["deleted"])
            total_migrated_emails += result["migrated_emails"]

            logger.info(f"Kept: {result['kept']}")
            logger.info(f"Deleted: {', '.join(result['deleted'])}")
            logger.info(f"Migrated {result['migrated_emails']} email relationships")

        logger.info(f"\n{'='*60}")
        logger.info("Cleanup complete!")
        logger.info(f"Total duplicate groups processed: {len(duplicate_groups)}")
        logger.info(f"Total subscriptions merged: {total_merged}")
        logger.info(f"Total subscriptions deleted: {total_deleted}")
        logger.info(f"Total email relationships migrated: {total_migrated_emails}")
        logger.info(f"{'='*60}")

    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
