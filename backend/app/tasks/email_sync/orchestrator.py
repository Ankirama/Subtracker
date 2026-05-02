"""Top-level orchestrator for the async email-sync pipeline.

Hosts ``_sync_mailbox_async``, the inner coroutine consumed by the
``sync_mailbox_emails`` Celery task. The orchestrator owns:

  - Provider bootstrap (decrypt credentials, instantiate JMAP/Gmail
    provider, authenticate, close).
  - Date-filter resolution (delegates to
    ``..filters.parse_date_filter`` for explicit overrides).
  - Top-level batch loop: per-batch fetch + 3-stage pipeline +
    progress persistence + cancellation polling.
  - Commit boundaries — see the per-batch comments below for the
    contract: the Phase 1 chartests assert exact commit counts.

Pipeline stages live in ``..stages.{classification,extraction,persistence}``.
Per-stage helpers (renewal, cancellation suggestion, price history,
progress tracking) live in dedicated sibling modules.

Phase 8a interface seam: the three AI collaborators
(``classify_emails_batch``, ``extract_subscriptions_batch``,
``get_reference_extractor``) are imported at module level here AND
exposed as default parameter values on ``_sync_mailbox_async``.
Defaults are resolved at call time (not at function-definition time)
so monkeypatching the module attribute still works — the conftest
harness relies on this.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.email_providers import GmailProvider, JMAPProvider
from app.email_providers.gmail import GmailAuthError
from app.models.mailbox import Mailbox
from app.models.sync_history import SyncHistory
from app.security.encryption import decrypt_credentials

# AI pipeline collaborators — hoisted to module level via the interface seam
# defined in `app.services.email_pipeline_protocol`. The Protocols decouple
# this module's type contract from the concrete implementations, neutralising
# the `api -> tasks -> services` import-DAG triangle (audit finding A.1).
# Defaults are wired here; tests inject mocks via `_sync_mailbox_async`'s
# parameters instead of monkeypatching attributes on the source modules.
from app.services.ai_classifier import classify_emails_batch
from app.services.email_pipeline_protocol import (
    AIClassifier,
    ReferenceExtractorFactory,
    SubscriptionExtractor,
)
from app.services.reference_extractor import get_reference_extractor
from app.services.subscription_extractor import extract_subscriptions_batch

from .filters import parse_date_filter
from .progress_tracker import apply_batch_progress, finalise_cancelled_history
from .stages.classification import classify_new_emails
from .stages.extraction import extract_subscription_emails
from .stages.persistence import persist_subscriptions_for_batch

logger = logging.getLogger(__name__)


async def _sync_mailbox_async(
    db: Session,
    mailbox: Mailbox,
    force_full_sync: bool,
    date_filter: str,
    resume_position: int = 0,
    resume_batch_num: int = 0,
    sync_start_time: datetime = None,
    history_entry: "SyncHistory" = None,
    classify_batch: Optional[AIClassifier] = None,
    extract_batch: Optional[SubscriptionExtractor] = None,
    ref_extractor_factory: Optional[ReferenceExtractorFactory] = None,
) -> Dict[str, Any]:
    """
    Async implementation of email sync logic with resume capability.

    Args:
        db: Database session
        mailbox: Mailbox to sync
        force_full_sync: Whether to ignore last sync and fetch all
        date_filter: Optional date filter override
        resume_position: Position to resume from (for interrupted syncs)
        resume_batch_num: Batch number to resume from (for interrupted syncs)
        sync_start_time: Start time of the sync (for progress tracking)
        history_entry: Sync history entry to update on cancellation
        classify_batch: Async callable used to classify emails. Defaults to
            the module-level `classify_emails_batch` (resolved at call
            time so monkeypatching the module attribute still works).
            Tests inject mocks here to drive the inner pipeline without
            monkeypatching.
        extract_batch: Async callable used to extract subscription data
            from emails. Defaults to the module-level
            `extract_subscriptions_batch` (resolved at call time). Tests
            inject mocks here to drive the inner pipeline without
            monkeypatching.
        ref_extractor_factory: Factory returning a service-reference
            matcher compatible with `ReferenceExtractorProtocol`. Defaults
            to the module-level `get_reference_extractor` (resolved at
            call time). Tests inject mocks here to drive the dedup
            strategy.
    """
    # Resolve defaults at call time (not at function-definition time) so
    # `unittest.mock.patch("app.tasks.email_sync.<name>")` is still effective
    # — the conftest harness relies on this. Direct injection via the
    # parameters takes precedence.
    if classify_batch is None:
        classify_batch = classify_emails_batch
    if extract_batch is None:
        extract_batch = extract_subscriptions_batch
    if ref_extractor_factory is None:
        ref_extractor_factory = get_reference_extractor
    try:
        # Decrypt credentials
        credentials = decrypt_credentials(mailbox.encrypted_credentials)

        # Get email provider
        if mailbox.provider_type == "jmap":
            provider = JMAPProvider(credentials)
        elif mailbox.provider_type == "gmail":
            provider = GmailProvider(credentials)
        else:
            raise ValueError(f"Unsupported provider type: {mailbox.provider_type}")

        # Authenticate
        try:
            auth_success = await provider.authenticate()
            if not auth_success:
                return {"success": False, "error": "Authentication failed"}
        except GmailAuthError:
            # Re-raise to be handled by the caller with proper reconnect flag handling
            raise

        # Determine date filter - prioritize explicit date_filter parameter
        since_date = None
        if date_filter:
            # Use explicit date filter if provided (from UI or API call)
            filter_str = date_filter
            since_date = parse_date_filter(filter_str, db)
            logger.info(f"Using custom date filter: {filter_str} (since {since_date})")
        elif not force_full_sync and mailbox.last_sync_at:
            # Use last sync time for incremental updates
            since_date = mailbox.last_sync_at
            logger.info(f"Using last sync time: {since_date}")
        elif mailbox.import_date_filter:
            # Fall back to mailbox's default import filter
            filter_str = mailbox.import_date_filter
            since_date = parse_date_filter(filter_str, db)
            logger.info(
                f"Using mailbox default filter: {filter_str} (since {since_date})"
            )
        else:
            # No filter - fetch all emails
            since_date = None
            logger.info("No date filter - fetching all emails")

        # Pagination loop - fetch and process emails in batches
        # Resume from last position if resuming an interrupted sync
        position = resume_position
        has_more = True
        total_emails_processed = (
            mailbox.last_sync_emails_processed or 0
        )  # Resume from last count
        subscriptions_found = 0
        subscriptions_updated = 0
        batch_num = resume_batch_num

        if resume_position > 0:
            logger.info(
                f"Resuming paginated email fetch from position {position}, batch {batch_num}"
            )
        else:
            logger.info(f"Starting paginated email fetch since {since_date}")

        while has_more:
            batch_num += 1

            # Fetch batch of emails
            logger.info(
                f"Fetching batch {batch_num} (position {position}, batch_size {mailbox.batch_size})"
            )
            emails, has_more = await provider.fetch_messages(
                folder=None,
                since_date=since_date,
                limit=mailbox.batch_size,
                position=position,
            )

            batch_size = len(emails)
            logger.info(
                f"SYNC DEBUG - Fetched {batch_size} emails in batch {batch_num}, has_more={has_more}, current position={position}"
            )

            # Issue #9 fix: Safety check for empty batch (catches edge cases from pagination heuristics)
            if batch_size == 0:
                logger.info(
                    "SYNC DEBUG - No more emails to fetch (batch_size=0), breaking loop (Issue #9 safety net)"
                )
                break

            logger.info(
                f"SYNC DEBUG - Loop state BEFORE processing: has_more={has_more}, position={position}, batch_num={batch_num}"
            )

            # STAGE 1: Parallel Classification
            email_records, existing_email_records = await classify_new_emails(
                db,
                mailbox,
                emails,
                batch_num,
                classify_batch=classify_batch,
                sync_history=history_entry,
            )

            # STAGE 2: Parallel Extraction for subscription emails
            (
                subscription_email_records,
                subscription_data_list,
            ) = await extract_subscription_emails(
                db,
                email_records,
                existing_email_records,
                extract_batch=extract_batch,
            )

            # STAGE 3: Process subscription data and save to database
            # CRITICAL: per-email commit/rollback boundaries live inside this
            # call — see stages/persistence.py docstring.
            subscriptions_found, subscriptions_updated = (
                persist_subscriptions_for_batch(
                    db,
                    mailbox,
                    subscription_email_records,
                    subscription_data_list,
                    subscriptions_found=subscriptions_found,
                    subscriptions_updated=subscriptions_updated,
                    ref_extractor_factory=ref_extractor_factory,
                    sync_history_id=history_entry.id if history_entry else None,
                )
            )

            # Update counters after processing batch
            total_emails_processed += batch_size
            position += batch_size

            logger.info(
                f"SYNC DEBUG - Updated position to {position}, total_emails_processed={total_emails_processed}"
            )

            # Update sync progress in database (Issue #7: Sync resume capability)
            apply_batch_progress(
                mailbox,
                sync_start_time=sync_start_time,
                total_emails_processed=total_emails_processed,
                subscriptions_found=subscriptions_found,
                position=position,
                batch_num=batch_num,
                has_more=has_more,
            )

            db.commit()

            # Check for user-initiated cancellation after each batch
            db.refresh(mailbox)
            if mailbox.sync_cancellation_requested:
                logger.info(
                    f"Sync cancellation requested by user at batch {batch_num}. Stopping gracefully."
                )

                finalise_cancelled_history(
                    mailbox,
                    history_entry,
                    total_emails_processed=total_emails_processed,
                    subscriptions_found=subscriptions_found,
                    subscriptions_updated=subscriptions_updated,
                    batch_num=batch_num,
                    position=position,
                )

                db.commit()

                # Break out of the loop gracefully - progress is already saved
                return {
                    "success": True,
                    "cancelled": True,
                    "total_emails_processed": total_emails_processed,
                    "subscriptions_found": subscriptions_found,
                    "subscriptions_updated": subscriptions_updated,
                    "message": f"Sync cancelled by user at batch {batch_num}",
                }

            logger.info(
                f"Completed batch {batch_num}: {total_emails_processed} total emails processed, {subscriptions_found} subscriptions found"
            )
            logger.info(
                f"SYNC DEBUG - Loop state at END of iteration: has_more={has_more}, position={position}, will_continue={has_more}"
            )

            # Continue to next batch if has_more is True

        # Close provider connection
        await provider.close()

        return {
            "success": True,
            "total_emails_processed": total_emails_processed,
            "subscriptions_found": subscriptions_found,
            "subscriptions_updated": subscriptions_updated,
        }

    except Exception as e:
        logger.error(f"Error in async sync: {str(e)}")
        raise
