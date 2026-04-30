"""Unit tests for sync_error_recorder.

The recorder is the sole writer of email_sync_errors rows. It must:
- persist a row even when the previous DB op poisoned the session
  (caller has issued db.rollback() before calling)
- truncate subject/raw_payload defensively
- write to application_logs at severity=high for unexpected errors
- be idempotent on (mailbox_id, provider_message_id, sync_history_id, error_type)
- support auto_recover_pending() for the success path
"""

from sqlalchemy.orm import Session

from app.models.email_sync_error import EmailSyncError
from app.models.mailbox import Mailbox
from app.models.user import User
from app.services.sync_error_recorder import (
    record_sync_error,
    auto_recover_pending,
)


def _make_mailbox(db: Session, user: User) -> Mailbox:
    mb = Mailbox(
        user_id=user.id,
        provider_type="gmail",
        email_address="test@example.com",
        encrypted_credentials="x",
        is_active=True,
        sync_frequency="manual",
        batch_size=10,
        import_date_filter="30days",
        last_sync_status="success",
    )
    db.add(mb)
    db.commit()
    return mb


def test_record_sync_error_persists_row(db_session, test_user):
    mb = _make_mailbox(db_session, test_user)
    raw_email = {
        "message_id": "msg-1",
        "subject": "S" * 100,
        "sender": "spam@example.com",
    }
    err = record_sync_error(
        db=db_session,
        mailbox=mb,
        sync_history=None,
        raw_email=raw_email,
        exc=ValueError("boom"),
        error_type="unexpected",
        severity="high",
    )
    assert err.id is not None
    assert err.mailbox_id == mb.id
    assert err.error_type == "unexpected"
    assert err.severity == "high"
    assert err.status == "pending"
    assert err.provider_message_id == "msg-1"
    assert err.subject == "S" * 100
    assert err.sender == "spam@example.com"
    assert err.error_message == "boom"
    assert err.stack_trace is not None  # populated for severity=high


def test_record_sync_error_truncates_subject_and_payload(db_session, test_user):
    mb = _make_mailbox(db_session, test_user)
    raw_email = {
        "message_id": "msg-2",
        "subject": "X" * 100_000,  # 100KB
        "sender": "spam@example.com",
    }
    err = record_sync_error(
        db=db_session,
        mailbox=mb,
        sync_history=None,
        raw_email=raw_email,
        exc=ValueError("boom"),
        error_type="unexpected",
        severity="high",
    )
    # Subject capped at 4096 bytes
    assert len(err.subject.encode("utf-8")) <= 4096
    # raw_payload exists and is under 16KB serialised
    import json

    assert err.raw_payload is not None
    assert len(json.dumps(err.raw_payload)) <= 16_384


def test_record_sync_error_idempotent_on_same_message(db_session, test_user):
    mb = _make_mailbox(db_session, test_user)
    raw = {"message_id": "msg-3", "subject": "s", "sender": "x@x"}
    e1 = record_sync_error(
        db_session, mb, None, raw, ValueError("a"), "schema_too_long", "medium"
    )
    e2 = record_sync_error(
        db_session, mb, None, raw, ValueError("b"), "schema_too_long", "medium"
    )
    assert e1.id == e2.id  # same row returned
    rows = (
        db_session.query(EmailSyncError)
        .filter(EmailSyncError.mailbox_id == mb.id)
        .all()
    )
    assert len(rows) == 1


def test_record_sync_error_unexpected_writes_application_log(db_session, test_user):
    from app.models.admin import ApplicationLog

    mb = _make_mailbox(db_session, test_user)
    raw = {"message_id": "msg-4", "subject": "s", "sender": "x@x"}
    record_sync_error(
        db_session, mb, None, raw, RuntimeError("boom"), "unexpected", "high"
    )
    logs = (
        db_session.query(ApplicationLog)
        .filter(ApplicationLog.logger_name == "email_sync.unexpected")
        .all()
    )
    assert len(logs) == 1
    assert logs[0].level == "ERROR"


def test_auto_recover_pending_marks_resolved(db_session, test_user):
    mb = _make_mailbox(db_session, test_user)
    err = EmailSyncError(
        mailbox_id=mb.id,
        provider_message_id="msg-5",
        error_type="schema_too_long",
        error_message="x",
        status="pending",
    )
    db_session.add(err)
    db_session.commit()

    n = auto_recover_pending(db_session, mb.id, "msg-5")
    db_session.refresh(err)
    assert n == 1
    assert err.status == "auto_recovered"
    assert err.resolution == "auto_recovered"
    assert err.resolved_at is not None


def test_auto_recover_pending_noop_when_already_resolved(db_session, test_user):
    mb = _make_mailbox(db_session, test_user)
    err = EmailSyncError(
        mailbox_id=mb.id,
        provider_message_id="msg-6",
        error_type="schema_too_long",
        error_message="x",
        status="ignored",
    )
    db_session.add(err)
    db_session.commit()

    n = auto_recover_pending(db_session, mb.id, "msg-6")
    assert n == 0
