"""Admin-only endpoints for cross-mailbox sync error oversight.

Three endpoints, all gated by ``get_current_admin_user``:

* ``GET  /api/admin/sync-errors`` — paginated cross-mailbox list with
  optional ``error_type``/``severity``/``status``/``mailbox_id`` filters.
  Response includes ``raw_payload`` and ``stack_trace`` for debugging.
* ``GET  /api/admin/sync-errors/{error_id}`` — single error detail
  (admin view exposing all fields).
* ``POST /api/admin/sync-errors/{error_id}/resolve`` — mark the error as
  ``resolved`` with ``resolution="admin_resolved"`` and stamp the admin
  on ``resolved_by_id`` / ``resolved_at``.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.email_sync_error import EmailSyncError
from app.models.user import User
from app.schemas.sync_error import (
    SyncErrorAdminListOut,
    SyncErrorAdminOut,
)
from app.security.dependencies import get_current_admin_user

router = APIRouter(prefix="/api/admin", tags=["admin", "sync-errors"])


@router.get("/sync-errors", response_model=SyncErrorAdminListOut)
def list_admin_sync_errors(
    error_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    mailbox_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> SyncErrorAdminListOut:
    """List sync errors across all mailboxes, paginated and filterable."""
    q = db.query(EmailSyncError)
    if error_type:
        q = q.filter(EmailSyncError.error_type == error_type)
    if severity:
        q = q.filter(EmailSyncError.severity == severity)
    if status_filter:
        q = q.filter(EmailSyncError.status == status_filter)
    if mailbox_id:
        q = q.filter(EmailSyncError.mailbox_id == mailbox_id)

    total = q.count()
    items = (
        q.order_by(EmailSyncError.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return SyncErrorAdminListOut(
        items=[SyncErrorAdminOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sync-errors/{error_id}", response_model=SyncErrorAdminOut)
def get_admin_sync_error(
    error_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> SyncErrorAdminOut:
    """Return a single sync error with all admin-visible fields."""
    err = db.query(EmailSyncError).filter(EmailSyncError.id == error_id).first()
    if err is None:
        raise HTTPException(status_code=404, detail="Sync error not found")
    return SyncErrorAdminOut.model_validate(err)


@router.post("/sync-errors/{error_id}/resolve", response_model=SyncErrorAdminOut)
def resolve_admin_sync_error(
    error_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> SyncErrorAdminOut:
    """Mark a sync error as resolved by the acting admin."""
    err = db.query(EmailSyncError).filter(EmailSyncError.id == error_id).first()
    if err is None:
        raise HTTPException(status_code=404, detail="Sync error not found")
    err.status = "resolved"
    err.resolution = "admin_resolved"
    err.resolved_at = datetime.now(timezone.utc)
    err.resolved_by_id = admin.id
    db.commit()
    db.refresh(err)
    return SyncErrorAdminOut.model_validate(err)
