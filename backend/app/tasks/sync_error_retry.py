"""Celery task stub for retrying skipped emails.

Full implementation lands in Task 12 — this stub exists so that Task 10's
user-facing retry endpoint has a real Celery task name to enqueue against.
The router calls ``retry_skipped_emails.delay(str(mailbox_id))`` and returns
the resulting task id. Tests patch the bound name in
``app.api.sync_errors`` to avoid actually running the Celery worker.
"""

from app.celery_app import celery_app


@celery_app.task(name="app.tasks.sync_error_retry.retry_skipped_emails")
def retry_skipped_emails(mailbox_id: str) -> dict:
    """Stub: replaced by full implementation in Task 12.

    Args:
        mailbox_id: stringified UUID of the mailbox whose pending sync
            errors should be retried.

    Returns:
        Diagnostic dict marking this as a stub invocation.
    """
    return {"success": True, "mailbox_id": mailbox_id, "stub": True}
