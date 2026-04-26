"""Progress tracking for the email-sync orchestrator.

Encapsulates the per-batch progress field updates on the ``Mailbox`` row
and the cancellation finalisation of the ``SyncHistory`` entry. Helpers
mutate ORM instances but DO NOT commit — the orchestrator owns the
commit boundaries (this is mandatory: the Phase 1 ``commit_rollback_counter``
chartests assert the number of commits per batch).

The two extracted helpers correspond to the two distinct mutation regions
inside ``_sync_mailbox_async`` lines 706-803 (pre-Phase-8b numbering):

  - ``apply_batch_progress``: lines 706-755 — counters + mailbox progress
    fields (current_batch_number, total_batches_estimate, etc.).
  - ``finalise_cancelled_history``: lines 765-783 — mailbox status fields
    + history-entry mutation when the user has requested cancellation.

The orchestrator still owns:
  - The ``db.commit()`` after ``apply_batch_progress`` (was line 757).
  - The ``db.refresh(mailbox)`` BEFORE the cancellation check (was line 760).
  - The ``db.commit()`` after ``finalise_cancelled_history`` (was line 785).
  - The early ``return`` from the cancellation arm.
"""

from datetime import datetime, timezone, timedelta

from app.models.mailbox import Mailbox
from app.models.sync_history import SyncHistory


def apply_batch_progress(
    mailbox: Mailbox,
    *,
    sync_start_time: datetime,
    total_emails_processed: int,
    subscriptions_found: int,
    position: int,
    batch_num: int,
    has_more: bool,
) -> None:
    """Update mailbox progress fields after a batch completes.

    Mirrors the inline block previously at ``_sync_mailbox_async`` lines
    706-755. Does NOT commit; the caller commits exactly once after this
    helper plus any other in-batch mutations.
    """
    # Persist position and batch_num so sync can resume if interrupted (Issue #7)
    mailbox.last_sync_emails_processed = total_emails_processed
    mailbox.last_sync_subscriptions_found = subscriptions_found
    mailbox.last_sync_position = position
    mailbox.last_sync_batch_num = batch_num

    # Update real-time progress tracking (Issue #10)
    # Estimate total batches based on has_more flag
    # If has_more=True, we estimate at least 2 more batches, otherwise this is the last
    estimated_remaining_batches = 2 if has_more else 0
    total_batches_estimate = batch_num + estimated_remaining_batches

    # Calculate progress percentage
    progress_percentage = (
        (batch_num / total_batches_estimate * 100)
        if total_batches_estimate > 0
        else 100.0
    )

    # Calculate estimated completion time based on average batch duration
    elapsed_time = datetime.now(timezone.utc) - sync_start_time
    avg_time_per_batch = (
        elapsed_time.total_seconds() / batch_num if batch_num > 0 else 0
    )
    estimated_remaining_seconds = avg_time_per_batch * estimated_remaining_batches
    estimated_completion_time = (
        datetime.now(timezone.utc) + timedelta(seconds=estimated_remaining_seconds)
        if has_more
        else None
    )

    # Update progress fields
    mailbox.current_batch_number = batch_num
    mailbox.total_batches_estimate = total_batches_estimate
    mailbox.progress_percentage = min(
        progress_percentage, 99.0
    )  # Cap at 99% until actually done
    mailbox.estimated_completion_time = estimated_completion_time


def finalise_cancelled_history(
    mailbox: Mailbox,
    history_entry: SyncHistory,
    *,
    total_emails_processed: int,
    subscriptions_found: int,
    subscriptions_updated: int,
    batch_num: int,
    position: int,
) -> None:
    """Finalise mailbox + history rows when user-initiated cancellation fires.

    Mirrors the inline block previously at ``_sync_mailbox_async`` lines
    765-783 (Issue #11). Does NOT commit; the caller commits exactly once
    after this helper.
    """
    mailbox.last_sync_status = "cancelled"
    mailbox.sync_cancelled_at = datetime.now(timezone.utc)
    mailbox.sync_cancellation_requested = False  # Reset flag

    # Update history entry for cancellation (Issue #11)
    history_entry.status = "cancelled"
    history_entry.completed_at = datetime.now(timezone.utc)
    history_entry.duration_seconds = int(
        (history_entry.completed_at - history_entry.started_at).total_seconds()
    )
    history_entry.total_emails_processed = total_emails_processed
    history_entry.subscriptions_found = subscriptions_found
    history_entry.subscriptions_updated = subscriptions_updated
    history_entry.batches_processed = batch_num
    history_entry.final_position = position
    history_entry.final_batch_number = batch_num
    history_entry.final_progress_percentage = mailbox.progress_percentage
