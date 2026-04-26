"""Celery task definitions for the email-sync pipeline.

Hosts:
  - ``DatabaseTask``: Celery base class providing a per-task
    SQLAlchemy session.
  - ``sync_mailbox_emails``: the public Celery task that wraps
    ``orchestrator._sync_mailbox_async`` with retry policy, resume
    detection, and ``SyncHistory`` finalisation.
  - ``check_scheduled_syncs``: periodic scheduler entry-point used by
    Celery Beat (registered in ``app.celery_app``).

Task names are preserved verbatim
(``app.tasks.email_sync.sync_mailbox_emails`` and
``app.tasks.email_sync.check_scheduled_syncs``) so Celery's task
registry — and any in-flight messages — keep resolving.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict
from uuid import UUID

from celery import Task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.email_providers.gmail import GmailAuthError
from app.models.mailbox import Mailbox
from app.models.sync_history import SyncHistory

from .orchestrator import _sync_mailbox_async
from .status_reconciler import update_subscription_statuses

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """
    Base task with database session management.
    """

    _db: Session = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        """Close database session after task completion."""
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    base=DatabaseTask,
    bind=True,
    name="app.tasks.email_sync.sync_mailbox_emails",
    autoretry_for=(Exception,),  # Retry on any exception
    retry_kwargs={
        "max_retries": 3,
        "countdown": 60,
    },  # 3 retries with 60s initial delay
    retry_backoff=True,  # Exponential backoff (60s, 120s, 240s)
    retry_backoff_max=300,  # Max 5 minutes between retries
    retry_jitter=True,  # Add randomness to avoid thundering herd
)
def sync_mailbox_emails(
    self, mailbox_id: str, force_full_sync: bool = False, date_filter: str = None
) -> Dict[str, Any]:
    """
    Sync emails from a mailbox and detect subscriptions.

    Args:
        mailbox_id: UUID of the mailbox to sync
        force_full_sync: If True, ignore last_sync_at and sync all emails
        date_filter: Override mailbox date filter (e.g., '30days', '6months')

    Returns:
        Dict with sync results
    """
    db = self.db
    logger.info(f"Starting email sync for mailbox {mailbox_id}")

    # Fetch mailbox
    mailbox = db.query(Mailbox).filter(Mailbox.id == UUID(mailbox_id)).first()
    if not mailbox:
        logger.error(f"Mailbox {mailbox_id} not found")
        return {"success": False, "error": "Mailbox not found"}

    if not mailbox.is_active:
        logger.error(f"Mailbox {mailbox_id} is not active")
        return {"success": False, "error": "Mailbox is not active"}

    # Check for sync resume capability (Issue #7)
    # If there's a recent in_progress or cancelled sync (< 1 hour old), resume from last position
    resume_position = 0
    resume_batch_num = 0
    is_resuming = False

    if (
        mailbox.last_sync_status in ("in_progress", "cancelled")
        and mailbox.last_sync_started_at
    ):
        time_since_start = datetime.now(
            timezone.utc
        ) - mailbox.last_sync_started_at.replace(tzinfo=timezone.utc)

        if time_since_start.total_seconds() < 3600:  # Less than 1 hour old
            # Resume from last position
            resume_position = mailbox.last_sync_position or 0
            resume_batch_num = mailbox.last_sync_batch_num or 0
            is_resuming = True
            resume_reason = (
                "cancelled by user"
                if mailbox.last_sync_status == "cancelled"
                else "interrupted"
            )
            logger.info(
                f"Resuming sync from position {resume_position}, batch {resume_batch_num} "
                f"(was {resume_reason}, started {time_since_start.total_seconds():.0f}s ago)"
            )
        else:
            # Stale sync - restart from beginning
            logger.warning(
                f"Found stale {mailbox.last_sync_status} sync (started {time_since_start.total_seconds()/3600:.1f}h ago), "
                f"restarting from beginning"
            )

    # Set status to in_progress and update sync start time
    # For resuming syncs, use the original start time; for fresh syncs, use current time
    if is_resuming and mailbox.last_sync_started_at:
        sync_start_time = mailbox.last_sync_started_at.replace(tzinfo=timezone.utc)
        logger.info(f"Using original sync start time: {sync_start_time}")
    else:
        sync_start_time = datetime.now(timezone.utc)
        mailbox.last_sync_status = "in_progress"
        mailbox.last_sync_started_at = sync_start_time
        mailbox.last_sync_position = 0
        mailbox.last_sync_batch_num = 0
    mailbox.last_sync_error_message = None
    db.commit()

    # Create sync history entry (Issue #11)
    history_entry = SyncHistory(
        mailbox_id=mailbox.id,
        started_at=sync_start_time,
        status="in_progress",
        sync_type="full" if force_full_sync else "incremental",
        date_filter_used=date_filter or mailbox.import_date_filter,
        batch_size_used=mailbox.batch_size,
        was_resumed=is_resuming,
        resumed_from_position=resume_position if is_resuming else None,
        resumed_from_batch=resume_batch_num if is_resuming else None,
    )
    db.add(history_entry)
    db.commit()
    logger.info(f"Created sync history entry: {history_entry.id}")

    try:
        # Run async sync logic with resume position and sync start time
        result = asyncio.run(
            _sync_mailbox_async(
                db,
                mailbox,
                force_full_sync,
                date_filter,
                resume_position=resume_position,
                resume_batch_num=resume_batch_num,
                sync_start_time=sync_start_time,
                history_entry=history_entry,
            )
        )

        # Update mailbox sync status with metrics
        completion_time = datetime.now(timezone.utc)
        mailbox.last_sync_at = completion_time
        mailbox.last_sync_status = "success" if result["success"] else "failed"

        if result["success"]:
            # Update metrics on success
            mailbox.last_sync_emails_processed = result.get("total_emails_processed", 0)
            mailbox.last_sync_subscriptions_found = result.get(
                "subscriptions_found", 0
            ) + result.get("subscriptions_updated", 0)
            mailbox.last_sync_error_message = None

            # Clear sync resume fields on successful completion (Issue #7)
            mailbox.last_sync_position = 0
            mailbox.last_sync_batch_num = 0
            mailbox.last_sync_started_at = None

            # Clear progress tracking fields on completion (Issue #10)
            mailbox.current_batch_number = None
            mailbox.total_batches_estimate = None
            mailbox.progress_percentage = 100.0  # Set to 100% on completion
            mailbox.estimated_completion_time = None

            # Clear reconnect flags on successful sync (auth is working again)
            mailbox.needs_reconnect = False
            mailbox.auth_error_at = None
            mailbox.auth_error_message = None

            # Update history entry for successful completion (Issue #11)
            history_entry.status = "completed"
            history_entry.completed_at = completion_time
            history_entry.duration_seconds = int(
                (
                    completion_time
                    - history_entry.started_at.replace(tzinfo=timezone.utc)
                ).total_seconds()
            )
            history_entry.total_emails_processed = result.get(
                "total_emails_processed", 0
            )
            history_entry.subscriptions_found = result.get("subscriptions_found", 0)
            history_entry.subscriptions_updated = result.get("subscriptions_updated", 0)
            history_entry.batches_processed = mailbox.last_sync_batch_num or 0
            history_entry.final_position = mailbox.last_sync_position or 0
            history_entry.final_batch_number = mailbox.last_sync_batch_num or 0
            history_entry.final_progress_percentage = 100.0

            # Update subscription active/inactive status based on last confirmation dates
            status_update = update_subscription_statuses(db, mailbox.id)
            logger.info(
                f"Subscription status update: {status_update['activated']} activated, {status_update['deactivated']} deactivated"
            )
        else:
            # Store error message on failure
            error_msg = result.get("error", "Unknown error")
            mailbox.last_sync_error_message = error_msg

            # Update history entry for failure (Issue #11)
            history_entry.status = "failed"
            history_entry.completed_at = completion_time
            history_entry.duration_seconds = int(
                (
                    completion_time
                    - history_entry.started_at.replace(tzinfo=timezone.utc)
                ).total_seconds()
            )
            history_entry.total_emails_processed = result.get(
                "total_emails_processed", 0
            )
            history_entry.subscriptions_found = result.get("subscriptions_found", 0)
            history_entry.subscriptions_updated = result.get("subscriptions_updated", 0)
            history_entry.error_message = error_msg
            history_entry.error_type = result.get("error_type", "sync_error")

        db.commit()

        result.update(
            {
                "mailbox_id": mailbox_id,
                "sync_timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        logger.info(f"Email sync completed for mailbox {mailbox_id}: {result}")
        return result

    except GmailAuthError as e:
        # Handle Gmail authentication errors specifically
        logger.error(
            f"Gmail auth error for mailbox {mailbox_id}: {e.message} (needs_reconnect={e.needs_reconnect})"
        )
        exception_time = datetime.now(timezone.utc)

        # Set special auth_failed status and reconnect flags
        mailbox.last_sync_status = "auth_failed"
        mailbox.last_sync_at = exception_time
        mailbox.last_sync_error_message = e.message

        if e.needs_reconnect:
            mailbox.needs_reconnect = True
            mailbox.auth_error_at = exception_time
            mailbox.auth_error_message = e.message

        # Update history entry for auth failure
        history_entry.status = "failed"
        history_entry.completed_at = exception_time
        history_entry.duration_seconds = int(
            (
                exception_time - history_entry.started_at.replace(tzinfo=timezone.utc)
            ).total_seconds()
        )
        history_entry.error_message = e.message
        history_entry.error_type = "GmailAuthError"
        history_entry.total_emails_processed = mailbox.last_sync_emails_processed or 0
        history_entry.subscriptions_found = mailbox.last_sync_subscriptions_found or 0
        history_entry.batches_processed = mailbox.last_sync_batch_num or 0

        db.commit()

        # Don't retry auth errors - user needs to reconnect
        return {
            "success": False,
            "error": e.message,
            "needs_reconnect": e.needs_reconnect,
            "error_type": "auth_failed",
        }

    except Exception as e:
        logger.error(f"Email sync failed for mailbox {mailbox_id}: {str(e)}")
        exception_time = datetime.now(timezone.utc)
        mailbox.last_sync_status = "failed"
        mailbox.last_sync_at = exception_time
        mailbox.last_sync_error_message = str(e)

        # Update history entry for exception (Issue #11)
        history_entry.status = "failed"
        history_entry.completed_at = exception_time
        history_entry.duration_seconds = int(
            (
                exception_time - history_entry.started_at.replace(tzinfo=timezone.utc)
            ).total_seconds()
        )
        history_entry.error_message = str(e)
        history_entry.error_type = type(e).__name__
        history_entry.total_emails_processed = mailbox.last_sync_emails_processed or 0
        history_entry.subscriptions_found = mailbox.last_sync_subscriptions_found or 0
        history_entry.batches_processed = mailbox.last_sync_batch_num or 0

        db.commit()
        return {"success": False, "error": str(e)}


@celery_app.task(
    base=DatabaseTask,
    bind=True,
    name="app.tasks.email_sync.check_scheduled_syncs",
)
def check_scheduled_syncs(self) -> Dict[str, Any]:
    """
    Check for mailboxes that need automatic sync based on their sync_frequency.

    This task runs periodically (daily) and triggers sync for mailboxes where:
    - sync_frequency is 'daily' or 'weekly'
    - last_sync_at is older than the sync interval (or never synced)
    - Not currently syncing (status != 'in_progress' or 'queued')
    - Not needing reconnection (needs_reconnect = False)
    - Is active

    Returns:
        Dict with count of syncs triggered
    """
    db = self.db
    now = datetime.now(timezone.utc)
    syncs_triggered = 0
    skipped = []

    logger.info("Checking for scheduled mailbox syncs...")

    try:
        # Get all active mailboxes with automatic sync enabled
        mailboxes = (
            db.query(Mailbox)
            .filter(
                Mailbox.is_active.is_(True),
                Mailbox.needs_reconnect.is_(False),
                Mailbox.sync_frequency.in_(["daily", "weekly"]),
            )
            .all()
        )

        logger.info(f"Found {len(mailboxes)} mailboxes with automatic sync enabled")

        for mailbox in mailboxes:
            # Skip if already syncing
            if mailbox.last_sync_status in ["in_progress", "queued"]:
                skipped.append({"id": str(mailbox.id), "reason": "already_syncing"})
                continue

            # Calculate sync interval based on frequency
            if mailbox.sync_frequency == "daily":
                sync_interval = timedelta(days=1)
            elif mailbox.sync_frequency == "weekly":
                sync_interval = timedelta(days=7)
            else:
                continue  # Manual or unknown frequency

            # Check if sync is due
            if mailbox.last_sync_at is None:
                # Never synced - trigger sync
                needs_sync = True
            else:
                # Check if enough time has passed since last sync
                time_since_last_sync = now - mailbox.last_sync_at
                needs_sync = time_since_last_sync >= sync_interval

            if needs_sync:
                logger.info(
                    f"Triggering scheduled sync for mailbox {mailbox.id} "
                    f"({mailbox.email_address}, frequency={mailbox.sync_frequency})"
                )

                # Trigger async sync task
                sync_mailbox_emails.delay(str(mailbox.id), force_full_sync=False)
                syncs_triggered += 1
            else:
                time_until_next = sync_interval - (now - mailbox.last_sync_at)
                skipped.append(
                    {
                        "id": str(mailbox.id),
                        "reason": "not_due",
                        "next_sync_in": str(time_until_next),
                    }
                )

        logger.info(
            f"Scheduled sync check complete: {syncs_triggered} syncs triggered, "
            f"{len(skipped)} skipped"
        )

        return {
            "success": True,
            "syncs_triggered": syncs_triggered,
            "skipped": skipped,
        }

    except Exception as e:
        logger.error(f"Error in scheduled sync check: {str(e)}")
        return {"success": False, "error": str(e)}
