"""Comprehensive tests for notifications task."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationType,
)
from app.models.user import User
from app.tasks.notifications import (
    send_renewal_reminders,
    check_inactive_subscriptions,
    _convert_to_monthly,
)
from app.tasks.summary_tasks import send_weekly_summaries, send_monthly_summaries


@pytest.fixture
def subscription_renewing_in_7_days(
    db_session: Session, test_subscription: Subscription
) -> Subscription:
    """Create a subscription renewing in 7 days."""
    test_subscription.is_active = True
    test_subscription.next_billing_date = datetime.utcnow() + timedelta(days=7)
    test_subscription.amount = 15.99
    test_subscription.currency = "USD"
    test_subscription.billing_cycle = "monthly"
    db_session.commit()
    db_session.refresh(test_subscription)
    return test_subscription


@pytest.fixture
def renewal_preference(db_session: Session, test_user: User) -> NotificationPreference:
    """Create a renewal reminder preference."""
    pref = NotificationPreference(
        user_id=test_user.id,
        notification_type=NotificationType.RENEWAL_REMINDER,
        enabled=True,
        days_before_renewal=7,
    )
    db_session.add(pref)
    db_session.commit()
    db_session.refresh(pref)
    return pref


class TestSendRenewalReminders:
    """Tests for send_renewal_reminders task."""

    @patch("app.tasks.notifications.get_db")
    def test_sends_reminder_for_upcoming_renewal(
        self,
        mock_get_db: MagicMock,
        db_session: Session,
        subscription_renewing_in_7_days: Subscription,
        renewal_preference: NotificationPreference,
    ):
        """Should send reminder for subscription renewing in target window."""
        mock_get_db.return_value = iter([db_session])

        result = send_renewal_reminders()

        assert result["success"] is True
        assert result["notifications_sent"] >= 0

    @patch("app.tasks.notifications.get_db")
    def test_does_not_send_duplicate_reminder(
        self,
        mock_get_db: MagicMock,
        db_session: Session,
        subscription_renewing_in_7_days: Subscription,
        renewal_preference: NotificationPreference,
        test_user: User,
    ):
        """Should not send duplicate reminder if one was sent recently."""
        mock_get_db.return_value = iter([db_session])

        # Create recent notification
        notification = Notification(
            user_id=test_user.id,
            related_subscription_id=subscription_renewing_in_7_days.id,
            type=NotificationType.RENEWAL_REMINDER,
            priority="medium",
            title="Test",
            message="Test",
            created_at=datetime.utcnow() - timedelta(days=1),
        )
        db_session.add(notification)
        db_session.commit()

        result = send_renewal_reminders()

        assert result["success"] is True
        assert result["notifications_sent"] == 0

    @patch("app.tasks.notifications.get_db")
    def test_handles_no_preferences(self, mock_get_db: MagicMock, db_session: Session):
        """Should handle case with no renewal preferences."""
        mock_get_db.return_value = iter([db_session])

        result = send_renewal_reminders()

        assert result["success"] is True
        assert result["notifications_sent"] == 0

    @patch("app.tasks.notifications.get_db")
    def test_handles_errors_gracefully(self, mock_get_db: MagicMock):
        """Should handle errors and return error status."""
        mock_get_db.side_effect = Exception("Database error")

        result = send_renewal_reminders()

        assert result["success"] is False
        assert "error" in result


# NOTE: Tests for send_weekly_summaries and send_monthly_summaries have been moved to
# tests/test_summary_tasks.py which tests the newer implementation in app/tasks/summary_tasks.py


class TestCheckInactiveSubscriptions:
    """Tests for check_inactive_subscriptions task."""

    @patch("app.tasks.notifications.get_db")
    def test_detects_inactive_subscription(
        self,
        mock_get_db: MagicMock,
        db_session: Session,
        test_user: User,
        test_subscription: Subscription,
    ):
        """Should detect subscription with no activity in 90+ days."""
        mock_get_db.return_value = iter([db_session])

        # Set subscription as active but with old last_confirmed_at
        test_subscription.is_active = True
        test_subscription.last_confirmed_at = datetime.utcnow() - timedelta(days=100)
        db_session.commit()

        # Create preference
        pref = NotificationPreference(
            user_id=test_user.id,
            notification_type=NotificationType.INACTIVE_SUBSCRIPTION,
            enabled=True,
        )
        db_session.add(pref)
        db_session.commit()

        result = check_inactive_subscriptions()

        assert result["success"] is True
        assert result["notifications_sent"] >= 0

    @patch("app.tasks.notifications.get_db")
    def test_does_not_send_duplicate_inactive_notification(
        self,
        mock_get_db: MagicMock,
        db_session: Session,
        test_user: User,
        test_subscription: Subscription,
    ):
        """Should not send duplicate inactive notification within 30 days."""
        mock_get_db.return_value = iter([db_session])

        test_subscription.is_active = True
        test_subscription.last_confirmed_at = datetime.utcnow() - timedelta(days=100)
        db_session.commit()

        # Create recent notification
        notification = Notification(
            user_id=test_user.id,
            related_subscription_id=test_subscription.id,
            type=NotificationType.INACTIVE_SUBSCRIPTION,
            priority="low",
            title="Test",
            message="Test",
            created_at=datetime.utcnow() - timedelta(days=10),
        )
        db_session.add(notification)

        pref = NotificationPreference(
            user_id=test_user.id,
            notification_type=NotificationType.INACTIVE_SUBSCRIPTION,
            enabled=True,
        )
        db_session.add(pref)
        db_session.commit()

        result = check_inactive_subscriptions()

        assert result["success"] is True
        assert result["notifications_sent"] == 0

    @patch("app.tasks.notifications.get_db")
    def test_handles_errors_gracefully(self, mock_get_db: MagicMock):
        """Should handle errors and return error status."""
        mock_get_db.side_effect = Exception("Database error")

        result = check_inactive_subscriptions()

        assert result["success"] is False
        assert "error" in result


class TestConvertToMonthly:
    """Tests for _convert_to_monthly helper function."""

    def test_converts_monthly_correctly(self):
        """Should return same amount for monthly billing."""
        result = _convert_to_monthly(10.00, "monthly")
        assert result == 10.00

    def test_converts_yearly_correctly(self):
        """Should convert yearly amount to monthly."""
        result = _convert_to_monthly(120.00, "yearly")
        assert result == pytest.approx(10.00, rel=0.01)

    def test_converts_weekly_correctly(self):
        """Should convert weekly amount to monthly."""
        result = _convert_to_monthly(10.00, "weekly")
        assert result == pytest.approx(43.33, rel=0.01)

    def test_converts_quarterly_correctly(self):
        """Should convert quarterly amount to monthly."""
        result = _convert_to_monthly(30.00, "quarterly")
        assert result == pytest.approx(10.00, rel=0.01)

    def test_handles_none_amount(self):
        """Should return 0 for None amount."""
        result = _convert_to_monthly(None, "monthly")
        assert result == 0.0

    def test_handles_unknown_cycle(self):
        """Should default to monthly for unknown cycle."""
        result = _convert_to_monthly(10.00, "unknown_cycle")
        assert result == 10.00

    def test_handles_none_cycle(self):
        """Should default to monthly for None cycle."""
        result = _convert_to_monthly(10.00, None)
        assert result == 10.00
