"""User-facing endpoints for email sync errors.

Three endpoints, all scoped to the authenticated user via ``user_id``
filtering on the parent mailbox:

* ``GET  /api/mailboxes/{mailbox_id}/sync-errors`` — paginated list,
  PII-safe (no ``raw_payload`` or ``stack_trace`` exposure).
* ``POST /api/sync-errors/{error_id}/ignore`` — idempotent dismiss.
* ``POST /api/mailboxes/{mailbox_id}/sync-errors/retry`` — enqueue a
  Celery retry task for all ``pending`` errors of that mailbox.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.email_sync_error import EmailSyncError
from app.models.mailbox import Mailbox
from app.models.user import User
from app.schemas.sync_error import (
    RetryResponseOut,
    SyncErrorListOut,
    SyncErrorOut,
)
from app.security.dependencies import get_current_user
from app.tasks.sync_error_retry import retry_skipped_emails

router = APIRouter(prefix="/api", tags=["sync-errors"])


def _get_user_mailbox(mailbox_id: UUID, db: Session, current_user: User) -> Mailbox:
    """Fetch a mailbox owned by ``current_user`` or raise 404."""
    mb = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == current_user.id)
        .first()
    )
    if mb is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    return mb


def _get_user_error(error_id: UUID, db: Session, current_user: User) -> EmailSyncError:
    """Fetch a sync error whose mailbox is owned by ``current_user`` or raise 404."""
    err = (
        db.query(EmailSyncError)
        .join(Mailbox, Mailbox.id == EmailSyncError.mailbox_id)
        .filter(
            EmailSyncError.id == error_id,
            Mailbox.user_id == current_user.id,
        )
        .first()
    )
    if err is None:
        raise HTTPException(status_code=404, detail="Sync error not found")
    return err


@router.get(
    "/mailboxes/{mailbox_id}/sync-errors",
    response_model=SyncErrorListOut,
)
def list_sync_errors(
    mailbox_id: UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    error_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncErrorListOut:
    """List sync errors for a mailbox, paginated and ordered by ``created_at desc``."""
    _get_user_mailbox(mailbox_id, db, current_user)

    q = db.query(EmailSyncError).filter(EmailSyncError.mailbox_id == mailbox_id)
    if status_filter:
        q = q.filter(EmailSyncError.status == status_filter)
    if error_type:
        q = q.filter(EmailSyncError.error_type == error_type)

    total = q.count()
    items = (
        q.order_by(EmailSyncError.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return SyncErrorListOut(
        items=[SyncErrorOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/sync-errors/{error_id}/ignore", response_model=SyncErrorOut)
def ignore_sync_error(
    error_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncErrorOut:
    """Mark a sync error as ignored. Idempotent — already-ignored errors are returned as-is."""
    err = _get_user_error(error_id, db, current_user)
    if err.status == "ignored":
        return SyncErrorOut.model_validate(err)
    err.status = "ignored"
    err.resolution = "user_ignored"
    err.resolved_at = datetime.now(timezone.utc)
    err.resolved_by_id = current_user.id
    db.commit()
    db.refresh(err)
    return SyncErrorOut.model_validate(err)


@router.post(
    "/mailboxes/{mailbox_id}/sync-errors/retry",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RetryResponseOut,
)
def retry_sync_errors(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RetryResponseOut:
    """Enqueue a Celery retry task for all pending errors on the mailbox.

    Returns 400 if no errors are in ``pending`` status.
    """
    mb = _get_user_mailbox(mailbox_id, db, current_user)
    pending_count = (
        db.query(EmailSyncError)
        .filter(
            EmailSyncError.mailbox_id == mb.id,
            EmailSyncError.status == "pending",
        )
        .count()
    )
    if pending_count == 0:
        raise HTTPException(status_code=400, detail="No pending errors to retry")
    task = retry_skipped_emails.delay(str(mb.id))
    return RetryResponseOut(task_id=task.id, pending_count=pending_count)
