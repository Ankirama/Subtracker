"""Celery task for retrying skipped emails.

Re-fetches the email from its provider via ``provider_message_id``, runs
the per-email persistence path again (``classify_new_emails``), and
updates the corresponding ``EmailSyncError`` row.

Per-error isolation: a failure on one row does not abort the others.

Status transitions on retry:
- success → ``status="retried"``, ``resolution="user_retried_success"``,
  ``resolved_at=now``.
- failure (re-fetched but persistence still fails) → row stays ``pending``;
  ``retry_count`` incremented; ``last_retry_at`` updated. The resilient
  classifier itself records the new failure (idempotent on
  ``(mailbox_id, provider_message_id, sync_history_id, error_type)``).
- provider returns ``None`` (message deleted/moved) → row stays
  ``pending``; ``retry_count`` incremented; ``error_message`` updated.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from celery import Task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.email_providers import GmailProvider, JMAPProvider
from app.models.email_sync_error import EmailSyncError
from app.models.mailbox import Mailbox
from app.security.encryption import decrypt_credentials
from app.services.ai_classifier import classify_emails_batch
from app.tasks.email_sync.stages.classification import classify_new_emails

logger = logging.getLogger(__name__)


class _RetryDatabaseTask(Task):
    """Celery task base that lazily opens a SessionLocal and closes it after run."""

    _db: Optional[Session] = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):  # noqa: D401
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    base=_RetryDatabaseTask,
    bind=True,
    name="app.tasks.sync_error_retry.retry_skipped_emails",
    autoretry_for=(),  # never autoretry — explicit per-row handling below
    max_retries=0,
)
def retry_skipped_emails(
    self, mailbox_id: str, error_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Retry pending skipped emails for one mailbox.

    Args:
        mailbox_id: Stringified UUID of the mailbox.
        error_ids: Optional list of stringified ``EmailSyncError`` UUIDs to
            scope the retry to specific rows. When omitted, all pending
            errors for the mailbox are retried.

    Returns:
        Counter dict: ``{"retried": N, "succeeded": K, "still_failing": M}``.
        On unknown mailbox: zeros plus ``"error": "mailbox not found"``.
    """
    db: Session = self.db

    try:
        mb_uuid = UUID(mailbox_id)
    except (TypeError, ValueError):
        return {
            "retried": 0,
            "succeeded": 0,
            "still_failing": 0,
            "error": "invalid mailbox id",
        }

    mb = db.query(Mailbox).filter(Mailbox.id == mb_uuid).first()
    if mb is None:
        return {
            "retried": 0,
            "succeeded": 0,
            "still_failing": 0,
            "error": "mailbox not found",
        }

    q = db.query(EmailSyncError).filter(
        EmailSyncError.mailbox_id == mb.id,
        EmailSyncError.status == "pending",
    )
    if error_ids:
        try:
            scoped_ids = [UUID(e) for e in error_ids]
        except (TypeError, ValueError):
            return {
                "retried": 0,
                "succeeded": 0,
                "still_failing": 0,
                "error": "invalid error id",
            }
        q = q.filter(EmailSyncError.id.in_(scoped_ids))

    rows = q.all()

    retried = 0
    succeeded = 0
    still_failing = 0

    for err in rows:
        retried += 1

        # Persist retry bookkeeping before doing any work, so the increment
        # is durable even if the persistence path raises a hard exception.
        err.retry_count = (err.retry_count or 0) + 1
        err.last_retry_at = datetime.now(timezone.utc)
        db.commit()

        provider_message_id = err.provider_message_id
        err_id = err.id

        try:
            refetched = _refetch_email(mb, provider_message_id)
            if refetched is None:
                err.error_message = "Provider no longer returns this message id"
                db.commit()
                still_failing += 1
                continue

            ok = _process_single_email_attempt(db, mb, refetched)
            if ok:
                # ``classify_new_emails`` already called ``auto_recover_pending``
                # which updated this row to ``status="auto_recovered"`` via a
                # raw UPDATE + commit. The in-memory ``err`` is stale — refresh
                # before overwriting so we don't trip a stale-row optimistic
                # concurrency error and so we land on ``status="retried"``.
                db.refresh(err)
                err.status = "retried"
                err.resolution = "user_retried_success"
                err.resolved_at = datetime.now(timezone.utc)
                db.commit()
                succeeded += 1
            else:
                # The resilient wrapper inside ``classify_new_emails`` already
                # wrote (or updated) this row's error_type / severity /
                # error_message. We deliberately do NOT touch those fields
                # here to avoid a double-write race.
                still_failing += 1
        except Exception as exc:  # noqa: BLE001 — defensive belt-and-suspenders
            # Hard exception escaped the resilient wrapper (e.g. OperationalError
            # raised by the wrapping commit). Roll back the session, re-fetch
            # the row, and surface the failure on the row's error_message.
            logger.exception("Hard failure during retry of email_sync_error %s", err_id)
            db.rollback()
            refreshed = (
                db.query(EmailSyncError).filter(EmailSyncError.id == err_id).first()
            )
            if refreshed is not None:
                refreshed.error_message = f"retry failed: {exc}"
                db.commit()
            still_failing += 1

    return {
        "retried": retried,
        "succeeded": succeeded,
        "still_failing": still_failing,
    }


def _refetch_email(mailbox: Mailbox, provider_message_id: str):
    """Fetch one email by provider id.

    Runs the entire async dance (instantiate provider, fetch, close) in a
    single ``asyncio.run`` so we don't churn through three event loops per
    email.

    Returns the provider-side ``EmailMessage`` dataclass, or ``None`` if
    the provider type is unsupported / the message has been deleted.
    """

    async def _run():
        creds = decrypt_credentials(mailbox.encrypted_credentials)
        if mailbox.provider_type == "jmap":
            provider = JMAPProvider(creds)
        elif mailbox.provider_type == "gmail":
            provider = GmailProvider(creds)
        else:
            return None
        try:
            return await provider.get_message_by_id(provider_message_id)
        finally:
            try:
                await provider.close()
            except Exception:  # noqa: BLE001 — best-effort cleanup
                logger.warning("Provider close() failed during retry", exc_info=True)

    return asyncio.run(_run())


def _process_single_email_attempt(db: Session, mailbox: Mailbox, email_obj) -> bool:
    """Run the resilient classifier on a single re-fetched email.

    Returns ``True`` when the email landed in ``EmailMessage`` (i.e. the
    persistence path succeeded), ``False`` otherwise. The resilient
    wrapper already records the new ``EmailSyncError`` (idempotent
    update) on failure paths.
    """

    async def _run():
        return await classify_new_emails(
            db,
            mailbox,
            [email_obj],
            batch_num=0,
            classify_batch=classify_emails_batch,
        )

    try:
        records, _existing = asyncio.run(_run())
    except Exception:  # noqa: BLE001 — caller still bumps still_failing
        logger.exception(
            "classify_new_emails raised during retry for mailbox %s", mailbox.id
        )
        return False
    return len(records) == 1
