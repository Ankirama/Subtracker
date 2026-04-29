"""Persistence layer for email sync errors.

The single writer of ``email_sync_errors`` rows. Callers are the per-email
try/except in the email-sync pipeline (``stages/classification.py``) and the
retry task (``tasks/sync_error_retry.py``).

Contract:
- The caller has already issued ``db.rollback()`` before calling
  ``record_sync_error`` so the session is clean.
- Idempotent on
  ``(mailbox_id, provider_message_id, sync_history_id, error_type)``: if a
  matching row already exists, it is updated (retry_count++) and returned
  unchanged otherwise.
- ``unexpected`` errors are mirrored to ``application_logs`` at
  ``level='ERROR'`` so admins see them in the existing log viewer.
"""

import json
import logging
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.email_sync_error import EmailSyncError
from app.models.mailbox import Mailbox
from app.models.sync_history import SyncHistory
from app.utils.string_truncate import truncate_to_bytes
from app.models.admin import ApplicationLog

logger = logging.getLogger(__name__)

_SUBJECT_MAX_BYTES = 4096
_RAW_PAYLOAD_MAX_BYTES = 16_384


def record_sync_error(
    db: Session,
    mailbox: Mailbox,
    sync_history: Optional[SyncHistory],
    raw_email: Dict[str, Any],
    exc: Exception,
    error_type: str,
    severity: str,
) -> EmailSyncError:
    """Persist (or update) an ``EmailSyncError`` row for one failed email."""
    provider_message_id = raw_email.get("message_id")
    sync_history_id = sync_history.id if sync_history else None

    # Idempotent lookup
    existing = (
        db.query(EmailSyncError)
        .filter(
            EmailSyncError.mailbox_id == mailbox.id,
            EmailSyncError.provider_message_id == provider_message_id,
            EmailSyncError.sync_history_id == sync_history_id,
            EmailSyncError.error_type == error_type,
        )
        .one_or_none()
    )

    subject = truncate_to_bytes(raw_email.get("subject"), _SUBJECT_MAX_BYTES)
    sender = raw_email.get("sender")

    error_message = str(exc) or exc.__class__.__name__
    stack = (
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        if severity == "high"
        else None
    )

    payload = _build_payload(raw_email)

    if existing is not None:
        existing.error_message = error_message
        existing.stack_trace = stack
        existing.severity = severity
        existing.raw_payload = payload
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        return existing

    err = EmailSyncError(
        mailbox_id=mailbox.id,
        sync_history_id=sync_history_id,
        provider_message_id=provider_message_id,
        subject=subject,
        sender=sender,
        error_type=error_type,
        error_message=error_message,
        stack_trace=stack,
        raw_payload=payload,
        severity=severity,
        status="pending",
    )
    db.add(err)
    db.commit()

    if error_type == "unexpected":
        _mirror_to_application_logs(db, err, exc)

    return err


def auto_recover_pending(
    db: Session, mailbox_id: uuid.UUID, provider_message_id: str
) -> int:
    """Mark all pending errors for this email as auto_recovered. Returns affected row count."""
    if not provider_message_id:
        return 0
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(EmailSyncError)
        .where(
            EmailSyncError.mailbox_id == mailbox_id,
            EmailSyncError.provider_message_id == provider_message_id,
            EmailSyncError.status == "pending",
        )
        .values(
            status="auto_recovered",
            resolution="auto_recovered",
            resolved_at=now,
            updated_at=now,
        )
    )
    db.commit()
    return result.rowcount


def _build_payload(raw_email: Dict[str, Any]) -> Dict[str, Any]:
    """Build a JSON-serialisable payload no larger than 16KB."""
    payload = {
        k: raw_email.get(k)
        for k in (
            "message_id",
            "thread_id",
            "subject",
            "sender",
            "sender_name",
            "recipient",
            "date",
            "labels",
        )
        if k in raw_email
    }
    serialised = json.dumps(payload, default=str)
    if len(serialised) <= _RAW_PAYLOAD_MAX_BYTES:
        return payload
    while serialised and len(serialised) > _RAW_PAYLOAD_MAX_BYTES:
        if not payload:
            break
        biggest = max(payload, key=lambda k: len(str(payload[k])))
        payload[biggest] = "[truncated]"
        serialised = json.dumps(payload, default=str)
    payload["_truncated"] = True
    return payload


def _mirror_to_application_logs(
    db: Session, err: EmailSyncError, exc: Exception
) -> None:
    log = ApplicationLog(
        level="ERROR",
        logger_name="email_sync.unexpected",
        message=f"Unexpected error syncing email {err.provider_message_id}",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        stack_trace=err.stack_trace,
        context={
            "email_sync_error_id": str(err.id),
            "mailbox_id": str(err.mailbox_id),
            "provider_message_id": err.provider_message_id,
        },
    )
    db.add(log)
    db.commit()
