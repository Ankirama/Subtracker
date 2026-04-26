"""STAGE 2 — Subscription-data extraction stage of the email-sync pipeline.

Decides which emails need subscription extraction:
  - All NEW emails classified as subscriptions are always extracted.
  - EXISTING emails classified as subscriptions are extracted only when
    they are NOT already linked to a subscription via the
    ``subscription_emails`` association table (extraction is cached on
    re-sync to avoid redundant API calls).

Then dispatches a single batched call to the injected
``SubscriptionExtractor``.

Mirrors lines 318-369 of pre-Phase-8b ``_sync_mailbox_async``. Does NOT
commit; does NOT mutate ORM state (only reads).
"""

import logging
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.email_message import subscription_emails
from app.services.email_pipeline_protocol import SubscriptionExtractor

logger = logging.getLogger(__name__)


async def extract_subscription_emails(
    db: Session,
    email_records: List[tuple],
    existing_email_records: List[tuple],
    *,
    extract_batch: SubscriptionExtractor,
) -> Tuple[List[tuple], List]:
    """Stage 2: select subscription emails needing extraction; run extractor.

    Args:
        db: SQLAlchemy session.
        email_records: ``[(provider_email, EmailMessage_db_row), ...]`` for
            NEW emails (output of stage 1).
        existing_email_records: same shape for emails that were already in
            the DB at fetch time.
        extract_batch: Injected ``SubscriptionExtractor`` callable.

    Returns:
        Tuple ``(subscription_email_records, subscription_data_list)``
        where the lists are aligned: ``subscription_data_list[i]`` is the
        AI extraction (or ``None``) for the email at
        ``subscription_email_records[i]``.
    """
    subscription_emails_to_extract = []
    subscription_email_records = []
    skipped_count = 0

    # Add newly classified subscription emails (always need extraction)
    new_subscription_count = 0
    for email, email_record in email_records:
        if email_record.is_subscription:
            subscription_emails_to_extract.append(email)
            subscription_email_records.append((email, email_record))
            new_subscription_count += 1

    # For existing subscription emails, only extract if not already linked to a subscription
    # This avoids redundant API calls for emails that have already been processed
    existing_subscription_count = 0
    for email, email_record in existing_email_records:
        if email_record.is_subscription:
            existing_subscription_count += 1

            # Check if this email is already linked to a subscription (extraction already done)
            existing_link = db.execute(
                subscription_emails.select().where(
                    subscription_emails.c.email_id == email_record.id
                )
            ).first()

            if not existing_link:
                # No existing link - needs extraction
                subscription_emails_to_extract.append(email)
                subscription_email_records.append((email, email_record))
                logger.info(f"Existing email needs extraction: {email.subject}")
            else:
                skipped_count += 1
                logger.debug(
                    f"Skipping extraction for already-linked email: {email.subject}"
                )

    logger.info(
        f"Subscription emails: {new_subscription_count} new, {existing_subscription_count} existing "
        f"({len(subscription_emails_to_extract)} need extraction, {skipped_count} cached)"
    )

    # Extract subscription data in parallel
    subscription_data_list = []
    if subscription_emails_to_extract:
        logger.info(
            f"Extracting {len(subscription_emails_to_extract)} subscription emails in parallel..."
        )
        subscription_data_list = await extract_batch(subscription_emails_to_extract, db)

    return subscription_email_records, subscription_data_list
