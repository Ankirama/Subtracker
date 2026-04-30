"""Tests for the ``retry_skipped_emails`` Celery task.

Covers the row-level state machine on success/failure paths and the
filtering/safety behaviour around scoped retries and unknown mailboxes.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.models.email_sync_error import EmailSyncError
from app.tasks.sync_error_retry import retry_skipped_emails


def _make_provider_email(message_id: str):
    """Build a minimal stand-in for ``app.email_providers.base.EmailMessage``.

    Only the attributes touched by ``classify_new_emails`` matter — they
    are all duck-typed via attribute access.
    """
    return SimpleNamespace(
        id=message_id,
        subject="retry subject",
        sender="r@example.com",
        sender_name="R",
        recipients=["test@fastmail.com"],
        date=datetime.now(timezone.utc),
        body_text="body",
        body_html=None,
        headers={"Message-ID": message_id, "Thread-ID": None},
        has_attachments=False,
        folder=None,
    )


@patch("app.tasks.sync_error_retry.SessionLocal")
@patch("app.tasks.sync_error_retry._process_single_email_attempt")
@patch("app.tasks.sync_error_retry._refetch_email")
def test_retry_success_marks_user_retried_success(
    mock_refetch,
    mock_process,
    mock_session_local,
    db_session,
    test_mailbox,
):
    """Happy path: one pending row becomes ``retried`` with the user resolution."""
    mock_session_local.return_value = db_session
    # Neutralise the task's after_return close — we want the test session alive
    # so post-call refresh() does not detach the ORM instance.
    db_session.close = lambda: None

    err = EmailSyncError(
        mailbox_id=test_mailbox.id,
        provider_message_id="m-success",
        error_type="schema_too_long",
        error_message="x",
        status="pending",
    )
    db_session.add(err)
    db_session.commit()

    mock_refetch.return_value = _make_provider_email("m-success")
    mock_process.return_value = True

    result = retry_skipped_emails.apply(args=[str(test_mailbox.id)]).get()

    db_session.refresh(err)
    assert err.status == "retried"
    assert err.resolution == "user_retried_success"
    assert err.retry_count == 1
    assert err.last_retry_at is not None
    assert result["retried"] == 1
    assert result["succeeded"] == 1
    assert result["still_failing"] == 0


@patch("app.tasks.sync_error_retry.SessionLocal")
@patch("app.tasks.sync_error_retry._process_single_email_attempt")
@patch("app.tasks.sync_error_retry._refetch_email")
def test_retry_failure_keeps_pending_increments_count(
    mock_refetch,
    mock_process,
    mock_session_local,
    db_session,
    test_mailbox,
):
    """Refetch ok but persistence fails → row stays pending, counter bumps."""
    mock_session_local.return_value = db_session
    db_session.close = lambda: None

    err = EmailSyncError(
        mailbox_id=test_mailbox.id,
        provider_message_id="m-fail",
        error_type="schema_too_long",
        error_message="x",
        status="pending",
        retry_count=0,
    )
    db_session.add(err)
    db_session.commit()

    mock_refetch.return_value = _make_provider_email("m-fail")
    mock_process.return_value = False

    result = retry_skipped_emails.apply(args=[str(test_mailbox.id)]).get()

    db_session.refresh(err)
    assert err.status == "pending"
    assert err.retry_count == 1
    assert err.last_retry_at is not None
    assert result["still_failing"] == 1
    assert result["succeeded"] == 0


@patch("app.tasks.sync_error_retry.SessionLocal")
@patch("app.tasks.sync_error_retry._refetch_email")
def test_retry_provider_returns_none_marks_still_failing(
    mock_refetch,
    mock_session_local,
    db_session,
    test_mailbox,
):
    """Provider 404 / message gone → row stays pending with descriptive message."""
    mock_session_local.return_value = db_session
    db_session.close = lambda: None

    err = EmailSyncError(
        mailbox_id=test_mailbox.id,
        provider_message_id="m-gone",
        error_type="schema_too_long",
        error_message="x",
        status="pending",
    )
    db_session.add(err)
    db_session.commit()

    mock_refetch.return_value = None

    result = retry_skipped_emails.apply(args=[str(test_mailbox.id)]).get()

    db_session.refresh(err)
    assert err.status == "pending"
    assert err.retry_count == 1
    assert err.error_message is not None
    assert "no longer" in err.error_message.lower()
    assert result["retried"] == 1
    assert result["still_failing"] == 1


@patch("app.tasks.sync_error_retry.SessionLocal")
def test_retry_with_specific_error_ids_filters(
    mock_session_local,
    db_session,
    test_mailbox,
):
    """``error_ids`` scopes the retry to a specific row."""
    mock_session_local.return_value = db_session
    db_session.close = lambda: None

    e1 = EmailSyncError(
        mailbox_id=test_mailbox.id,
        provider_message_id="m-1",
        error_type="schema_too_long",
        error_message="x",
        status="pending",
    )
    e2 = EmailSyncError(
        mailbox_id=test_mailbox.id,
        provider_message_id="m-2",
        error_type="schema_too_long",
        error_message="x",
        status="pending",
    )
    db_session.add_all([e1, e2])
    db_session.commit()

    with patch("app.tasks.sync_error_retry._refetch_email", return_value=None):
        result = retry_skipped_emails.apply(
            args=[str(test_mailbox.id), [str(e1.id)]]
        ).get()

    assert result["retried"] == 1
    # The unscoped row must remain untouched.
    db_session.refresh(e2)
    assert e2.retry_count == 0
    assert e2.last_retry_at is None


@patch("app.tasks.sync_error_retry.SessionLocal")
def test_retry_unknown_mailbox_returns_zero(
    mock_session_local,
    db_session,
):
    """Unknown mailbox short-circuits with zeros and an ``error`` field."""
    mock_session_local.return_value = db_session
    db_session.close = lambda: None

    result = retry_skipped_emails.apply(args=[str(uuid.uuid4())]).get()

    assert result["retried"] == 0
    assert result["succeeded"] == 0
    assert result["still_failing"] == 0
    assert "not found" in result.get("error", "").lower()


@patch("app.tasks.sync_error_retry.SessionLocal")
def test_retry_jmap_mailbox_writes_unsupported_message(
    mock_session_local,
    db_session,
    test_mailbox,
):
    """JMAP refetch is a stub — retry must surface a clearer "not supported"
    error_message instead of the misleading "no longer returns" one.

    This test deliberately does NOT mock ``_refetch_email`` so the new
    ``_RETRY_SUPPORTED_PROVIDERS`` guard is exercised end-to-end.
    """
    # ``test_mailbox`` defaults to provider_type="jmap" (see conftest).
    assert test_mailbox.provider_type == "jmap"

    mock_session_local.return_value = db_session
    db_session.close = lambda: None

    err = EmailSyncError(
        mailbox_id=test_mailbox.id,
        provider_message_id="m-jmap",
        error_type="schema_too_long",
        error_message="x",
        status="pending",
    )
    db_session.add(err)
    db_session.commit()

    result = retry_skipped_emails.apply(args=[str(test_mailbox.id)]).get()

    db_session.refresh(err)
    assert err.status == "pending"
    assert err.retry_count == 1
    assert err.error_message is not None
    msg = err.error_message.lower()
    assert "not yet supported" in msg
    assert "no longer" not in msg
    assert result["retried"] == 1
    assert result["still_failing"] == 1
    assert result["succeeded"] == 0
