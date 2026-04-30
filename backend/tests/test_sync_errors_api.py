"""Chartests for user-facing sync errors endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.email_sync_error import EmailSyncError
from app.models.mailbox import Mailbox
from app.models.user import User
from app.security.password import hash_password


@pytest.fixture
def other_user_mailbox(db_session: Session) -> Mailbox:
    """A mailbox owned by a DIFFERENT user (for cross-tenant isolation tests)."""
    pw_hash, salt = hash_password("otherpassword123")
    other = User(
        email="other@example.com",
        password_hash=pw_hash,
        salt=salt,
        is_active=True,
        email_verified=True,
        settings={},
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    mb = Mailbox(
        user_id=other.id,
        email_address="other@fastmail.com",
        provider_type="jmap",
        encrypted_credentials="x",
        is_active=True,
    )
    db_session.add(mb)
    db_session.commit()
    db_session.refresh(mb)
    return mb


def _seed_errors(
    db_session: Session, mailbox: Mailbox, count: int, status: str = "pending"
):
    rows = []
    for i in range(count):
        e = EmailSyncError(
            mailbox_id=mailbox.id,
            provider_message_id=f"msg-{i}",
            subject=f"Subject {i}",
            sender=f"sender{i}@example.com",
            error_type="schema_too_long",
            error_message="value too long",
            severity="medium",
            status=status,
        )
        db_session.add(e)
        rows.append(e)
    db_session.commit()
    for e in rows:
        db_session.refresh(e)
    return rows


def test_list_sync_errors_returns_user_mailbox_errors(
    client, auth_headers, test_mailbox, db_session
):
    _seed_errors(db_session, test_mailbox, 3)
    resp = client.get(
        f"/api/mailboxes/{test_mailbox.id}/sync-errors", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    # PII-safe: server-side schema must not expose raw_payload / stack_trace.
    for item in body["items"]:
        assert "raw_payload" not in item
        assert "stack_trace" not in item


def test_list_sync_errors_filters_by_status(
    client, auth_headers, test_mailbox, db_session
):
    _seed_errors(db_session, test_mailbox, 2, status="pending")
    _seed_errors(db_session, test_mailbox, 1, status="ignored")
    resp = client.get(
        f"/api/mailboxes/{test_mailbox.id}/sync-errors?status=ignored",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_list_sync_errors_rejects_other_users_mailbox(
    client, auth_headers, other_user_mailbox
):
    resp = client.get(
        f"/api/mailboxes/{other_user_mailbox.id}/sync-errors",
        headers=auth_headers,
    )
    assert resp.status_code in (403, 404)


def test_ignore_sync_error_marks_ignored(
    client, auth_headers, test_mailbox, db_session
):
    [err] = _seed_errors(db_session, test_mailbox, 1)
    resp = client.post(f"/api/sync-errors/{err.id}/ignore", headers=auth_headers)
    assert resp.status_code == 200
    db_session.refresh(err)
    assert err.status == "ignored"
    assert err.resolution == "user_ignored"
    assert err.resolved_at is not None


def test_ignore_sync_error_rejects_other_users_error(
    client, auth_headers, other_user_mailbox, db_session
):
    [err] = _seed_errors(db_session, other_user_mailbox, 1)
    resp = client.post(f"/api/sync-errors/{err.id}/ignore", headers=auth_headers)
    assert resp.status_code in (403, 404)


def test_retry_sync_errors_enqueues_celery_task(
    client, auth_headers, test_mailbox, db_session
):
    _seed_errors(db_session, test_mailbox, 2)
    # Patch the bound name in the router module so the FastAPI handler
    # invokes the mock instead of touching Celery.
    with patch("app.api.sync_errors.retry_skipped_emails.delay") as delay_mock:
        delay_mock.return_value = MagicMock(id="task-123")
        resp = client.post(
            f"/api/mailboxes/{test_mailbox.id}/sync-errors/retry",
            headers=auth_headers,
        )
    assert resp.status_code == 202
    body = resp.json()
    assert body["task_id"] == "task-123"
    assert body["pending_count"] == 2
    delay_mock.assert_called_once()


def test_retry_sync_errors_400_when_no_pending(
    client, auth_headers, test_mailbox, db_session
):
    _seed_errors(db_session, test_mailbox, 1, status="ignored")
    resp = client.post(
        f"/api/mailboxes/{test_mailbox.id}/sync-errors/retry",
        headers=auth_headers,
    )
    assert resp.status_code == 400
