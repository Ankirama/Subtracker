"""Integration tests for GET /api/sync-history/{id}/preview."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.models.sync_history import SyncHistory
from app.models.user import User
from app.security.password import hash_password


def _make_sync_history(db: Session, mailbox_id) -> SyncHistory:
    sh = SyncHistory(
        mailbox_id=mailbox_id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        status="completed",
        total_emails_processed=2,
        new_emails_count=2,
    )
    db.add(sh)
    db.commit()
    db.refresh(sh)
    return sh


@pytest.fixture
def other_user_mailbox(db_session: Session) -> Mailbox:
    """Create a mailbox owned by a different user (for cross-tenant tests)."""
    password_hash, salt = hash_password("otherpass123")
    other_user = User(
        email="other-tenant@example.com",
        password_hash=password_hash,
        salt=salt,
        is_active=True,
        email_verified=True,
        settings={},
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    mailbox = Mailbox(
        user_id=other_user.id,
        email_address="other@fastmail.com",
        provider_type="jmap",
        encrypted_credentials="other_encrypted_credentials",
        is_active=True,
    )
    db_session.add(mailbox)
    db_session.commit()
    db_session.refresh(mailbox)
    return mailbox


class TestSyncPreviewEndpoint:
    def test_returns_404_for_unknown_id(self, client: TestClient, auth_headers: dict):
        unknown = uuid4()
        r = client.get(f"/api/sync-history/{unknown}/preview", headers=auth_headers)
        assert r.status_code == 404

    def test_returns_404_when_sync_history_belongs_to_other_user(
        self,
        client: TestClient,
        db_session: Session,
        other_user_mailbox: Mailbox,
        auth_headers: dict,
    ):
        sh = _make_sync_history(db_session, other_user_mailbox.id)
        r = client.get(f"/api/sync-history/{sh.id}/preview", headers=auth_headers)
        assert r.status_code == 404

    def test_buckets_subscription_by_confidence(
        self,
        client: TestClient,
        db_session: Session,
        test_mailbox: Mailbox,
        auth_headers: dict,
    ):
        sh = _make_sync_history(db_session, test_mailbox.id)
        auto = Subscription(
            mailbox_id=test_mailbox.id,
            user_id=test_mailbox.user_id,
            provider="Netflix",
            amount=Decimal("14.99"),
            currency="EUR",
            billing_cycle="monthly",
            confidence_score=Decimal("92.0"),
            discovered_via_sync_history_id=sh.id,
        )
        review = Subscription(
            mailbox_id=test_mailbox.id,
            user_id=test_mailbox.user_id,
            provider="Patreon",
            amount=Decimal("5.00"),
            currency="EUR",
            billing_cycle="monthly",
            confidence_score=Decimal("70.0"),
            discovered_via_sync_history_id=sh.id,
        )
        db_session.add_all([auto, review])
        db_session.commit()

        r = client.get(f"/api/sync-history/{sh.id}/preview", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        buckets = {
            row["provider"]: row["confidence_bucket"]
            for row in body["new_subscriptions"]
        }
        assert buckets == {
            "Netflix": "auto_saved",
            "Patreon": "pending_review",
        }

    def test_returns_empty_arrays_when_run_produced_nothing(
        self,
        client: TestClient,
        db_session: Session,
        test_mailbox: Mailbox,
        auth_headers: dict,
    ):
        sh = _make_sync_history(db_session, test_mailbox.id)
        r = client.get(f"/api/sync-history/{sh.id}/preview", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["new_subscriptions"] == []
        assert body["updated_subscriptions"] == []
        assert body["sync_history"]["id"] == str(sh.id)
