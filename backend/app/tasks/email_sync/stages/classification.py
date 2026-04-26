"""STAGE 1 — Classification stage of the email-sync pipeline.

Filters out emails that already exist in ``EmailMessage`` (by
``Message-ID``), separates remaining new emails into "to-classify" vs
"system" buckets, dispatches a single batched call to the injected
``AIClassifier``, and persists ``EmailMessage`` rows for every new email.

Returns the per-batch artefacts the next stages need:
  - ``email_records``: ``[(provider_email, db_email_record), ...]`` for
    NEW emails.
  - ``existing_email_records``: ``[(provider_email, db_email_record), ...]``
    for emails that were already in the DB at fetch time.

Mirrors lines 250-316 of pre-Phase-8b ``_sync_mailbox_async``. Does NOT
commit (the orchestrator owns commit boundaries); does call
``db.flush()`` per row to obtain primary keys.
"""

import logging
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.email_message import EmailMessage
from app.models.mailbox import Mailbox
from app.services.email_filter import should_process_email
from app.services.email_pipeline_protocol import AIClassifier

logger = logging.getLogger(__name__)


async def classify_new_emails(
    db: Session,
    mailbox: Mailbox,
    emails: list,
    batch_num: int,
    *,
    classify_batch: AIClassifier,
) -> Tuple[List[tuple], List[tuple]]:
    """Stage 1: identify new emails, filter system messages, classify, persist.

    Args:
        db: SQLAlchemy session.
        mailbox: The mailbox being synced.
        emails: Provider-side ``EmailMessage`` dataclasses for this batch.
        batch_num: Current batch number (used in logging only).
        classify_batch: Injected ``AIClassifier`` callable, awaited for the
            batch of emails that pass the system-email filter.

    Returns:
        Tuple ``(email_records, existing_email_records)`` where each
        element is a list of ``(provider_email, EmailMessage_db_row)``
        pairs.
    """
    new_emails = []
    new_emails_to_classify = []
    existing_email_records = []

    for email in emails:
        message_id = email.headers.get("Message-ID", email.id)
        existing_email = (
            db.query(EmailMessage).filter(EmailMessage.message_id == message_id).first()
        )

        if not existing_email:
            new_emails.append(email)
            # Only add to classification if not a system email
            if should_process_email(email, db):
                new_emails_to_classify.append(email)
            else:
                logger.info(f"Skipping system email: {email.subject}")
        else:
            existing_email_records.append((email, existing_email))

    logger.info(
        f"Batch {batch_num}: {len(new_emails)} new emails, {len(existing_email_records)} existing emails"
    )

    # Classify all new emails in parallel
    classifications = []
    if new_emails_to_classify:
        logger.info(f"Classifying {len(new_emails_to_classify)} emails in parallel...")
        classifications = await classify_batch(new_emails_to_classify, db)

    # Save new emails to database with classification results
    email_records = []
    for email, classification in zip(new_emails, classifications):
        message_id = email.headers.get("Message-ID", email.id)
        email_record = EmailMessage(
            mailbox_id=mailbox.id,
            message_id=message_id,
            thread_id=email.headers.get("Thread-ID"),
            subject=email.subject,
            sender=email.sender,
            sender_name=email.sender_name,
            recipient=(
                email.recipients[0] if email.recipients else mailbox.email_address
            ),
            date=email.date,
            body_text=email.body_text,
            body_html=email.body_html,
            labels=[email.folder] if email.folder else None,
            attachments=None,
            is_subscription=classification.get("is_subscription", False),
            classification_confidence=classification.get("confidence", 0.0),
            classification_reasoning=classification,
        )
        db.add(email_record)
        db.flush()
        email_records.append((email, email_record))
        logger.info(
            f"Saved email to database: {email.subject} (subscription: {email_record.is_subscription})"
        )

    return email_records, existing_email_records
