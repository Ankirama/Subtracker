"""Tests for admin sync-errors endpoints."""

import uuid

from app.models.email_sync_error import EmailSyncError


def _seed(db_session, mailbox, **kwargs):
    err = EmailSyncError(
        mailbox_id=mailbox.id,
        provider_message_id=kwargs.get("message_id", "m"),
        error_type=kwargs.get("error_type", "schema_too_long"),
        error_message="x",
        severity=kwargs.get("severity", "medium"),
        status=kwargs.get("status", "pending"),
        stack_trace="full traceback here",
        raw_payload={"subject": "X" * 100, "sender": "s@s"},
    )
    db_session.add(err)
    db_session.commit()
    db_session.refresh(err)
    return err


def test_admin_list_sync_errors_cross_user(
    client, admin_headers, test_mailbox, other_user_mailbox, db_session
):
    _seed(db_session, test_mailbox, message_id="m1")
    _seed(db_session, other_user_mailbox, message_id="m2")
    resp = client.get("/api/admin/sync-errors", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_admin_list_filters_by_severity(
    client, admin_headers, test_mailbox, db_session
):
    _seed(db_session, test_mailbox, message_id="a", severity="medium")
    _seed(db_session, test_mailbox, message_id="b", severity="high")
    resp = client.get("/api/admin/sync-errors?severity=high", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_admin_list_rejects_non_admin(client, auth_headers):
    resp = client.get("/api/admin/sync-errors", headers=auth_headers)
    assert resp.status_code == 403


def test_admin_list_rejects_unauthenticated(client):
    resp = client.get("/api/admin/sync-errors")
    assert resp.status_code in (401, 403)


def test_admin_detail_returns_raw_payload_and_stack_trace(
    client, admin_headers, test_mailbox, db_session
):
    err = _seed(db_session, test_mailbox)
    resp = client.get(f"/api/admin/sync-errors/{err.id}", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["stack_trace"] == "full traceback here"
    assert body["raw_payload"]["sender"] == "s@s"


def test_admin_detail_404_when_not_found(client, admin_headers):
    fake_id = uuid.uuid4()
    resp = client.get(f"/api/admin/sync-errors/{fake_id}", headers=admin_headers)
    assert resp.status_code == 404


def test_admin_resolve_marks_admin_resolved(
    client, admin_headers, admin_user, test_mailbox, db_session
):
    err = _seed(db_session, test_mailbox)
    resp = client.post(
        f"/api/admin/sync-errors/{err.id}/resolve", headers=admin_headers
    )
    assert resp.status_code == 200
    db_session.refresh(err)
    assert err.status == "resolved"
    assert err.resolution == "admin_resolved"
    assert err.resolved_by_id == admin_user.id
    assert err.resolved_at is not None
