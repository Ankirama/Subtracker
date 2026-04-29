"""Tests for per-email failure isolation in the email-sync pipeline.

Verifies the resilience behaviour added in Task 7 to
``stages/classification.py``:

- A poisoned email in the middle of a batch yields one EmailSyncError row
  and the other emails persist normally.
- 5 consecutive ``unexpected`` errors trip the circuit breaker.

Tests call ``classify_new_emails`` directly with constructed inputs rather
than driving the full Celery harness, since this is a stage-level concern.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import exc as sa_exc

from app.email_providers.base import EmailMessage as ProviderEmailMessage
from app.models.email_message import EmailMessage
from app.models.email_sync_error import EmailSyncError
from app.services.sync_error_circuit_breaker import (
    SyncCircuitBreakerError,
    CIRCUIT_BREAKER_THRESHOLD,
)
from app.tasks.email_sync.stages.classification import classify_new_emails


def _provider_email(message_id: str, subject: str = "test"):
    return ProviderEmailMessage(
        id=message_id,
        subject=subject,
        sender="x@example.com",
        sender_name="X",
        recipients=["test@example.com"],
        date=datetime.now(timezone.utc),
        body_text="body",
        body_html=None,
        headers={"Message-ID": message_id},
        has_attachments=False,
        folder=None,
    )


async def _passthrough_classify(emails, db):
    return [
        {
            "is_subscription": False,
            "category": None,
            "confidence": 0.0,
            "reasoning": "",
        }
        for _ in emails
    ]


def _make_selective_flush(db_session, predicate):
    """Build a flush replacement that raises ``predicate(pending)`` if not
    None and otherwise delegates to the original flush.

    The predicate receives the iterable of pending ``Session.new`` objects
    and returns either an exception to raise or ``None`` to pass through.
    This lets us inject failures only when the email-sync code is
    flushing an ``EmailMessage`` row, while still allowing the
    sync-error recorder to commit its own ``EmailSyncError`` rows
    through this same patched session.
    """
    original_flush = db_session.flush

    def selective_flush(*args, **kwargs):
        pending = list(db_session.new)
        exc = predicate(pending)
        if exc is not None:
            raise exc
        return original_flush(*args, **kwargs)

    return selective_flush, original_flush


@pytest.mark.asyncio
async def test_poisoned_email_does_not_kill_batch(db_session, test_mailbox):
    """Three emails: middle one's flush raises DataError. Other two
    persist; exactly one EmailSyncError row records the failure."""
    emails = [
        _provider_email("good-1"),
        _provider_email("poison-1"),
        _provider_email("good-2"),
    ]

    flush_calls = {"n": 0}

    def predicate(pending):
        # Only raise on EmailMessage flushes; let EmailSyncError commits
        # (used by the sync-error recorder) pass through unhindered.
        if any(isinstance(o, EmailMessage) for o in pending):
            flush_calls["n"] += 1
            if flush_calls["n"] == 2:
                return sa_exc.DataError(
                    "INSERT",
                    {},
                    Exception("value too long for type character varying(500)"),
                )
        return None

    selective_flush, original_flush = _make_selective_flush(db_session, predicate)
    db_session.flush = selective_flush
    try:
        await classify_new_emails(
            db_session,
            test_mailbox,
            emails,
            batch_num=1,
            classify_batch=_passthrough_classify,
        )
    finally:
        db_session.flush = original_flush

    persisted_ids = {
        e.message_id
        for e in db_session.query(EmailMessage)
        .filter(EmailMessage.mailbox_id == test_mailbox.id)
        .all()
    }
    assert "good-1" in persisted_ids
    assert "good-2" in persisted_ids
    assert "poison-1" not in persisted_ids

    errors = (
        db_session.query(EmailSyncError)
        .filter(EmailSyncError.mailbox_id == test_mailbox.id)
        .all()
    )
    assert len(errors) == 1
    assert errors[0].provider_message_id == "poison-1"
    assert errors[0].error_type == "schema_too_long"
    assert errors[0].status == "pending"


@pytest.mark.asyncio
async def test_circuit_breaker_trips_after_5_consecutive_unexpected(
    db_session, test_mailbox
):
    """Five consecutive unexpected errors → SyncCircuitBreakerError raised
    and 5 pending error rows recorded."""
    emails = [_provider_email(f"m-{i}") for i in range(CIRCUIT_BREAKER_THRESHOLD)]

    def predicate(pending):
        # Raise on every EmailMessage flush, but let the recorder's
        # EmailSyncError commits pass through.
        if any(isinstance(o, EmailMessage) for o in pending):
            return RuntimeError("simulated systemic bug")
        return None

    selective_flush, original_flush = _make_selective_flush(db_session, predicate)
    db_session.flush = selective_flush
    try:
        with pytest.raises(SyncCircuitBreakerError) as excinfo:
            await classify_new_emails(
                db_session,
                test_mailbox,
                emails,
                batch_num=1,
                classify_batch=_passthrough_classify,
            )
        assert excinfo.value.error_count >= CIRCUIT_BREAKER_THRESHOLD
        assert excinfo.value.threshold == CIRCUIT_BREAKER_THRESHOLD
    finally:
        db_session.flush = original_flush

    errors = (
        db_session.query(EmailSyncError)
        .filter(EmailSyncError.mailbox_id == test_mailbox.id)
        .all()
    )
    assert len(errors) == CIRCUIT_BREAKER_THRESHOLD
    assert all(e.error_type == "unexpected" for e in errors)
    assert all(e.severity == "high" for e in errors)
