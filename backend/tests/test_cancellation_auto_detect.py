"""Tests for the AI cancellation auto-detect flow.

Covers:
- ``maybe_create_cancellation_suggestion`` (the email-sync stage that
  populates ``suggested_cancellation_status`` from a classifier verdict)
- ``POST /api/subscriptions/{id}/accept-suggestion``
- ``POST /api/subscriptions/{id}/dismiss-suggestion``

Out of scope (covered separately):
- The post-commit notification emission in ``persistence.py`` is wired
  through ``NotificationService`` and tested in the notifications suite;
  here we only assert the cancellation step's return contract.
- ``ReviewSuggestionsService._detect_pending_cancellation`` lives in PR #60
  and is tested in the review-suggestions suite once that branch is in.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.email_message import EmailMessage
from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.tasks.email_sync.cancellation_step import (
    CancellationSuggestionCreated,
    maybe_create_cancellation_suggestion,
)


def _make_email(
    db: Session,
    mailbox: Mailbox,
    *,
    classification: dict | None,
) -> EmailMessage:
    """Create an EmailMessage with a chosen classification_reasoning blob."""
    email = EmailMessage(
        mailbox_id=mailbox.id,
        message_id=f"msg-{uuid4()}",
        subject="Subject",
        sender="provider@example.com",
        recipient=mailbox.email_address,
        date=datetime.now(timezone.utc),
        body_text="body",
        is_subscription=True,
        classification_confidence=0.9,
        classification_reasoning=classification,
    )
    db.add(email)
    db.commit()
    db.refresh(email)
    return email


# ---------- maybe_create_cancellation_suggestion -----------------------------


class TestMaybeCreateCancellationSuggestion:
    """Unit tests for the cancellation-step pure-ish function."""

    def test_returns_payload_and_sets_fields_on_first_detection(
        self,
        db_session: Session,
        test_subscription: Subscription,
        test_mailbox: Mailbox,
    ):
        """Happy path: cancellation classification + no prior suggestion."""
        email = _make_email(
            db_session,
            test_mailbox,
            classification={
                "category": "cancellation",
                "reasoning": "Email confirms account closure on 2026-06-01.",
            },
        )

        result = maybe_create_cancellation_suggestion(test_subscription, email)

        assert isinstance(result, CancellationSuggestionCreated)
        assert result.subscription_id == test_subscription.id
        assert result.user_id == test_subscription.user_id
        assert result.provider == test_subscription.provider
        assert "account closure" in result.reason

        # Fields are mutated on the subscription (caller commits)
        assert test_subscription.suggested_cancellation_status == "cancelled"
        assert (
            test_subscription.cancellation_suggestion_reason
            == "Email confirms account closure on 2026-06-01."
        )
        assert test_subscription.cancellation_suggestion_created_at is not None

    def test_returns_none_when_category_not_cancellation(
        self,
        db_session: Session,
        test_subscription: Subscription,
        test_mailbox: Mailbox,
    ):
        """Wrong category — no payload, no field mutation."""
        email = _make_email(
            db_session,
            test_mailbox,
            classification={"category": "renewal", "reasoning": "Monthly renewal."},
        )

        result = maybe_create_cancellation_suggestion(test_subscription, email)

        assert result is None
        assert test_subscription.suggested_cancellation_status is None
        assert test_subscription.cancellation_suggestion_reason is None

    def test_returns_none_when_classification_is_none(
        self,
        db_session: Session,
        test_subscription: Subscription,
        test_mailbox: Mailbox,
    ):
        """Missing classification — defaults to empty dict, no category match."""
        email = _make_email(db_session, test_mailbox, classification=None)

        result = maybe_create_cancellation_suggestion(test_subscription, email)

        assert result is None
        assert test_subscription.suggested_cancellation_status is None

    def test_returns_none_when_suggestion_already_pending(
        self,
        db_session: Session,
        test_subscription: Subscription,
        test_mailbox: Mailbox,
    ):
        """Single-shot guard: a second cancellation email doesn't re-suggest."""
        test_subscription.suggested_cancellation_status = "cancelled"
        test_subscription.cancellation_suggestion_reason = "earlier reason"
        test_subscription.cancellation_suggestion_created_at = datetime.now(
            timezone.utc
        )
        db_session.commit()

        email = _make_email(
            db_session,
            test_mailbox,
            classification={
                "category": "cancellation",
                "reasoning": "second cancellation email",
            },
        )

        result = maybe_create_cancellation_suggestion(test_subscription, email)

        assert result is None
        # Existing suggestion is preserved (not overwritten)
        assert test_subscription.cancellation_suggestion_reason == "earlier reason"

    def test_falls_back_to_default_reason_when_reasoning_missing(
        self,
        db_session: Session,
        test_subscription: Subscription,
        test_mailbox: Mailbox,
    ):
        """Cancellation category but no ``reasoning`` field — uses default text."""
        email = _make_email(
            db_session,
            test_mailbox,
            classification={"category": "cancellation"},
        )

        result = maybe_create_cancellation_suggestion(test_subscription, email)

        assert result is not None
        assert result.reason == "AI detected a cancellation email"
        assert (
            test_subscription.cancellation_suggestion_reason
            == "AI detected a cancellation email"
        )


# ---------- accept / dismiss endpoints ---------------------------------------


@pytest.fixture
def subscription_with_pending_suggestion(
    db_session: Session, test_subscription: Subscription
) -> Subscription:
    """A subscription that has an AI-generated cancellation suggestion waiting."""
    test_subscription.suggested_cancellation_status = "cancelled"
    test_subscription.cancellation_suggestion_reason = "Cancellation confirmation email"
    test_subscription.cancellation_suggestion_created_at = datetime.now(timezone.utc)
    db_session.commit()
    db_session.refresh(test_subscription)
    return test_subscription


class TestAcceptCancellationSuggestionEndpoint:
    """``POST /api/subscriptions/{id}/accept-suggestion``."""

    def test_accept_flips_status_and_clears_suggestion(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        subscription_with_pending_suggestion: Subscription,
    ):
        sub = subscription_with_pending_suggestion
        response = client.post(
            f"/api/subscriptions/{sub.id}/accept-suggestion",
            headers=auth_headers,
        )
        assert response.status_code == 200

        db_session.refresh(sub)
        assert sub.cancellation_status == "cancelled"
        assert sub.cancellation_confirmed_at is not None
        assert sub.cancellation_notes is not None
        assert "Auto-cancelled" in sub.cancellation_notes
        # Suggestion fields cleared
        assert sub.suggested_cancellation_status is None
        assert sub.cancellation_suggestion_reason is None
        assert sub.cancellation_suggestion_created_at is None

    def test_accept_returns_400_when_no_pending_suggestion(
        self,
        client: TestClient,
        auth_headers: dict,
        test_subscription: Subscription,
    ):
        # test_subscription has no suggestion populated by default
        response = client.post(
            f"/api/subscriptions/{test_subscription.id}/accept-suggestion",
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "No pending cancellation suggestion" in response.json()["detail"]

    def test_accept_returns_404_for_unknown_subscription(
        self, client: TestClient, auth_headers: dict
    ):
        response = client.post(
            f"/api/subscriptions/{uuid4()}/accept-suggestion",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_accept_returns_404_for_other_users_subscription(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        other_user_mailbox: Mailbox,
    ):
        # Build a subscription owned by another user with a pending suggestion
        other_sub = Subscription(
            id=uuid4(),
            user_id=other_user_mailbox.user_id,
            mailbox_id=other_user_mailbox.id,
            provider="OtherUserSpotify",
            amount=9.99,
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            is_active=True,
            extraction_method="ai",
            confidence_score=0.95,
            first_detected_at=datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc),
            suggested_cancellation_status="cancelled",
            cancellation_suggestion_reason="cancellation email",
            cancellation_suggestion_created_at=datetime.now(timezone.utc),
        )
        db_session.add(other_sub)
        db_session.commit()

        response = client.post(
            f"/api/subscriptions/{other_sub.id}/accept-suggestion",
            headers=auth_headers,
        )
        # Multi-tenant safety: looks like "not found" rather than 403
        assert response.status_code == 404


class TestDismissCancellationSuggestionEndpoint:
    """``POST /api/subscriptions/{id}/dismiss-suggestion``."""

    def test_dismiss_clears_suggestion_without_changing_status(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        subscription_with_pending_suggestion: Subscription,
    ):
        sub = subscription_with_pending_suggestion
        original_status = sub.cancellation_status
        response = client.post(
            f"/api/subscriptions/{sub.id}/dismiss-suggestion",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json() == {"success": True, "message": "Suggestion dismissed"}

        db_session.refresh(sub)
        # Status unchanged (still active)
        assert sub.cancellation_status == original_status
        # Suggestion fields cleared
        assert sub.suggested_cancellation_status is None
        assert sub.cancellation_suggestion_reason is None
        assert sub.cancellation_suggestion_created_at is None

    def test_dismiss_returns_400_when_no_pending_suggestion(
        self,
        client: TestClient,
        auth_headers: dict,
        test_subscription: Subscription,
    ):
        response = client.post(
            f"/api/subscriptions/{test_subscription.id}/dismiss-suggestion",
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_dismiss_returns_404_for_unknown_subscription(
        self, client: TestClient, auth_headers: dict
    ):
        response = client.post(
            f"/api/subscriptions/{uuid4()}/dismiss-suggestion",
            headers=auth_headers,
        )
        assert response.status_code == 404
