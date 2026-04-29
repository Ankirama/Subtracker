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

Per-email persistence is wrapped in a try/except so a single bad email
cannot crash the whole batch. Failures are classified, recorded as
``EmailSyncError`` rows, and the loop continues. Five consecutive
``unexpected`` errors trip a circuit breaker (raises
``SyncCircuitBreakerError``) so the orchestrator aborts the sync.

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
from app.services.sync_error_circuit_breaker import (
    CIRCUIT_BREAKER_THRESHOLD,
    SyncCircuitBreakerError,
)
from app.services.sync_error_classifier import classify_exception
from app.services.sync_error_recorder import (
    auto_recover_pending,
    record_sync_error,
)
from app.utils.string_truncate import truncate_to_bytes

logger = logging.getLogger(__name__)

_SUBJECT_MAX_BYTES = 4096
_SENDER_NAME_MAX_BYTES = 4096


async def classify_new_emails(
    db: Session,
    mailbox: Mailbox,
    emails: list,
    batch_num: int,
    *,
    classify_batch: AIClassifier,
    sync_history=None,
) -> Tuple[List[tuple], List[tuple]]:
    """Stage 1 (resilient): identify, classify, persist new emails.

    A failure on any single email is caught, classified, and recorded as
    an ``EmailSyncError`` row. The batch continues with the remaining
    emails.

    Five consecutive ``unexpected`` failures trip the circuit breaker —
    a ``SyncCircuitBreakerError`` is raised and the sync aborts. The
    orchestrator's outer scope handles propagation.

    Args:
        db: SQLAlchemy session.
        mailbox: The mailbox being synced.
        emails: Provider-side ``EmailMessage`` dataclasses for this batch.
        batch_num: Current batch number (used in logging only).
        classify_batch: Injected ``AIClassifier`` callable, awaited for the
            batch of emails that pass the system-email filter.
        sync_history: Optional ``SyncHistory`` row this sync belongs to;
            recorded errors will be linked to it.

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
        f"Batch {batch_num}: {len(new_emails)} new emails, "
        f"{len(existing_email_records)} existing emails"
    )

    # Classify all new emails in parallel
    classifications = []
    if new_emails_to_classify:
        logger.info(f"Classifying {len(new_emails_to_classify)} emails in parallel...")
        classifications = await classify_batch(new_emails_to_classify, db)

    # Per-email persistence with isolation
    email_records = []
    consecutive_unexpected = 0

    for email, classification in zip(new_emails, classifications):
        message_id = email.headers.get("Message-ID", email.id)
        try:
            email_record = EmailMessage(
                mailbox_id=mailbox.id,
                message_id=message_id,
                thread_id=email.headers.get("Thread-ID"),
                subject=truncate_to_bytes(email.subject, _SUBJECT_MAX_BYTES),
                sender=email.sender,
                sender_name=truncate_to_bytes(
                    email.sender_name, _SENDER_NAME_MAX_BYTES
                ),
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

            # Auto-recovery: a previously-pending error for this same
            # provider_message_id is now flagged resolved.
            auto_recover_pending(db, mailbox.id, message_id)

            consecutive_unexpected = 0
            logger.info(
                f"Saved email to database: {email.subject} "
                f"(subscription: {email_record.is_subscription})"
            )
        except Exception as exc:  # noqa: BLE001 — intentional broad catch
            db.rollback()
            error_type, severity = classify_exception(exc)
            raw_email_dict = {
                "message_id": message_id,
                "thread_id": email.headers.get("Thread-ID"),
                "subject": email.subject,
                "sender": email.sender,
                "sender_name": email.sender_name,
                "recipient": (
                    email.recipients[0] if email.recipients else mailbox.email_address
                ),
                "date": email.date.isoformat() if email.date else None,
                "labels": [email.folder] if email.folder else None,
            }
            record_sync_error(
                db=db,
                mailbox=mailbox,
                sync_history=sync_history,
                raw_email=raw_email_dict,
                exc=exc,
                error_type=error_type,
                severity=severity,
            )
            logger.warning(
                f"Skipped email {message_id} (error_type={error_type}): {exc}"
            )

            if error_type == "unexpected":
                consecutive_unexpected += 1
                if consecutive_unexpected >= CIRCUIT_BREAKER_THRESHOLD:
                    raise SyncCircuitBreakerError(
                        threshold=CIRCUIT_BREAKER_THRESHOLD,
                        error_count=consecutive_unexpected,
                    )

    return email_records, existing_email_records
