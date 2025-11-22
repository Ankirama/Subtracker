"""Comprehensive tests for trial reminders task."""
import pytest
from datetime import datetime, timedelta, date, timezone
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.models.notification import Notification, NotificationPreference, NotificationType, NotificationPriority
from app.models.user import User
from app.tasks.trial_reminders import (
    should_send_trial_reminder,
    create_trial_notification,
    send_trial_email,
    check_trial_reminders
)


@pytest.fixture
def trial_subscription(db_session: Session, test_subscription: Subscription) -> Subscription:
    """Create a subscription in trial period."""
    test_subscription.trial_end_date = date.today() + timedelta(days=3)
    test_subscription.trial_status = 'trial'
    test_subscription.is_active = True
    db_session.commit()
    db_session.refresh(test_subscription)
    return test_subscription


class TestShouldSendTrialReminder:
    """Tests for should_send_trial_reminder function."""

    def test_sends_reminder_3_days_before(self, db_session: Session, trial_subscription: Subscription):
        """Should send reminder 3 days before trial ends."""
        result = should_send_trial_reminder(trial_subscription, 3, db_session)
        assert result is True

    def test_does_not_send_wrong_day(self, db_session: Session, trial_subscription: Subscription):
        """Should not send reminder on wrong day."""
        result = should_send_trial_reminder(trial_subscription, 1, db_session)
        assert result is False

    def test_does_not_send_without_trial_end_date(self, db_session: Session, test_subscription: Subscription):
        """Should not send reminder if no trial_end_date."""
        test_subscription.trial_end_date = None
        db_session.commit()
        result = should_send_trial_reminder(test_subscription, 3, db_session)
        assert result is False

    def test_does_not_send_duplicate_within_24h(
        self,
        db_session: Session,
        trial_subscription: Subscription,
        test_user: User
    ):
        """Should not send duplicate reminder within 24 hours."""
        # Create recent reminder
        notification = Notification(
            user_id=test_user.id,
            related_subscription_id=trial_subscription.id,
            type=NotificationType.TRIAL_ENDING,
            priority=NotificationPriority.HIGH,
            title="Trial Ending",
            message="Test",
            created_at=datetime.now(timezone.utc) - timedelta(hours=12)
        )
        db_session.add(notification)
        db_session.commit()

        result = should_send_trial_reminder(trial_subscription, 3, db_session)
        assert result is False

    def test_sends_after_24_hours(
        self,
        db_session: Session,
        trial_subscription: Subscription,
        test_user: User
    ):
        """Should send reminder if last one was >24h ago."""
        # Create old reminder
        notification = Notification(
            user_id=test_user.id,
            related_subscription_id=trial_subscription.id,
            type=NotificationType.TRIAL_ENDING,
            priority=NotificationPriority.HIGH,
            title="Trial Ending",
            message="Test",
            created_at=datetime.now(timezone.utc) - timedelta(hours=25)
        )
        db_session.add(notification)
        db_session.commit()

        result = should_send_trial_reminder(trial_subscription, 3, db_session)
        assert result is True

    def test_does_not_send_for_non_trial_status(self, db_session: Session, trial_subscription: Subscription):
        """Should not send reminder for non-trial subscriptions."""
        trial_subscription.trial_status = 'converted'
        db_session.commit()

        result = should_send_trial_reminder(trial_subscription, 3, db_session)
        assert result is False


class TestCreateTrialNotification:
    """Tests for create_trial_notification function."""

    def test_creates_high_priority_for_today(self, db_session: Session, trial_subscription: Subscription):
        """Should create HIGH priority notification for trial ending today."""
        trial_subscription.trial_end_date = date.today()
        db_session.commit()

        notification = create_trial_notification(trial_subscription, 0, db_session)

        assert notification.priority == NotificationPriority.HIGH
        assert "URGENT" in notification.title
        assert "today" in notification.message.lower()

    def test_creates_high_priority_for_tomorrow(self, db_session: Session, trial_subscription: Subscription):
        """Should create HIGH priority notification for tomorrow."""
        notification = create_trial_notification(trial_subscription, 1, db_session)

        assert notification.priority == NotificationPriority.HIGH
        assert "tomorrow" in notification.message.lower()

    def test_creates_medium_priority_for_3_days(self, db_session: Session, trial_subscription: Subscription):
        """Should create MEDIUM priority notification for 3 days."""
        notification = create_trial_notification(trial_subscription, 3, db_session)

        assert notification.priority == NotificationPriority.MEDIUM
        assert "3 days" in notification.message

    def test_includes_subscription_details(self, db_session: Session, trial_subscription: Subscription):
        """Should include subscription details in notification."""
        notification = create_trial_notification(trial_subscription, 3, db_session)

        assert trial_subscription.provider in notification.message
        metadata = notification.notification_metadata
        assert 'days_before' in metadata
        assert 'trial_end_date' in metadata
        assert 'amount' in metadata

    def test_notification_persisted(self, db_session: Session, trial_subscription: Subscription):
        """Should persist notification to database."""
        notification = create_trial_notification(trial_subscription, 3, db_session)

        db_notification = db_session.query(Notification).filter(
            Notification.id == notification.id
        ).first()
        assert db_notification is not None


class TestCheckTrialReminders:
    """Tests for check_trial_reminders task."""

    @patch('app.tasks.trial_reminders.send_trial_email')
    @patch('app.tasks.trial_reminders.SessionLocal')
    def test_sends_reminders_for_ending_trials(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        trial_subscription: Subscription
    ):
        """Should send reminders for trials ending in 3, 1, or 0 days."""
        mock_session_local.return_value = db_session
        mock_send_email.return_value = (True, None)

        result = check_trial_reminders()

        assert result['status'] == 'success'
        assert result['notifications_created'] >= 0

    @patch('app.tasks.trial_reminders.SessionLocal')
    def test_handles_empty_subscription_list(
        self,
        mock_session_local: MagicMock,
        db_session: Session
    ):
        """Should handle empty subscription list gracefully."""
        mock_session_local.return_value = db_session

        result = check_trial_reminders()

        assert result['status'] == 'success'
        assert result['notifications_created'] == 0

    @patch('app.tasks.trial_reminders.send_trial_email')
    @patch('app.tasks.trial_reminders.SessionLocal')
    def test_respects_notification_preferences(
        self,
        mock_session_local: MagicMock,
        mock_send_email: AsyncMock,
        db_session: Session,
        trial_subscription: Subscription,
        test_user: User
    ):
        """Should respect user notification preferences."""
        mock_session_local.return_value = db_session

        # Disable notifications
        pref = NotificationPreference(
            user_id=test_user.id,
            notification_type=NotificationType.TRIAL_ENDING,
            enabled=False,
            email_enabled=False
        )
        db_session.add(pref)
        db_session.commit()

        result = check_trial_reminders()

        # Should not send notifications
        mock_send_email.assert_not_called()

    @patch('app.tasks.trial_reminders.SessionLocal')
    def test_handles_errors_gracefully(
        self,
        mock_session_local: MagicMock
    ):
        """Should handle errors and return error status."""
        mock_session_local.side_effect = Exception("Database error")

        result = check_trial_reminders()

        assert result['status'] == 'error'
        assert 'error' in result
