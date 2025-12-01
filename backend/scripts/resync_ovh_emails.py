#!/usr/bin/env python3
"""
Re-sync OVH emails to apply new service reference extraction.

This script:
1. Finds all OVH emails
2. Re-processes them with the new hybrid extraction
3. Updates subscriptions with service references
4. Maintains data integrity by not deleting existing records
"""

import sys
from pathlib import Path
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models import EmailMessage as EmailMessageModel, Subscription
from app.services.subscription_extractor import extract_subscription_data
from app.email_providers.base import EmailMessage
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database engine
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


async def resync_ovh_emails(provider_filter: str = "OVH", dry_run: bool = True):
    """
    Re-sync emails for a specific provider with new service reference extraction.

    Args:
        provider_filter: Provider name to filter (e.g., "OVH")
        dry_run: If True, only show what would be updated without making changes
    """
    db = SessionLocal()

    try:
        # Find all emails from this provider
        emails = (
            db.query(EmailMessageModel)
            .filter(EmailMessageModel.sender.ilike(f"%{provider_filter.lower()}%"))
            .order_by(EmailMessageModel.date.desc())
            .all()
        )

        logger.info(f"Found {len(emails)} emails from {provider_filter}")

        updated_count = 0
        new_refs_found = 0

        for email in emails:
            logger.info(f"\n{'='*70}")
            logger.info(f"Processing email: {email.subject}")
            logger.info(f"Date: {email.date}")
            logger.info(f"Linked subscriptions: {len(email.subscriptions)}")

            # Convert DB email to EmailMessage format
            email_msg = EmailMessage(
                id=email.message_id,
                subject=email.subject,
                sender=email.sender,
                sender_name=email.sender_name,
                recipients=[email.recipient],
                date=email.date,
                body_text=email.body_text or "",
                body_html=email.body_html or "",
                headers={},
                has_attachments=bool(email.attachments),
                folder=None,
            )

            # Re-extract with new hybrid approach
            extracted = await extract_subscription_data(email_msg, db)

            if extracted:
                metadata = extracted.get("extraction_metadata", {})
                service_refs = metadata.get("service_references", {})
                custom_label = extracted.get("custom_label")

                logger.info("Extraction results:")
                logger.info(f"  Custom label: {custom_label}")
                logger.info(f"  Service references: {service_refs}")
                logger.info(f"  Service type: {metadata.get('service_type')}")

                if service_refs:
                    new_refs_found += 1

                    if not dry_run:
                        # Update email's extraction metadata
                        email.extraction_metadata = metadata

                        # Update associated subscriptions if exist
                        if email.subscriptions:
                            for subscription in email.subscriptions:
                                # Merge service references into subscription metadata
                                sub_metadata = subscription.extraction_metadata or {}
                                sub_metadata.update(metadata)
                                subscription.extraction_metadata = sub_metadata

                                # Update custom label if better
                                if custom_label and not subscription.custom_label:
                                    subscription.custom_label = custom_label

                                logger.info(
                                    f"  ✅ Updated subscription {subscription.id}"
                                )
                                updated_count += 1

                        db.commit()
                        logger.info("  ✅ Saved to database")
                    else:
                        logger.info("  [DRY RUN] Would update with service references")
                else:
                    logger.info("  ℹ️  No service references extracted")
            else:
                logger.info("  ⚠️  Extraction returned None")

        logger.info(f"\n{'='*70}")
        logger.info("SUMMARY:")
        logger.info(f"  Total emails processed: {len(emails)}")
        logger.info(f"  Emails with service references: {new_refs_found}")
        logger.info(f"  Subscriptions updated: {updated_count}")

        if dry_run:
            logger.info("\n⚠️  DRY RUN MODE - No changes were saved")
            logger.info("Run with dry_run=False to apply changes")

    finally:
        db.close()


async def main():
    """Run the re-sync script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Re-sync emails with service reference extraction"
    )
    parser.add_argument(
        "--provider", default="OVH", help="Provider name to filter (default: OVH)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply changes (default is dry-run)",
    )

    args = parser.parse_args()

    logger.info("🚀 SERVICE REFERENCE RE-SYNC SCRIPT")
    logger.info("=" * 70)
    logger.info(f"Provider: {args.provider}")
    logger.info(f"Mode: {'APPLY CHANGES' if args.apply else 'DRY RUN'}")
    logger.info("=" * 70)

    await resync_ovh_emails(provider_filter=args.provider, dry_run=not args.apply)


if __name__ == "__main__":
    asyncio.run(main())
