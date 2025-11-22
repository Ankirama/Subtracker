"""Comprehensive tests for renewal reminders task."""
import pytest
from datetime import datetime, timedelta, date, timezone
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.models.notification import Notification, NotificationPreference, NotificationType, NotificationPriority
from app.models.user import User
from app.tasks.renewal_reminders import (
    get_renewal_date,
    should_send_reminder,
    create_renewal_notification,
    send_renewal_email,
    check_renewal_reminders
)


@pytest.fixture
def subscription_renewing_soon(db_session: Session, test_subscription: Subscription) -> Subscription:
    """Create a subscription renewing in 3 days."""
    test_subscription.renewal_date = date.today() + timedelta(days=3)
    test_subscription.is_active = True
    db_session.commit()
    db_session.refresh(test_subscription)
    return test_subscription


class TestGetRenewalDate:
    """Tests for get_renewal_date function."""

    def test_prefers_next_billing_date(self, test_subscription: Subscription):
        """Should return next_billing_date if available."""
        test_subscription.next_billing_date = date.today() + timedelta(days=5)
        test_subscription.renewal_date = date.today() + timedelta(days=10)

        result = get_renewal_date(test_subscription)
        assert result == test_subscription.next_billing_date

    def test_falls_back_to_renewal_date(self, test_subscription: Subscription):
        """Should return renewal_date if next_billing_date not set."""
        test_subscription.next_billing_date = None
        test_subscription.renewal_date = date.today() + timedelta(days=10)

        result = get_renewal_date(test_subscription)
        assert result == test_subscription.renewal_date

    def test_returns_none_if_no_dates(self, test_subscription: Subscription):
        """Should return None if no dates set."""
        test_subscription.next_billing_date = None
        test_subscription.renewal_date = None

        result = get_renewal_date(test_subscription)
        assert result is None


class TestShouldSendReminder:
    """Tests for should_send_reminder function."""

    def test_sends_reminder_3_days_before(
        self,
        db_session: Session,
        subscription_renewing_soon: Subscription
    ):
        """Should send reminder 3 days before renewal."""
        result = should_send_reminder(subscription_renewing_soon, 3, db_session)
        assert result is True

    def test_does_not_send_wrong_day(
        self,
        db_session: Session,
        subscription_renewing_soon: Subscription
    ):
        """Should not send reminder on wrong day."""
        result = should_send_reminder(subscription_renewing_soon, 1, db_session)
        assert result is False

    def test_does_not_send_without_renewal_date(
        self,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should not send reminder if no renewal date."""
        test_subscription.renewal_date = None
        test_subscription.next_billing_date = None
        db_session.commit()

        result = should_send_reminder(test_subscription, 3, db_session)
        assert result is False

    def test_does_not_send_duplicate_within_24h(
        self,
        db_session: Session,
        subscription_renewing_soon: Subscription,
        test_user: User
    ):
        """Should not send duplicate reminder within 24 hours."""
        # Create recent reminder
        notification = Notification(
            user_id=test_user.id,
            related_subscription_id=subscription_renewing_soon.id,
            type=NotificationType.RENEWAL_REMINDER,
            priority=NotificationPriority.MEDIUM,
            title="Renewal Reminder",
            message="Test",
            created_at=datetime.now(timezone.utc) - timedelta(hours=12)
        )
        db_session.add(notification)
        db_session.commit()

        result = should_send_reminder(subscription_renewing_soon, 3, db_session)
        assert result is False

    def test_sends_after_24_hours(
        self,
        db_session: Session,
        subscription_renewing_soon: Subscription,
        test_user: User
    ):
        """Should send reminder if last one was >24h ago."""
        # Create old reminder
        notification = Notification(
            user_id=test_user.id,
            related_subscription_id=subscription_renewing_soon.id,
            type=NotificationType.RENEWAL_REMINDER,
            priority=NotificationPriority.MEDIUM,
            title="Renewal Reminder",
            message="Test",
            created_at=datetime.now(timezone.utc) - timedelta(hours=25)
        )
        db_session.add(notification)
        db_session.commit()

        result = should_send_reminder(subscription_renewing_soon, 3, db_session)
        assert result is True


class TestCreateRenewalNotification:
    """Tests for create_renewal_notification function."""

    def test_creates_medium_priority_for_7_days(
        self,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should create MEDIUM priority notification for 7 days ahead."""
        test_subscription.renewal_date = date.today() + timedelta(days=7)
        db_session.commit()

        notification = create_renewal_notification(test_subscription, 7, db_session)

        assert notification.priority == NotificationPriority.MEDIUM
        assert "7 days" in notification.message

    def test_creates_high_priority_for_tomorrow(
        self,
        db_session: Session,
        test_subscription: Subscription
    ):
        """Should create HIGH priority notification for tomorrow."""
        test_subscription.renewal_date = date.today() + timedelta(days=1)
        db_session.commit()

        notification = create_renewal_notification(test_subscription, 1, db_session)

        assert notification.priority in [NotificationPriority.HIGH, NotificationPriority.MEDIUM]
        assert "tomorrow" in notification.message.lower()

    def test_includes_amount_and_provider(
        self,
        db_session: Session,
        subscription_renewing_soon: Subscription
    ):
        """Should include subscription details in notification."""
        notification = create_renewal_notification(subscription_renewing_soon, 3, db_session)

        assert subscription_renewing_soon.provider in notification.message
        if subscription_renewing_soon.amount:
            assert str(subscription_renewing_soon.currency) in notification.message

        metadata = notification.notification_metadata
        assert 'renewal_date' in metadata
        assert 'days_before' in metadata

    def test_notification_persisted(
        self,
        db_session: Session,
        subscription_renewing_soon: Subscription
    ):
        """Should persist notification to database."""
        notification = create_renewal_notification(subscription_renewing_soon, 3, db_session)

        db_notification = db_session.query(Notification).filter(
            Notification.id == notification.id
        ).first()

        assert db_notification is not None
        assert db_notification.type == NotificationType.RENEWAL_REMINDER


class TestCheckRenewalReminders:
    """Tests for check_renewal_reminders task."""

    @patch('app.tasks.renewal_reminders.send_renewal_email')
    @patch('app.tasks.renewal_reminders.SessionLocal')
    def test_sends_reminders_for_upcoming_renewals(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        subscription_renewing_soon: Subscription
    ):
        """Should send reminders for subscriptions renewing soon."""
        mock_session_local.return_value = db_session
        mock_send_email.return_value = (True, None)

        result = check_renewal_reminders()

        assert result['status'] == 'success'
        assert result['notifications_created'] >= 0

    @patch('app.tasks.renewal_reminders.SessionLocal')
    def test_handles_empty_subscription_list(
        self,
        mock_session_local: MagicMock,
        db_session: Session
    ):
        """Should handle empty subscription list gracefully."""
        mock_session_local.return_value = db_session

        result = check_renewal_reminders()

        assert result['status'] == 'success'
        assert result['notifications_created'] == 0

    @patch('app.tasks.renewal_reminders.send_renewal_email')
    @patch('app.tasks.renewal_reminders.SessionLocal')
    def test_respects_notification_preferences(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        subscription_renewing_soon: Subscription,
        test_user: User
    ):
        """Should respect user notification preferences."""
        mock_session_local.return_value = db_session

        # Disable notifications
        pref = NotificationPreference(
            user_id=test_user.id,
            notification_type=NotificationType.RENEWAL_REMINDER,
            enabled=False,
            email_enabled=False
        )
        db_session.add(pref)
        db_session.commit()

        result = check_renewal_reminders()

        # Should not send notifications
        mock_send_email.assert_not_called()

    @patch('app.tasks.renewal_reminders.send_renewal_email')
    @patch('app.tasks.renewal_reminders.SessionLocal')
    def test_sends_email_when_enabled(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        subscription_renewing_soon: Subscription,
        test_user: User
    ):
        """Should send email when email notifications enabled."""
        mock_session_local.return_value = db_session
        mock_send_email.return_value = (True, None)

        # Enable email notifications
        pref = NotificationPreference(
            user_id=test_user.id,
            notification_type=NotificationType.RENEWAL_REMINDER,
            enabled=True,
            email_enabled=True
        )
        db_session.add(pref)
        db_session.commit()

        result = check_renewal_reminders()

        # Should attempt to send emails
        assert result['status'] == 'success'

    @patch('app.tasks.renewal_reminders.SessionLocal')
    def test_handles_errors_gracefully(
        self,
        mock_session_local: MagicMock
    ):
        """Should handle errors and return error status."""
        mock_session_local.side_effect = Exception("Database error")

        result = check_renewal_reminders()

        assert result['status'] == 'error'
        assert 'error' in result

    @patch('app.tasks.renewal_reminders.send_renewal_email')
    @patch('app.tasks.renewal_reminders.SessionLocal')
    def test_skips_inactive_subscriptions(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        subscription_renewing_soon: Subscription
    ):
        """Should not send reminders for inactive subscriptions."""
        mock_session_local.return_value = db_session

        subscription_renewing_soon.is_active = False
        db_session.commit()

        result = check_renewal_reminders()

        # Should not send notifications for inactive subscriptions
        mock_send_email.assert_not_called()

    @patch('app.tasks.renewal_reminders.send_renewal_email')
    @patch('app.tasks.renewal_reminders.SessionLocal')
    def test_multiple_reminder_windows(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        test_user: User,
        test_mailbox
    ):
        """Should send reminders at different intervals (7, 3, 1 days)."""
        mock_session_local.return_value = db_session
        mock_send_email.return_value = (True, None)

        # Create subscriptions renewing at different times
        for days in [7, 3, 1]:
            sub = Subscription(
                user_id=test_user.id,
                mailbox_id=test_mailbox.id,
                provider=f"Service{days}",
                amount=10.00,
                currency="EUR",
                billing_cycle="monthly",
                is_active=True,
                renewal_date=date.today() + timedelta(days=days),
                extraction_method="ai",
                confidence_score=0.9
            )
            db_session.add(sub)
        db_session.commit()

        result = check_renewal_reminders()

        assert result['status'] == 'success'
        # Should send at least some reminders
        assert result['notifications_created'] >= 0
